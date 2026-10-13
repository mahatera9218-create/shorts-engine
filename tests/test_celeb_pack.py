"""패션 조사 세트: 확인 안 된 값 지우기 · 붙여넣을 글 만들기 (키 없이)."""
import unittest

from content import celeb_pack as P


class PackTest(unittest.TestCase):
    def test_clean_drops_unknown(self):
        d = P.clean({"person": "전지현", "age": "확인 안 됨", "what_happened": "공항 출국", "worn_confirmed": False, "worn_basis": "",
                     "products": [{"brand_ko": "샤넬", "brand_en": "Chanel", "name_en": "Flap", "list_price_krw": "정보 없음",
                                   "sale_price_krw": "", "model_no": "-"}, {"brand_ko": "", "name_en": "미확인"}],
                     "styling": "", "related_people": [], "reactions": [{"text": "", "rumor": False}], "photo_links": [], "sources": [{"title": "", "url": ""}]})
        self.assertNotIn("age", d)
        self.assertEqual(len(d["products"]), 1)
        self.assertEqual(set(d["products"][0]), {"brand_ko", "brand_en", "name_en"})
        self.assertNotIn("styling", d)
        self.assertNotIn("sources", d)
        self.assertFalse(d["worn_confirmed"])

    def test_render_no_empty_lines(self):
        d = P.clean({"person": "전지현", "what_happened": "공항 출국", "worn_confirmed": True, "worn_basis": "공식 SNS",
                     "products": [{"brand_ko": "샤넬", "brand_en": "Chanel", "name_en": "Medium Flap", "list_price_krw": "1,000만원", "price_asof": "2026-10-12"}]})
        t = P.render("전지현 / 10월 공항 / 샤넬 플랩", d, "2026-10-12")
        self.assertTrue(t.startswith("전지현 / 10월 공항 / 샤넬 플랩"))
        self.assertTrue(t.rstrip().endswith("출발"))
        self.assertIn("착용 확인: 됨 (근거: 공식 SNS)", t)
        self.assertIn("정가: 1,000만원", t)
        self.assertNotIn("할인가", t)
        self.assertNotIn("확인 안 됨", t.replace("착용 확인: 안 됨", ""))

    def test_render_profile_age(self):
        d = P.clean({"person": "장원영", "birth": "2004년생", "age": "22세", "worn_confirmed": True})
        t = P.render("a / b / c", d, "2026-10-13")
        self.assertIn("인물 프로필(나이): 2004년생 · 만 22세 (2026-10-13 기준)", t)
        t2 = P.render("a / b / c", P.clean({"person": "a", "birth": "확인 안 됨"}), "2026-10-13")
        self.assertNotIn("인물 프로필", t2)

    def test_worn_false_flag(self):
        t = P.render("a / b / c", P.clean({"person": "a", "worn_confirmed": False}), "2026-10-12")
        self.assertIn("착용 확인: 안 됨", t)

    def test_parse(self):
        self.assertEqual(P.parse('설명 {"person": "a"} 끝'), {"person": "a"})
        self.assertEqual(P.parse("JSON 아님"), {})


if __name__ == "__main__":
    unittest.main()
