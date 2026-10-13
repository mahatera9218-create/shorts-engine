"""경제판 핵심 동작 시험 (키 없이 도는 것만)."""
import tempfile
import unittest
from pathlib import Path


class EconTest(unittest.TestCase):
    def test_imports(self):
        import content.econ_flow, content.econ_desk, content.econ_inbox, content.post_art, content.art_library  # noqa: F401
        import content.head_swap, content.hook_thumb  # noqa: F401
        from content import celeb, kunine  # 글 흐름에 꼭 있어야 할 함수 (2026-10-06 편집 실수로 지워진 적 있음)
        for m, names in ((kunine, ("research", "titles", "produce", "TITLES", "BODY")), (celeb, ("research", "titles", "produce"))):
            for n in names:
                self.assertTrue(hasattr(m, n), f"{m.__name__}.{n} 없음")

    def test_desk_builds(self):
        from content import econ_desk
        with tempfile.TemporaryDirectory() as d:
            econ_desk.build(Path(d) / "site")
            html = (Path(d) / "site" / "index.html").read_text(encoding="utf-8")
            # 대표 결정 2026-10-13: 키워드 도구 3탭(순번·경제 키워드·패션 키워드), 성과는 숨겨도 코드엔 남김
            self.assertIn("경제 순번", html)
            self.assertIn("경제 키워드", html)
            self.assertIn("패션 키워드", html)
            self.assertIn('id="stats"', html)

    def test_edit_parse(self):
        from content.edits import parse
        title, blocks = parse("제목: 새 제목\n\n[문단 2]\n고친 문단\n\n아래 초록색 Create 버튼만 누르면 됩니다.")
        self.assertEqual(title, "새 제목")
        self.assertEqual(blocks, {2: "고친 문단"})

    def test_cost_guard_reads_csv(self):
        from content import econ_flow as F
        old = F.COSTS
        with tempfile.TemporaryDirectory() as d:
            F.COSTS = Path(d) / "c.csv"
            F.COSTS.write_text("date,time,cmd,item,claude_usd,gpt_usd,grok_usd,image_usd,total_usd\n"
                               f"{F.today()},06:00,produce,x,1,0,0,0,160\n", encoding="utf-8")
            self.assertEqual(F.month_spent_krw(), 224000)  # 상한 22만원 넘김
            with self.assertRaises(SystemExit):
                F.guard()
        F.COSTS = old

    def test_score_counts_overlap(self):
        from unittest import mock
        from content import econ_score
        items = [{"kw": "청년미래적금", "rows": ["B1", "B2", "G1", "N1"]}, {"kw": "금값", "rows": ["G2"]}]
        src = {"B1": "zkfldb888", "B2": "블로거", "G1": "Grok", "N1": "국내뉴스", "G2": "Grok"}
        with mock.patch.object(econ_score, "_recent_cores", return_value={}):  # 디스크의 '최근 반복 주제' 데이터에 오염되지 않게 (점수 계산만 검증)
            out = econ_score.score(items, src)
        # 출처(화제성)에서 블로거는 뺀다(최신성으로 감). 청년: Grok6+국내뉴스2=8, 금값: Grok6. 쿠니네(zkfldb888)는 0점.
        self.assertEqual(out[0]["kw"], "청년미래적금")
        self.assertEqual(out[0]["parts"]["출처"], 11)  # 그날 1등 = 출처 만점(w 출처 11, 화제성:최신성:수요 2:1:1 2026-10-10)
        self.assertEqual(out[1]["parts"]["출처"], round(11 * 6 / 8))  # Grok만(6) / 1등(8)
        self.assertEqual(out[0]["score"], 11)  # 블로거·어사이드 없어 최신성 0, 뉴스·검색 없음 → 출처만. 환산 없음(2:1:1)

    def test_score_aside_rank(self):
        from unittest import mock
        from content import econ_score
        items = [{"kw": "원달러 환율", "rows": [], "sources": {"Grok": 1}},
                 {"kw": "금값", "rows": [], "sources": {"어사이드": 1}, "naver_rank": 2},
                 {"kw": "코스피", "rows": [], "sources": {"어사이드": 1}, "naver_rank": 8}]
        with mock.patch.object(econ_score, "_recent_cores", return_value={}):  # 디스크 '최근 반복 주제' 감점에 오염되지 않게
            out = {x["kw"]: x for x in econ_score.score(items, None)}
        # 어사이드는 최신성의 '보조'(네이버 weight 15). 블로거 없으면 어사이드만으로 최신성.
        self.assertEqual(out["금값"]["parts"]["최신"], 15)   # 어사이드 1~3위 → 보조 만점(15)
        self.assertEqual(out["코스피"]["parts"]["최신"], round(15 * 0.5))  # 7~10위 절반
        self.assertNotIn("최신", out["원달러 환율"]["parts"])  # 블로거·어사이드 둘 다 없으면 최신성 없음
        self.assertGreater(out["금값"]["score"], out["원달러 환율"]["score"])

    def test_score_blogger_freshness(self):
        from unittest import mock
        from content import econ_score
        full = econ_score.F.load(econ_score.CFG(), {}).get("blogger_full", 2)  # 블로그별 만점 기준(경제 3·패션 2)
        # 최신성 블로거: 서로 다른 블로거 수로 센다(같은 블로거 반복은 무시). full명이면 만점.
        items = [{"kw": "A", "rows": [], "sources": {}, "bloggers": [f"b{i}" for i in range(full)]},
                 {"kw": "B", "rows": [], "sources": {}, "bloggers": ["b1"]}]
        with mock.patch.object(econ_score, "_recent_cores", return_value={}):
            out = {x["kw"]: x for x in econ_score.score(items, None)}
        self.assertEqual(out["A"]["parts"]["최신"], 25)        # 서로 다른 블로거 full명 = 최신성 만점
        self.assertEqual(out["B"]["parts"]["최신"], round(25 * 1 / full))  # 1명 = 비율만큼
        self.assertGreater(out["A"]["score"], out["B"]["score"])  # 블로거 많을수록 위 (선정 우선순위 블로거→어사이드)

    def test_kunine_check(self):
        from content import kunine
        a = {"intro": ["삼성전자 이야기"], "sections": [{"heading": "왜", "images": [], "paragraphs": ["연합뉴스에 따르면 올랐다"]}],
             "closing": ["끝"], "qa": [{"q": "q", "a": "a"}] * 3, "tags": ["t"] * 20}
        bad = kunine.check(a, "삼성전자 주가")
        self.assertTrue(any("언론사명" in b for b in bad))
        self.assertTrue(any("5~7개" in b for b in bad) and any("표 없음" in b for b in bad))  # 2026-10-10 원문
        a["sections"] = [{"heading": f"왜 {i}?", "images": [], "paragraphs": ["회사 공식 발표에 따르면 올랐다"]} for i in range(5)]
        a["table"] = {"title": "t", "header": ["a", "b"], "rows": [["1", "2"]], "after": 1}
        self.assertEqual(kunine.check(a, "삼성전자 주가"), [])

    def test_blogs(self):
        from content import blogs
        b = blogs.all_blogs()
        self.assertEqual({k: v["label"] for k, v in b.items()}, {"econ": "경제", "fashion": "패션"})  # 연예는 패션에 합침
        self.assertEqual(blogs.by_label("패션")["name"], "캐시미어 다이어리")

    def test_celeb_check(self):
        import os
        os.environ["BLOG"] = "fashion"
        try:
            import importlib
            from content import econ_flow, celeb
            importlib.reload(econ_flow)
            importlib.reload(celeb)
            a = {"greeting": "캐시미어 다이어리의 캐다입니다.", "sections": [{"heading": "h", "images": [], "paragraphs": ["첨부한 사진을 보면 예뻐요"]},
                                                                    {"heading": "끝", "images": [], "paragraphs": ["마무리"]}],
                 "tags": ["t"] * 25}
            bad = " ".join(celeb.check(a))
            for word in ("1,500자", "소제목 구간", "제작 과정", "해시태그", "자기소개", "사진 없는 구간"):
                self.assertIn(word, bad)
        finally:
            os.environ.pop("BLOG", None)
            importlib.reload(econ_flow)

    def test_written_recent_days(self):
        """이미 쓴 주제: core별 마지막 날과 (날, 제목) 목록 (대표 결정 2026-10-11 초대형 3일 간격)."""
        from unittest import mock
        from content import econ_flow as F
        from content.econ_score import _written_recent
        with tempfile.TemporaryDirectory() as d:
            flow = Path(d)
            for day, kw, title in [("2026-10-09", "삼성전자 성과급", "삼성전자 성과급 A"),
                                   ("2026-10-10", "삼성전자 주가", "삼성전자 주가 B")]:
                t = flow / day / kw.replace(" ", "-")
                t.mkdir(parents=True)
                (t / "chosen.yaml").write_text(f"kw: {kw}\ntitle: {title}\n", encoding="utf-8")
            with mock.patch.object(F, "FLOW", flow), mock.patch.object(F, "today", lambda: "2026-10-11"):
                cores, titles = _written_recent(14)
        self.assertEqual(cores["삼성전자"], "2026-10-10")
        self.assertIn(("2026-10-09", "삼성전자 성과급 A"), titles)


    def test_title_style(self):
        """제목 방식 판정: 따옴표 = 속마음형 (대표 결정 2026-10-11)."""
        from content.kunine import title_style
        self.assertEqual(title_style("삼성전자 성과급 '7.5억 받는다던데...' 실제 통장엔 얼마"), "속마음형")
        self.assertEqual(title_style("삼성전자 성과급 7.5억이라더니, 세후는 3.4억대 추산"), "숫자형")

    def test_title_style_blend(self):
        from content.kunine import title_style
        self.assertEqual(title_style("삼성전자 주가 '107조 벌었는데 왜 못 올라' 외국인이 '이것' 보고 있다는데"), "버무린형")
        self.assertEqual(title_style("현대차 주가 '32만원도 위태롭다' 개미들이 '이 가격' 앞에서 망설이는 이유"), "버무린형")
        self.assertEqual(title_style("금값 시세 '안전자산이라 믿고 샀는데..' 순금 1돈, 지금 팔면 얼마 남을까?"), "속마음형")
        self.assertEqual(title_style("SK하이닉스, 반도체 “공급부족 정말 2030년까지 이어질까?”"), "속마음형")
        self.assertEqual(title_style("원달러 환율 1330원대 지지 여부부터 확인하세요"), "숫자형")


if __name__ == "__main__":
    unittest.main()