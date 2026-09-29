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

    def test_trend_direction(self):
        self.assertAlmostEqual(naver_hub.trend_direction([10, 10, 10, 20, 20, 20]), 1.0)
        self.assertEqual(naver_hub.trend_direction([1, 2]), 0.0)


class ScoringTest(unittest.TestCase):
    cfg = load_yaml("global.yaml")

    def row(self, kw, volume, blog_total, postdate="20240101", **kw_extra):
        return {"keyword": kw, "volume": volume, "clicks": volume * 0.01, "competition_level": 2,
                "ad_depth": 8, "blog_total": blog_total, "affiliate_prior": 3, "area_id": "a", "area_name": "A",
                "blog_items": [{"postdate": postdate, "blogger": "x"}], **kw_extra}

    def test_less_supply_scores_higher(self):
        rows = [self.row("가", 10000, 1000), self.row("나", 10000, 1000000), self.row("다", 500, 5000)]
        out = scoring.score(rows, self.cfg["weights"], {}, today=date(2026, 9, 29))
        self.assertEqual(out[0]["keyword"], "가")
        self.assertEqual(out[0]["score"], 100.0)

    def test_regulated_flag_without_false_positive(self):
        terms = self.cfg["regulated_terms"]
        self.assertEqual(scoring.regulated_category("자동차 대출 금리", terms), "금융")
        self.assertIsNone(scoring.regulated_category("전자계약 방법", terms))

    def test_area_summary_excludes_regulated(self):
        rows = [self.row("대출 비교", 90000, 100), self.row("제습기", 1000, 1000)]
        out = scoring.score(rows, self.cfg["weights"], self.cfg["regulated_terms"])
        areas = scoring.area_summary(out)
        self.assertEqual(len(areas[0]["regulated"]), 1)
        self.assertEqual([k["keyword"] for k in areas[0]["top"]], ["제습기"])


class VerdictTest(unittest.TestCase):
    rules = load_yaml("global.yaml")["verdict"]

    def area(self, trend=0.0, age=400, win=0.8, regulated=0, keywords=3):
        kw = [{"trend": trend, "top_median_age_days": age, "axes": {"win": win}} for _ in range(keywords)]
        return {"top": kw, "keywords": kw, "regulated": [{}] * regulated}

    def test_rules(self):
        self.assertEqual(scoring.suggest_verdict(self.area(), self.rules)[0], "진입 후보")
        self.assertEqual(scoring.suggest_verdict(self.area(trend=-0.5), self.rules)[0], "제외")
        self.assertEqual(scoring.suggest_verdict(self.area(age=30), self.rules)[0], "제외")
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
