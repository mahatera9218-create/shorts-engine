"""시장조사 엔진 테스트. 실행: python -m unittest discover -s tests"""
import base64
import hashlib
import hmac
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from market import naver_ad, naver_hub, run, scoring
from market.common import SECRET_GROUPS, load_yaml


class NaverAdTest(unittest.TestCase):
    def test_signature_format(self):
        expected = base64.b64encode(hmac.new(b"s", b"1700000000000.GET./keywordstool", hashlib.sha256).digest()).decode()
        self.assertEqual(naver_ad.sign("1700000000000", "GET", "/keywordstool", "s"), expected)

    def test_normalize_handles_under_10(self):
        row = naver_ad.normalize({"relKeyword": "제습기", "monthlyPcQcCnt": "< 10", "monthlyMobileQcCnt": 1200,
                                  "monthlyAvePcClkCnt": 0.5, "monthlyAveMobileClkCnt": 10.2,
                                  "compIdx": "높음", "plAvgDepth": 15})
        self.assertEqual(row["volume"], 1205)
        self.assertEqual(row["competition_level"], 3)
        self.assertAlmostEqual(row["clicks"], 10.7)


class HubTest(unittest.TestCase):
    def test_clean_strips_tags(self):
        self.assertEqual(naver_hub.clean("<b>제습기</b> &amp; 추천"), "제습기 & 추천")

    def test_trend_is_year_over_year(self):
        # 여름에만 튀는 계절 상품: 작년 여름과 올해 여름이 같으면 추세 0
        summer = [10, 10, 10, 10, 10, 30, 30, 30, 10, 10, 10, 10]
        self.assertAlmostEqual(naver_hub.trend_direction(summer + summer[:8]), 0.0)
        self.assertAlmostEqual(naver_hub.trend_direction(summer + [10, 10, 10, 10, 10, 60, 60, 60]), 1.0)
        self.assertEqual(naver_hub.trend_direction([1] * 12), 0.0)


class BlogCountTest(unittest.TestCase):
    def test_total_comes_from_relevance_sort(self):
        def fake(method, url, headers=None, params=None, json=None):
            if params["sort"] == "sim":
                return {"total": 271010, "items": [{}]}
            return {"total": 563, "items": [{"title": "t", "bloggername": "b", "postdate": "20260920"}]}
        hub = naver_hub.ApiHub({"base": "https://x", "blog_search": "/b"})
        with mock.patch.object(naver_hub, "request_json", side_effect=fake), mock.patch.object(naver_hub.time, "sleep"):
            out = hub.blog("기아차종류")
        self.assertEqual(out["total"], 271010)
        self.assertEqual(out["items"][0]["postdate"], "20260920")


class ScoringTest(unittest.TestCase):
    cfg = load_yaml("global.yaml")

    def row(self, kw, volume, blog_total, postdate="20240101", **kw_extra):
        return {"keyword": kw, "volume": volume, "clicks": volume * 0.01, "competition_level": 2,
                "ad_depth": 8, "blog_total": blog_total, "affiliate_prior": 3, "area_id": "a", "area_name": "A",
                "blog_items": [{"postdate": postdate, "blogger": "x"}], **kw_extra}

    def test_monthly_new_posts(self):
        today = date(2026, 9, 29)
        # 100개가 모두 10일 안 → 한 달 약 300개로 추정
        busy = ["20260929"] * 50 + ["20260919"] * 50
        self.assertAlmostEqual(scoring.monthly_new_posts(busy, 100, today), 300.0)
        # 30일 안 글 3개뿐, 자리표시 날짜(19900101)는 버림
        quiet = ["20260925", "20260920", "20260905", "20250101", "19900101"]
        self.assertEqual(scoring.monthly_new_posts(quiet, 100, today), 3.0)
        self.assertIsNone(scoring.monthly_new_posts(["19900101"], 100, today))

    def test_quiet_competition_wins(self):
        today = date(2026, 9, 29)
        rows = [self.row("조용", 10000, 50000, postdate="20250101"),
                self.row("붐빔", 10000, 50000, postdate="20260929")]
        rows[1]["blog_items"] = [{"postdate": "20260929", "blogger": "x"}] * 100
        out = scoring.score(rows, self.cfg["weights"], {}, today=today)
        self.assertEqual(out[0]["keyword"], "조용")

    def test_relevance_filter(self):
        seeds = ["사업자 세금", "소상공인 지원금"]
        self.assertTrue(scoring.related_to_seeds("소상공인정책자금", seeds))
        self.assertFalse(scoring.related_to_seeds("번역", seeds))
        self.assertTrue(scoring.related_to_seeds("번역", seeds, ["번역"]))

    def test_less_supply_scores_higher(self):
        rows = [self.row("가", 10000, 1000), self.row("나", 10000, 1000000), self.row("다", 500, 5000)]
        out = scoring.score(rows, self.cfg["weights"], {}, today=date(2026, 9, 29))
        self.assertEqual(out[0]["keyword"], "가")
        self.assertEqual(out[0]["score"], 100.0)

    def test_regulated_flag_without_false_positive(self):
        terms = self.cfg["regulated_terms"]
        self.assertEqual(scoring.regulated_category("자동차 대출 금리", terms), "금융")
        self.assertIsNone(scoring.regulated_category("전자계약 방법", terms))
        self.assertEqual(scoring.regulated_category("카니발장기렌트", terms), "금융")
        for safe in ["체크리스트", "크리스마스선물", "로봇청소기"]:
            self.assertIsNone(scoring.regulated_category(safe, terms))

    def test_area_summary_excludes_regulated(self):
        rows = [self.row("대출 비교", 90000, 100), self.row("제습기", 1000, 1000)]
        out = scoring.score(rows, self.cfg["weights"], self.cfg["regulated_terms"])
        areas = scoring.area_summary(out)
        self.assertEqual(len(areas[0]["regulated"]), 1)
        self.assertEqual([k["keyword"] for k in areas[0]["top"]], ["제습기"])


class UniqueDirTest(unittest.TestCase):
    def test_same_day_run_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "2026-09-29"
            self.assertEqual(run.unique_dir(base), base)
            base.mkdir()
            self.assertEqual(run.unique_dir(base).name, "2026-09-29-2")
            (Path(d) / "2026-09-29-2").mkdir()
            self.assertEqual(run.unique_dir(base).name, "2026-09-29-3")


class VerdictTest(unittest.TestCase):
    rules = load_yaml("global.yaml")["verdict"]

    def area(self, trend=0.0, monthly=50, win=0.8, regulated=0, keywords=3):
        kw = [{"trend": trend, "monthly_new_posts": monthly, "axes": {"win": win}} for _ in range(keywords)]
        return {"top": kw, "keywords": kw, "regulated": [{}] * regulated}

    def test_rules(self):
        self.assertEqual(scoring.suggest_verdict(self.area(), self.rules)[0], "진입 후보")
        self.assertEqual(scoring.suggest_verdict(self.area(trend=-0.5), self.rules)[0], "제외")
        self.assertEqual(scoring.suggest_verdict(self.area(monthly=5000), self.rules)[0], "제외")
        self.assertEqual(scoring.suggest_verdict(self.area(regulated=5), self.rules)[0], "제외")
        self.assertEqual(scoring.suggest_verdict(self.area(win=0.1), self.rules)[0], "보류")
        self.assertEqual(scoring.suggest_verdict(self.area(keywords=0), self.rules)[0], "제외")


class RunTest(unittest.TestCase):
    def test_secret_names_match_kickoff(self):
        names = sum(SECRET_GROUPS.values(), [])
        kickoff = Path(__file__).resolve().parent.parent.joinpath("KICKOFF.md").read_text(encoding="utf-8")
        for n in names:
            self.assertIn(f"`{n}`", kickoff)

    def test_missing_secrets_stops_with_message(self):
        with tempfile.NamedTemporaryFile("r", suffix=".md", delete=False) as f:
            env = {"GITHUB_STEP_SUMMARY": f.name}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(run.run(sample=False), 1)
            text = Path(f.name).read_text(encoding="utf-8")
        self.assertIn("NAVER_AD_API_KEY", text)

    def test_sample_run_writes_three_memos(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(run, "ROOT", Path(d)):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(run.run(sample=True), 0)
            files = sorted(p.name for p in (Path(d) / "reports" / "sample").iterdir())
        self.assertEqual(len([f for f in files if f.startswith("memo-")]), 3)
        self.assertIn("00-요약-점수표.md", files)

    def test_memo_follows_skill_template(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(run, "ROOT", Path(d)):
            with mock.patch.dict(os.environ, {}, clear=True):
                run.run(sample=True)
            memo = next((Path(d) / "reports" / "sample").glob("memo-1-*.md")).read_text(encoding="utf-8")
        for heading in ["투자 메모 —", "**결론:**", "| 축 | 점수 | 근거 |", "**예상 편당 매출:**", "**예상 편당 원가:**",
                        "**상위 경쟁자 요약:**", "**빈틈과 우리의 정보 이득:**", "**대표 키워드 10개**",
                        "**규제·리스크**", "**검증할 가정**"]:
            self.assertIn(heading, memo)


if __name__ == "__main__":
    unittest.main()


class BenchmarkTest(unittest.TestCase):
    def test_repeated_blogs_become_candidates(self):
        from market import benchmark
        post = lambda b, t, d: {"blogger": b, "blog_link": f"https://blog.naver.com/{b}", "title": t,
                                "link": f"{b}/{t}", "postdate": d}
        results = {
            "연봉 순위": [post("a", "2026 연봉 순위 TOP10", "20260925"), post("b", "잡담", "20260101")],
            "몸값 순위": [post("a", "몸값 1위는?", "20260920"), post("c", "몸값 vs 성적", "20260928")],
            "이적료": [post("c", "이적료 비교", "20260927")],
        }
        out = benchmark.find_candidates(results, min_queries=2, top_n=5, today=date(2026, 9, 29))
        self.assertEqual({b["name"] for b in out}, {"a", "c"})
        self.assertEqual(out[0]["query_hits"], 2)

    def test_title_patterns(self):
        from market import benchmark
        p = benchmark.title_patterns(["연봉 순위 TOP10", "A vs B 비교", "그냥 제목"])
        self.assertAlmostEqual(p["digit"], 1 / 3)
        self.assertAlmostEqual(p["versus"], 1 / 3)


class ProbeTest(unittest.TestCase):
    def test_estimate_uses_anchor_volume(self):
        class Tool:
            def related(self, seeds):
                return [{"keyword": "휘발유가격", "volume": 60000.0}]

        class Hub:
            def relative_last_month(self, anchor, keywords):
                return {"손흥민": 2.5, "이정후": 0.5}

        areas = [{"name": "스포츠", "probe_keywords": ["손흥민", "이정후"]}]
        notes = []
        out = run.estimate_probes(Tool(), Hub(), areas, {"anchor": "휘발유가격"}, notes)
        self.assertEqual(out[0]["keyword"], "손흥민")
        self.assertAlmostEqual(out[0]["est_volume"], 150000.0)
        self.assertAlmostEqual(out[1]["est_volume"], 30000.0)
