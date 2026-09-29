"""자동 글쓰기의 코드 부분(숫자 충돌 규칙, 숫자 검사, 계산 입력) 테스트. 키 없이 돈다."""
import unittest

from content import receipt
from content.autopost import build_data, check_post, resolve, unknown_numbers

NEWS = [
    {"date": "2026-09-28", "link": "a"},
    {"date": "2026-09-20", "link": "b"},
    {"date": "2026-09-28", "link": "c"},
    {"date": "2026-09-28", "link": "d"},
]
CFG = {"constants": {"min_wage_monthly_krw": 2156880}}


def fact(key, value, source, unit="개"):
    return {"key": key, "label": key, "value": value, "unit": unit, "source": source}


def _ex(currency="USD", units=None):
    return {"salary_currency": currency, "salary_basis": "보도 기준", "season": 2026, "headline_unit": "hits",
            "units": units or [{"key": "games", "label": "1경기"}, {"key": "hits", "label": "1안타"}]}


def _facts(**kw):
    return {k: {"value": v, "date": "2026-09-28"} for k, v in kw.items()}


class ContentTest(unittest.TestCase):
    def test_resolve_latest_article_wins(self):
        r = resolve([fact("hits", 148, 2), fact("hits", 149, 1)], NEWS)
        assert r["hits"]["value"] == 149 and r["hits"]["rule"] == "최신 기사" and r["hits"]["differs"] == [148, 149]

    def test_resolve_same_day_majority(self):
        r = resolve([fact("hits", 149, 1), fact("hits", 150, 3), fact("hits", 149, 4)], NEWS)
        assert r["hits"]["value"] == 149 and r["hits"]["rule"] == "같은 날짜 다수"
        assert r["hits"]["sources"] == ["a", "d"]

    def test_resolve_ignores_bad_source_index(self):
        assert resolve([fact("hits", 1, 99)], NEWS) == {}

    def test_unknown_numbers(self):
        sheet = "1안타당: 2억 32만 원 · 타율 0.276 · 연봉 2,200만 달러"
        assert unknown_numbers("1안타에 2억 32만 원, 타율 0.276", sheet) == []
        assert unknown_numbers("9월 22일, 2026년", sheet) == []          # 날짜·연도는 허용
        assert unknown_numbers("1안타에 3억, 타율 0.301", sheet) == ["0.301"]  # 3은 작은 수라 통과, 0.301은 걸림
        assert unknown_numbers("연봉 2,300만 달러", sheet) == ["2,300"]

    def test_build_data_usd(self):
        d, why = build_data({"player": "가"}, _ex(), _facts(salary=22_000_000, fx_krw_per_usd=1356.7, games=143, hits=149), CFG)
        assert why == "" and d["salary_usd"] == 22_000_000 and [u["count"] for u in d["units"]] == [143, 149]
        n = receipt.compute(d)
        assert round(n["per"]["hits"]) == round(22_000_000 * 1356.7 / 149)

    def test_build_data_rejects_missing_or_absurd(self):
        assert build_data({"player": "가"}, _ex(), _facts(salary=22_000_000, games=1, hits=1), CFG)[0] is None  # 환율 없음
        assert build_data({"player": "가"}, _ex(), _facts(salary=113_000_000_0, fx_krw_per_usd=1356.7, games=1, hits=1), CFG)[0] is None
        assert build_data({"player": "가"}, _ex("KRW"), _facts(salary=2_000_000_000, games=30), CFG)[1] == "연봉을 나눌 기록이 2개 미만"

    def test_receipt_old_format_still_works(self):
        d = {"salary_usd": 1_000_000, "fx_krw_per_usd": 1000, "team_games": 100,
             "stats": {"games": 100, "at_bats": 400, "hits": 100, "home_runs": 0}}
        n = receipt.compute(d)
        assert set(n["per"]) == {"games", "at_bats", "hits"} and n["per_team_game"] == 10_000_000

    def test_innings_notation(self):
        d = {"salary_krw": 1_700_000_000, "units": [{"key": "innings", "label": "1이닝", "count": 85.2},
                                                     {"key": "games", "label": "1경기", "count": 10}]}
        assert round(receipt.compute(d)["per"]["innings"]) == round(1_700_000_000 / (85 + 2 / 3))
        assert receipt.compute(d)["per"]["games"] == 170_000_000

    def test_check_post(self):
        sheet = "1안타당: 2억 32만 원"
        good = {"body": "1안타에 2억.\n[1: thumb.png]\n[2: card_quiz.png]\n[3: card_answer.png]\n[4: card_wage.png]\n"
                        "[5: card_table.png]", "recommended": 1,
                "titles": [{"text": "1안타에 2억", "type": "숫자형"}] * 5}
        assert check_post(good, sheet) == []
        bad = {**good, "body": good["body"] + "\n토토 배당 3.5배", "titles": [{"text": "1안타에 5억 999만", "type": "숫자형"}] * 5}
        problems = " / ".join(check_post(bad, sheet))
        assert "금지 주제" in problems and "3.5" in problems and "제목1" in problems

    def test_quiz_answer_not_before_quiz(self):
        sheet = "1안타당: 2억 32만 원\n1홈런당: 29억 8,474만 원\n퀴즈 카드: 1홈런 1번에 받는 돈 맞히기 (정답 29억 8,474만 원)"
        imgs = "[1: thumb.png]\n{q}\n[2: card_quiz.png]\n[3: card_answer.png]\n[4: card_wage.png]\n[5: card_table.png]"
        base = {"recommended": 1, "titles": [{"text": "1안타에 2억", "type": "숫자형"}] * 5}
        ok = check_post({**base, "body": imgs.format(q="홈런 한 방은 얼마일까요?")}, sheet)
        early = check_post({**base, "body": imgs.format(q="홈런 한 방은 29억 8,474만 원이에요.")}, sheet)
        assert not any("퀴즈" in x for x in ok) and any("퀴즈 정답" in x for x in early)

    def test_quiz_options(self):
        from content.cards import nice, options
        assert nice(30_150_000) == 30_000_000 and nice(271_350_000) == 270_000_000
        opts, idx = options(90_450_000, "아무 글")
        assert opts[idx] == nice(90_450_000) and opts == sorted(opts) and len(set(opts)) == 3

    def test_titles(self):
        from content.autopost import check_titles
        sheet = ("제목용 짧은 이름: 오타니\n"
                 "썸네일: 오타니 쇼헤이 / 홈런 1개 / 9,045만원 (추천 제목에는 이 금액을 다시 쓰지 않는다)")
        good = {"recommended": 1, "tags": ["오타니", "MLB"],
                "titles": [{"text": "오타니 9,496억 계약인데 올해 27억?", "type": "반전형"}]
                + [{"text": "오타니 1경기에 얼마 받을까?", "type": "질문형"}] * 4}
        assert check_titles(good, sheet) == []
        bad = {"recommended": 1, "tags": ["MLB"],
               "titles": [{"text": "오타니 쇼헤이 홈런 9,045만원, 9,496억 계약인데 충격 연봉??", "type": "숫자형"},
                          {"text": "계약은 크지만 올해는 작다", "type": "반전형"}] * 2 + [{"text": "오타니 올해 연봉", "type": "질문형"}]}
        problems = " / ".join(check_titles(bad, sheet))
        for word in ("긴 이름", "과장어", "되풀이", "25자", "태그", "짧은 이름(오타니)으로 시작"):
            assert word in problems, word
        assert "숫자가 없음" in " / ".join(check_titles({**good, "titles": [{"text": "오타니 올해는 얼마?"}] * 5}, sheet))

    def test_won_only(self):
        sheet = "1안타당: 2억 32만 원"
        base = {"recommended": 1, "titles": [{"text": "1안타에 2억", "type": "숫자형"}] * 5}
        imgs = "\n[thumb.png][card_quiz.png][card_answer.png][card_wage.png][card_table.png]"
        ok = check_post({**base, "body": "1안타에 2억." + imgs + "\n기준: 1달러 1,356.7원"}, sheet)
        bad = check_post({**base, "body": "연봉은 2,200만 달러예요." + imgs}, sheet)
        assert not any("달러" in x for x in ok) and any("달러" in x for x in bad)

    def test_desk_parses_posts(self):
        import tempfile
        from pathlib import Path
        from content import desk
        for folder in Path("posts").glob("2026-*"):
            p = desk.parse(folder)
            assert p and len(p["titles"]) == 5 and sum(t["best"] for t in p["titles"]) == 1
            assert [x["n"] for x in p["images"]] == list(range(1, len(p["images"]) + 1)) and p["tags"]
        with tempfile.TemporaryDirectory() as d:
            desk.build(Path(d) / "site")
            html = (Path(d) / "site" / "index.html").read_text(encoding="utf-8")
            assert "noindex" in html and (Path(d) / "site" / "robots.txt").exists()

    def test_theme_plans(self):
        from content import themes
        from market.common import load_yaml
        pool = load_yaml("players.yaml")
        plans = themes.plans(pool, {"이정후"}, "2026-10-01", n=20)
        assert plans and all(p["theme"] in pool["themes"] for p in plans)
        for p in plans:
            names = [x["name"] for x in p["players"]]
            assert "이정후" not in names and len(set(names)) == len(names)
            if p["theme"] == "same":
                assert p["players"][0]["sport"] == p["players"][1]["sport"]
            if p["theme"] == "cross":
                assert p["players"][0]["sport"] != p["players"][1]["sport"]
        assert plans == themes.plans(pool, {"이정후"}, "2026-10-01", n=20)  # 같은 날 다시 돌려도 같은 뽑기

    def test_count_never_rounds_up(self):
        from content.themes import count, ratio
        assert count(1.68) == "1.6" and count(4.99) == "4.9" and count(23.9) == "23" and count(1234.5) == "1,234"
        assert count(2.0) == "2" and ratio(10.69) == "10.6"

    def test_images_from_sheet(self):
        from content import themes
        sheet = "1안타당: 2억 32만 원\n" + "\n".join(themes.image_lines("same"))
        body = "1안타에 2억.\n[thumb.png][card_quiz.png][card_answer.png]"
        p = {"body": body, "recommended": 1, "titles": [{"text": "1안타에 2억", "type": "숫자형"}] * 5}
        assert any("card_table.png" in x for x in check_post(p, sheet))
        assert not any("card_wage.png" in x for x in check_post({**p, "body": body + "[card_table.png]"}, sheet))

    def test_pick_prices_one_item(self):
        from collections import Counter
        from content.themes import pick_prices
        prices = {"group_weight": {"home": 1, "car_kr": 1, "car_import": 1}, "items": [
            {"key": k, "group": g, "label": k, "short": k, "unit": "대", "price_krw": 1, "as_of": "2026-09-01",
             "source": "x", "weight": w} for k, g, w in
            [("a", "home", 100), ("b", "home", 1), ("d", "car_kr", 100000), ("e", "car_import", 100000)]]}
        got = pick_prices(prices, "seed")
        assert len(got) == 1 and got == pick_prices(prices, "seed")
        groups = Counter(pick_prices(prices, str(i))[0]["group"] for i in range(300))
        assert all(v > 60 for v in groups.values())  # 차 검색량이 커도 집이 밀리지 않는다

    def test_count_small(self):
        from content.themes import count
        assert (count(0.5), count(0.036), count(0.0042)) == ("0.5", "0.03", "0.004")

    def test_fill_prices_checks_article(self):
        from content.autopost import eok_text, fill_prices
        assert "34억3000만" in eok_text(3_430_000_000) and "34억3천만" in eok_text(3_430_000_000)

        class Hub:
            def news(self, q, display=30):
                return [{"title": "은마 84㎡ 거래", "description": "전용 84㎡ 34억 3,000만원에 팔렸다",
                         "link": "https://n/1", "date": "2026-09-20"}]

        class LLM:
            def __init__(self, price):
                self.price = price

            def ask_json(self, *a, **k):
                return {"found": True, "price_krw": self.price, "deal_date": "2026-09-01", "source": 1}

        item = {"key": "eunma", "group": "home", "label": "은마 84㎡", "short": "은마아파트", "unit": "채",
                "fetch": "news", "query": "은마", "min_krw": 1_000_000_000, "max_krw": 10_000_000_000}
        fb = {"key": "seoul_apt", "short": "서울 아파트", "price_krw": 1, "as_of": "2026-08-10", "source": "x"}
        got, notes = fill_prices(Hub(), LLM(3_430_000_000), [item], "2026-09-29", fb)
        assert got[0]["price_krw"] == 3_430_000_000 and got[0]["as_of"] == "2026-09-01" and not notes
        for bad in (3_500_000_000, 500_000_000):  # 기사에 없는 숫자, 범위 밖
            got, notes = fill_prices(Hub(), LLM(bad), [item, dict(item, key="x")], "2026-09-29", fb)
            assert [g["key"] for g in got] == ["seoul_apt"] and len(notes) == 2


if __name__ == "__main__":
    unittest.main()
