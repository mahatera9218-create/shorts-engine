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

    def test_clip_caption_and_scenes(self):
        import tempfile
        from pathlib import Path
        from content import clip
        st = {"hook": {"tag": "t", "name": "오타니", "label": "홈런 1개", "big": "9,045만원"},
              "quiz": {"lines": ["a", "b"], "options": ["1", "2", "3"], "answer": 1},
              "answer": {"big": "3,167만원", "line": "x"},
              "table": {"title": "t", "header": ["기준", "1번에"], "rows": [["경기", "1"]] * 4, "hot": [0]}, "wage": None}
        sc = clip.scenes(st, None)
        assert [type(s).__name__ for s in sc] == ["Hook", "Quiz", "Answer", "Table", "Outro"]
        assert 15 <= sum(s.dur for s in sc) <= 25  # 15~25초
        with tempfile.TemporaryDirectory() as t:
            p = {"titles": [{"text": "오타니 1홈런에 9,045만원", "type": "숫자형", "best": True}], "tags": ["오타니", "연봉"]}
            text = clip.caption(Path(t), p)
            assert text.startswith("오타니 1홈런에 9,045만원") and "#오타니 #연봉" in text
    def test_jersey_spec(self):
        from content import jersey
        o = jersey.spec("오타니 쇼헤이")
        assert o["number"] == 17 and o["name"] == "OHTANI" and o["base"] and o["stripes"] == "none"
        assert jersey.spec("오타니") == o  # 짧은 이름도
        assert jersey.spec("임성재") is None and jersey.spec("없는선수") is None  # 골프·풀 밖은 등판 없음
        assert jersey.spec("애런 저지")["stripes"] == "pin"

    def test_mark_title_and_desk_lists(self):
        import tempfile
        from pathlib import Path
        from content import desk, mark
        folder = "2026-09-29-오타니-영수증"
        old_posts = mark.POSTS
        with tempfile.TemporaryDirectory() as t:
            mark.POSTS = Path(t)
            (mark.POSTS / folder).mkdir()
            (mark.POSTS / folder / "post.md").write_text("# x", encoding="utf-8")
            try:
                assert mark.parse_title(f"[발행완료] {folder}") == ("used", folder)
                assert mark.parse_title(f"[다시뽑기] {folder}") == ("rejected", folder)
                for bad in (f"발행완료 {folder}", "[발행완료] ../../etc", "[발행완료] 2026-01-01-없는글", f"[삭제] {folder}"):
                    assert mark.parse_title(bad) is None
            finally:
                mark.POSTS = old_posts
        base = {"titles": [], "ok": True, "date": "2026-09-29"}
        posts = [{**base, "folder": "2026-09-29-a", "status": {}},
                 {**base, "folder": "2026-09-30-b", "status": {"status": "used", "at": "2026-09-30 09:00"}},
                 {**base, "folder": "2026-10-01-c", "status": {"status": "rejected"}}]
        h = desk.index(posts)
        assert "2026-09-29-a" in h and "발행한 글" in h and "2026-10-01-c" not in h
        assert h.index("2026-09-29-a") < h.index("발행한 글") < h.index("2026-09-30-b")

    def test_clip_question_checked(self):
        from content.autopost import check_post
        sheet = "1안타당: 2억 32만원"
        p = {"body": "1안타에 2억.", "recommended": 1, "titles": [{"text": "1안타에 2억", "type": "숫자형"}] * 5,
             "clip_caption": "1안타에 2억?", "clip_question": "다음은 누구 몸값이 궁금한가요 댓글로 알려주세요"}
        probs = check_post(p, sheet)
        assert any("클립 질문" in x and "18자" in x for x in probs)
        assert any("클립 설명에 숫자표에 없는 숫자" in x for x in check_post({**p, "clip_caption": "75억?"}, sheet))

    def test_teaser_and_news_weight(self):
        from content.autopost import TEASER, weighted_pool
        assert TEASER.search("다음 영수증은 류현진이에요") and not TEASER.search("누구 연봉을 쪼개 볼까요?")

        class Hub:
            def news(self, q, display=100):
                n = 30 if q == "A" else 0
                return [{"date": "2026-09-29"}] * n + [{"date": "2026-09-01"}] * 5

        pool = {"players": [{"name": "A", "weight": 1}, {"name": "B", "weight": 2}]}
        got, why = weighted_pool(Hub(), pool, "2026-09-30")
        w = {p["name"]: p["weight"] for p in got["players"]}
        assert w == {"A": 3.0, "B": 2} and "A 기사 30건" in why

    def test_cross_is_different_sport_and_known_salary(self):
        from content import themes
        from content.autopost import with_known_salary
        pool = {"sports": {"kbo": {"sport": "야구"}, "mlb": {"sport": "야구"}, "soccer": {"sport": "축구"}},
                "themes": {"cross": {"weight": 1}},
                "players": [{"name": "K", "sport": "kbo"}, {"name": "M", "sport": "mlb"}, {"name": "S", "sport": "soccer"}]}
        for seed in range(20):
            for pl in themes.plans(pool, set(), str(seed), n=3, theme="cross"):
                sports = {pool["sports"][p["sport"]]["sport"] for p in pl["players"]}
                assert len(sports) == 2
        known = {"amount": 250000000, "currency": "KRW", "basis": "b", "as_of": "2026-01-15", "source": "u", "season": 2026}
        facts, ex = with_known_salary({"games": {"value": 30}}, {"salary_currency": "KRW", "season": 2026}, known)
        assert facts["salary"]["value"] == 250000000 and facts["salary"]["rule"] == "확인 연봉표"
        facts, _ = with_known_salary({"salary": {"value": 300000000, "differs": None}}, {"salary_currency": "KRW"}, known)
        assert facts["salary"]["value"] == 300000000 and facts["salary"]["differs"] == [250000000, 300000000]

    def test_tax_theme_and_long_run(self):
        import yaml
        from content import themes
        from content.receipt import won
        tax = yaml.safe_load(open("config/tax.yaml", encoding="utf-8"))
        assert round(themes.income_tax(2_100_000_000, tax["brackets"])) == 879_060_000  # 21억: 45% - 6,594만
        assert round(themes.income_tax(10_000_000, tax["brackets"])) == 600_000
        d = {"player": "류현진", "season": 2026, "salary_krw": 2_100_000_000,
             "units": [{"key": "games", "label": "1경기", "count": 25}]}
        n = themes.compute_tax(d, tax)
        assert round(n["withhold"]) == 69_300_000 and n["tax_max"] < d["salary_krw"] * 0.5
        assert themes.ro("유니폼") == "유니폼으로" and themes.ro("아반떼") == "아반떼로" and themes.ro("서울") == "서울로"
        assert won(159000) == "159,000원" and won(29_999_999) == "2,999만원"  # 버림
        pool = {"sports": {"kbo": {"sport": "야구"}}, "themes": {"tax": {"weight": 1}},
                "players": [{"name": "K", "sport": "kbo"}, {"name": "M", "sport": "mlb"}],
                "_eligible": {"tax": {"K"}}}
        got = themes.plans(pool, set(), "s", n=3, theme="tax")
        assert got and all(p["players"][0]["name"] == "K" for p in got)
        assert not themes.plans(pool, set(), "s", n=3, theme="tax", used={("tax", ("K",))})

    def test_places_and_items(self):
        import yaml
        from content.autopost import eligible, place_item, places_for
        pool = yaml.safe_load(open("config/players.yaml", encoding="utf-8"))
        ryu = next(p for p in pool["players"] if p["name"] == "류현진")
        pl = places_for(pool, ryu)
        assert pl[0]["city"] == "대전" and "소속팀" in pl[0]["relation"] and pl[0]["domestic"]
        assert {"인천", "로스앤젤레스", "토론토"} <= {x["city"] for x in pl}
        assert not next(x for x in pl if x["city"] == "토론토")["domestic"]
        el = eligible(pool)
        assert "류현진" in el["place"] and "류현진" in el["trip"]
        apt = place_item({"city": "광주", "domestic": True}, "place")
        assert apt["query"].startswith("광주광역시") and apt["kind"] == "region_avg" and apt["unit"] == "채"
        trip = place_item({"city": "토론토", "domestic": False}, "trip")
        assert trip["price_krw"] == 1423000 and trip["short"] == "토론토 여행"


if __name__ == "__main__":
    unittest.main()
