"""세무 도식 생성기(content/tax_cards.py) 테스트. 숫자 계산·라벨·렌더를 고정한다."""
import tempfile
import unittest
from pathlib import Path

from content import tax_cards


class TaxCardsTest(unittest.TestCase):
    def test_won_label(self):
        assert tax_cards.won_label(14_000_000) == "1,400만원"
        assert tax_cards.won_label(150_000_000) == "1억 5,000만원"
        assert tax_cards.won_label(1_000_000_000) == "10억원"
        assert tax_cards.won_label(1_260_000) == "126만원"
        assert tax_cards.won_label(0) == "0원"

    def test_calc_matches_known_example(self):
        cfg = tax_cards._cfg()
        r = tax_cards._calc(60_000_000, cfg)  # 과세표준 6,000만원
        assert r["rate"] == 0.24
        assert r["tax"] == 8_640_000          # 6,000만 × 24% − 576만 = 864만
        assert r["local"] == 864_000          # 지방소득세 10%
        assert r["total"] == 9_504_000

    def test_bracket_rows(self):
        rows = tax_cards._bracket_rows(tax_cards._cfg())
        assert len(rows) == 8
        assert rows[0][0] == "1,400만원 이하" and rows[0][1] == "6%"
        assert rows[-1][0] == "10억원 초과" and rows[-1][1] == "45%"

    def test_render_runs(self):
        with tempfile.TemporaryDirectory() as d:
            t = tax_cards.rate_table_card(Path(d) / "t.png")
            c = tax_cards.calc_card(Path(d) / "c.png", 60_000_000)
            assert t.exists() and t.stat().st_size > 1000
            assert c.exists() and c.stat().st_size > 1000


if __name__ == "__main__":
    unittest.main()
