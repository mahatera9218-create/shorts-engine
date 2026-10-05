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
            self.assertIn("📊 성과", html)

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
        self.assertEqual(out[0]["parts"]["출처"], 10 + 4 + 6 + 2)
        self.assertEqual(out[1]["parts"]["출처"], 6)


if __name__ == "__main__":
    unittest.main()
