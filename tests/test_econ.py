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
            self.assertIn("성과", html)

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
        from content import econ_score
        items = [{"kw": "청년미래적금", "rows": ["B1", "B2", "G1", "N1"]}, {"kw": "금값", "rows": ["G2"]}]
        src = {"B1": "zkfldb888", "B2": "블로거", "G1": "Grok", "N1": "국내뉴스", "G2": "Grok"}
        out = econ_score.score(items, src)
        self.assertEqual(out[0]["kw"], "청년미래적금")
        self.assertEqual(out[0]["parts"]["출처"], 15)  # 그날 1등 = 출처 만점 (2026-10-10 네이버 비중 강화로 출처 20→15)
        self.assertEqual(out[1]["parts"]["출처"], round(15 * 6 / 12))  # 쿠니네(zkfldb888)는 키워드 점수에서 뺌 (2026-10-07)
        self.assertEqual(out[0]["score"], round(15 * 100 / 65))  # 어사이드 없는 날은 나머지 65점을 100점으로 환산

    def test_score_aside_rank(self):
        from content import econ_score
        items = [{"kw": "원달러 환율", "rows": [], "sources": {"Grok": 1}},
                 {"kw": "금값", "rows": [], "sources": {"어사이드": 1}, "naver_rank": 2},
                 {"kw": "코스피", "rows": [], "sources": {"어사이드": 1}, "naver_rank": 8}]
        out = {x["kw"]: x for x in econ_score.score(items, None)}
        self.assertEqual(out["금값"]["parts"]["네이버"], 35)   # 어사이드 1~3위 만점
        self.assertEqual(out["코스피"]["parts"]["네이버"], round(35 * 0.5))  # 7~10위 절반
        self.assertEqual(out["원달러 환율"]["score"], out["원달러 환율"]["parts"]["출처"])  # 어사이드 있는 날은 환산 없음
        self.assertGreater(out["금값"]["score"], out["원달러 환율"]["score"])

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


if __name__ == "__main__":
    unittest.main()
