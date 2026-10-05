"""경제판 핵심 동작 시험 (키 없이 도는 것만)."""
import tempfile
import unittest
from pathlib import Path


class EconTest(unittest.TestCase):
    def test_imports(self):
        import content.econ_flow, content.econ_desk, content.econ_inbox, content.post_art, content.art_library  # noqa: F401
        import content.head_swap, content.hook_thumb  # noqa: F401

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
                               f"{F.today()},06:00,produce,x,1,0,0,0,40\n", encoding="utf-8")
            self.assertEqual(F.month_spent_krw(), 56000)
            with self.assertRaises(SystemExit):
                F.guard()
        F.COSTS = old

    def test_score_counts_overlap(self):
        from content import econ_score
        items = [{"kw": "청년미래적금", "rows": ["B1", "B2", "G1", "N1"]}, {"kw": "금값", "rows": ["G2"]}]
        src = {"B1": "zkfldb888", "B2": "블로거", "G1": "Grok", "N1": "국내뉴스", "G2": "Grok"}
        out = econ_score.score(items, src)
        self.assertEqual(out[0]["kw"], "청년미래적금")
        self.assertEqual(out[0]["parts"]["출처"], 40)  # 그날 1등 = 40
        self.assertEqual(out[1]["parts"]["출처"], round(40 * 6 / 22))

    def test_kunine_check(self):
        from content import kunine
        a = {"intro": ["삼성전자 이야기"], "sections": [{"heading": "왜", "images": [], "paragraphs": ["연합뉴스에 따르면 올랐다"]}],
             "closing": ["끝"], "qa": [{"q": "q", "a": "a"}] * 3, "tags": ["t"] * 20}
        bad = kunine.check(a, "삼성전자 주가")
        self.assertTrue(any("언론사명" in b for b in bad))
        a["sections"][0]["paragraphs"] = ["회사 공식 발표에 따르면 올랐다"]
        self.assertEqual(kunine.check(a, "삼성전자 주가"), [])

    def test_three_blogs(self):
        from content import blogs
        b = blogs.all_blogs()
        self.assertEqual([b[k]["label"] for k in ("econ", "ent", "fashion")], ["경제", "연예", "패션"])
        self.assertEqual(blogs.by_label("패션")["name"], "캐시미어 다이어리")

    def test_celeb_check(self):
        import os
        os.environ["BLOG"] = "fashion"
        try:
            import importlib
            from content import econ_flow, celeb
            importlib.reload(econ_flow)
            importlib.reload(celeb)
            a = {"greeting": "안녕하세요", "sections": [{"heading": "h", "images": [], "paragraphs": ["첨부한 사진을 보면 예뻐요"]}],
                 "summary": "세 가지가 좋았어요", "tags": ["t"] * 25}
            bad = " ".join(celeb.check(a))
            for word in ("1,500자", "요약", "제작 과정", "해시태그", "캐다입니다"):
                self.assertIn(word, bad)
        finally:
            os.environ.pop("BLOG", None)
            importlib.reload(econ_flow)


if __name__ == "__main__":
    unittest.main()
