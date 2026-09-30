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
        assert [type(s).__name__ for s in sc] == ["Hook", "Quiz", "Answer", "Reveal", "Table", "Outro"]
        assert 15 <= sum(s.dur for s in sc) <= 25  # 15~25초
        assert clip.tease("9,045만원") == "???" and clip.tease("모델Y 597대") == "모델Y ???대"  # 표지에서 답을 가린다
        assert clip.tease("2억원 vs 1억원") == "??? vs ???"
        with tempfile.TemporaryDirectory() as t:
            p = {"titles": [{"text": "오타니 1홈런에 9,045만원", "type": "숫자형", "best": True}], "tags": ["오타니", "연봉"]}
            text = clip.caption(Path(t), p)
            assert text.startswith("오타니 1홈런에 9,045만원") and "#오타니 #연봉" in text

    def test_tags_and_title_suffix(self):
        from content.autopost import base_tags, search_suffix
        from content.desk import clean_tags
        d = {"player": "이정후", "team": "샌프란시스코 자이언츠", "season": 2026, "sport": "야구 (메이저리그)", "theme": "life"}
        tags = clean_tags(base_tags(d) + ["테슬라"] * 3 + [f"t{i}" for i in range(20)])
        assert tags[:3] == ["이정후", "이정후연봉", "샌프란시스코자이언츠"] and len(tags) == 15
        assert search_suffix(d, "이정후 안타 하나 2억, 모델Y 몇 대?") == "(이정후 연봉 2026 · 샌프란시스코 자이언츠)"
        assert search_suffix(d, "이정후 연봉 2026 샌프란시스코 자이언츠") == ""
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
        w = {p["name"]: p["weight"] for p in got["players"] if p["name"] in ("A", "B")}  # 실제 화제 선수 파일은 무시
        assert w == {"A": 3.0, "B": 2}

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

    def test_trending_names_must_be_in_article(self):
        from content import trending
        assert trending.volume_factor(10_000) == 1 and trending.volume_factor(1_000_000) == 3
        assert trending.volume_factor(100) == 0.5 and trending.volume_factor(0) == 1

        class Hub:
            def news(self, q, display=30):
                return [{"title": "김도영 끝내기 홈런", "description": "KIA 김도영이 끝내기 홈런", "link": f"https://n/{q}",
                         "date": "2026-09-29"}]

        class LLM:
            def ask_json(self, *a, **k):
                return {"players": [
                    {"name": "김도영", "short": "김도영", "sport": "kbo", "team": "KIA 타이거즈", "why": "끝내기", "source": 1},
                    {"name": "없는선수", "short": "없는", "sport": "kbo", "team": "", "why": "지어냄", "source": 1}]}

        got = trending.find_trending(Hub(), LLM(), "2026-09-30")
        assert [p["name"] for p in got] == ["김도영"]

    def test_weekly_judge(self):
        from datetime import date
        from content import weekly
        names = {"life": "생활 물가"}
        m = {"posts": {f"2026-10-0{i}-x": {"published": f"2026-10-0{i}", "views_7d": 100} for i in range(1, 4)}}
        assert "판정할 글이 아직" in weekly.judge(m, date(2026, 10, 20), names)[0]
        assert "판정할 글이 아직 0편" in weekly.judge(m, date(2026, 10, 5), names)[0]  # 7일 안 지난 글은 빼고 센다

    def test_reset_drafts_keeps_published(self):
        import tempfile
        from pathlib import Path
        from content import autopost, mark
        old = (autopost.POSTS, mark.POSTS, autopost.write_index)
        with tempfile.TemporaryDirectory() as t:
            autopost.POSTS = mark.POSTS = Path(t)
            for name in ("2026-10-01-life-a", "2026-10-01-tax-b", "2026-10-02-life-c"):
                (Path(t) / name).mkdir()
                (Path(t) / name / "post.md").write_text("# x", encoding="utf-8")
            mark.mark("2026-10-01-life-a", "used")
            try:
                autopost.write_index = lambda: None
                gone = autopost.reset_drafts("2026-10-02")
            finally:
                autopost.POSTS, mark.POSTS, autopost.write_index = old
            assert gone == ["2026-10-01-tax-b"]
            assert (Path(t) / "2026-10-01-life-a").exists() and (Path(t) / "2026-10-02-life-c").exists()


if __name__ == "__main__":
    unittest.main()


class TestCleanTags(unittest.TestCase):
    def test_naver_tag_chars(self):
        from content.desk import clean_tags
        self.assertEqual(clean_tags(["김도영", "3.3%", "KIA 타이거즈", "연봉·세금", "#홈런왕", "김도영"]),
                         ["김도영", "KIA타이거즈", "연봉세금", "홈런왕"])


class TestTitlePair(unittest.TestCase):
    SHEET = ("제목용 짧은 이름: 이정후\n썸네일: 이정후 / 올해 연봉이면 / 테슬라 모델Y 597대 (추천 제목에는 이 숫자를 다시 쓰지 않는다)\n"
             "추천 제목 유형: 질문형 (코드가 날마다 돌린다)")

    def post(self, text, typ="질문형"):
        return {"titles": [{"text": text, "type": typ}], "recommended": 1}

    def test_pair_ok(self):
        from content.autopost import check_titles
        self.assertEqual(check_titles(self.post("이정후 안타 하나 2억, 모델Y 몇 대?"), self.SHEET), [])

    def test_off_pair_and_type(self):
        from content.autopost import check_titles
        got = check_titles(self.post("이정후 65승 97패 팀에서 받은 2억", "대비형"), self.SHEET)
        self.assertTrue(any("썸네일과 다른 이야기" in x for x in got))
        self.assertTrue(any("유형" in x for x in got))

    def test_repeat_number(self):
        from content.autopost import check_titles
        got = check_titles(self.post("이정후 모델Y 597대, 진짜일까?"), self.SHEET)
        self.assertTrue(any("되풀이" in x for x in got))

    def test_title_type_rotates(self):
        from content.autopost import title_type
        self.assertEqual(len({title_type("2026-10-01", i) for i in range(5)}), 5)


class TestPublished(unittest.TestCase):
    RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>
<item><title><![CDATA[이정후 안타 하나에 2억, 비싼가? (다듬음)]]></title>
<link>https://blog.naver.com/tenbillionsound/224000000001?fromRss=true&amp;trackingCode=rss</link>
<pubDate>Tue, 30 Sep 2026 13:00:00 +0900</pubDate></item></channel></rss>"""

    def test_items_and_match(self):
        import tempfile
        from pathlib import Path
        from content import published
        it = published.items(self.RSS)
        self.assertEqual(it[0]["url"], "https://blog.naver.com/tenbillionsound/224000000001")
        self.assertEqual(it[0]["at"], "2026-09-30 13:00")
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "2026-09-30-life-이정후"
            other = Path(d) / "2026-09-30-life-류현진"
            future = Path(d) / "2026-10-01-life-이정후"
            for f in (old, other, future):
                f.mkdir()
                (f / "data.yaml").write_text(f"player: {f.name.rsplit('-', 1)[1]}\n", encoding="utf-8")
            self.assertEqual(published.match(it[0], [old, other, future]), old)


class TestShortsScenes(unittest.TestCase):
    def test_youtube_variant_loops_back(self):
        from content import clip
        st = {"hook": {"tag": "t", "name": "n", "label": "l", "big": "b", "players": []},
              "quiz": {"lines": ["a", "b"], "options": ["1", "2", "3"], "answer": 0},
              "answer": {"big": "x", "line": "y"}, "table": {"title": "t", "head": ["a", "b"], "rows": [["1", "2"]]}}
        nav = clip.scenes(st, None, "q")
        yt = clip.scenes(st, None, "q", youtube=True)
        self.assertEqual(type(yt[-1]).__name__, "LoopBack")
        self.assertEqual(len(yt), len(nav) + 1)
        self.assertFalse(nav[-1].yt)
        self.assertTrue(yt[-2].yt)


class TestShortsABC(unittest.TestCase):
    def test_options_and_meta(self):
        from content import shorts
        table = shorts.salary_table(1350.0)
        b = shorts.options_b(table)
        c = shorts.options_c(table)
        self.assertTrue(b and c)
        self.assertTrue(all(x["krw"] for o in b for x in o["left"] + o["right"]))
        self.assertEqual(len({o["key"] for o in c}), len(c))
        m = shorts.meta_text({"kind": "C", "title": "2026 KBO 연봉 TOP5", "q": "1위 예상했나요?", "basis": "확인 연봉표",
                              "names": ["양의지"]})
        self.assertTrue(m.startswith("2026 KBO 연봉 TOP5\n"))
        self.assertIn("#shorts", m)
        self.assertEqual(shorts._josa("류현진", "이", "가"), "이")
        self.assertEqual(shorts._josa("커리", "이", "가"), "가")

    def test_no_fx_keeps_usd_out(self):
        from content import shorts
        table = shorts.salary_table(None)
        self.assertTrue(all(x["krw"] is None for x in table if x["usd"]))
        self.assertFalse(any(o["key"].startswith("C-nba") for o in shorts.options_c(table)))


class TestShortsStats(unittest.TestCase):
    def test_update_match_and_summary(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        import yaml
        from content import shorts_stats as ss
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            log = d / "log.yaml"
            log.write_text(yaml.safe_dump([{"date": "2026-09-30", "kind": "B", "key": "B-x", "title": "KBO 연봉 1위 vs NBA 연봉 1위"}],
                                          allow_unicode=True), encoding="utf-8")
            with mock.patch.object(ss, "OUT", d), mock.patch.object(ss, "STATS", d / "stats.yaml"), mock.patch.object(ss, "LOG", log):
                vids = [{"id": "v1", "title": "KBO 연봉 1위 vs NBA 연봉 1위", "published": "2026-09-30", "views": 100, "likes": 3, "comments": 1},
                        {"id": "v2", "title": "직접 올린 영상", "published": "2026-09-30", "views": 5, "likes": 0, "comments": 0}]
                ss.update({"subs": 10, "views": 105, "videos": 2}, vids, "2026-09-30")
                vids[0]["views"] = 900
                stats = ss.update({"subs": 25, "views": 905, "videos": 2}, vids, "2026-10-03")
                self.assertEqual(stats["videos"]["v1"]["kind"], "B")
                self.assertEqual(ss.views_at(stats["videos"]["v1"], 3), 900)
                self.assertIsNone(ss.views_at(stats["videos"]["v1"], 7))
                self.assertEqual(yaml.safe_load(log.read_text(encoding="utf-8"))[0]["video_id"], "v1")
                text = "\n".join(ss.summary(stats, "2026-10-03"))
                self.assertIn("구독자 **25**", text)
                self.assertIn("짝을 못 찾은 영상 1개", text)


class TestShortsStatsEmpty(unittest.TestCase):
    def test_no_uploads_yet(self):
        from market.common import ApiError
        from content import shorts_stats as ss

        class YT:
            def _call(self, kind, params):
                if kind == "channels":
                    return {"items": [{"statistics": {"subscriberCount": "3", "viewCount": "0", "videoCount": "0"},
                                       "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]}
                raise ApiError("GET playlistItems → HTTP 404: not found")

        ch, vids = ss.fetch(YT(), "@x")
        self.assertEqual((ch["subs"], vids), (3, []))


class TestProduce(unittest.TestCase):
    def test_license_filter(self):
        from content.playerphoto import OK_LICENSE
        for ok in ("CC BY-SA 4.0", "CC BY 2.0", "CC0", "Public domain"):
            self.assertTrue(OK_LICENSE.match(ok), ok)
        for bad in ("CC BY-NC 2.0", "CC BY-ND 4.0", "", "All rights reserved"):
            self.assertFalse(OK_LICENSE.match(bad), bad)

    def test_find_needs_sport_word(self):
        from unittest import mock
        from content import playerphoto as pp
        calls = []

        def fake(url, params):
            calls.append(params["action"])
            if params["action"] == "wbsearchentities":
                return {"search": [{"id": "Q1"}, {"id": "Q2"}]}
            if params["action"] == "wbgetentities":
                p18 = [{"mainsnak": {"datavalue": {"value": "X.jpg"}}}]
                return {"entities": {"Q1": {"descriptions": {"ko": {"value": "대한민국의 가수"}}, "claims": {"P18": p18}},
                                     "Q2": {"descriptions": {"ko": {"value": "대한민국의 야구 선수"}}, "claims": {"P18": p18}}}}
            return {"query": {"pages": {"1": {"imageinfo": [{"url": "u", "thumburl": "t", "descriptionurl": "d",
                                                              "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                                                                              "Artist": {"value": "<a>Kim</a>"}}}]}}}}
        with mock.patch.object(pp, "_get", fake):
            r = pp.find("이정후", "mlb")
        self.assertEqual((r["qid"], r["artist"], r["license"]), ("Q2", "Kim", "CC BY-SA 4.0"))

    def test_narrate_extends_scene(self):
        import subprocess, tempfile
        from pathlib import Path
        from unittest import mock
        from content import clip, produce
        exe = clip.ffmpeg()
        if not exe:
            self.skipTest("ffmpeg 없음")
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "a.wav"
            subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=4", "-ar", "44100", str(wav)], check=True)

            class S(clip.Scene):
                dur = 2.0
                say = "안녕"
            s = S()
            with mock.patch.object(produce, "tts", lambda text: wav):
                cues = produce.narrate([s], [s.say])
            self.assertGreater(s.dur, 4.0)
            self.assertEqual(len(cues), 1)
            out = produce.mix(exe, cues + [(produce.sfx(exe, "ding"), 1.0, 0.5)], s.dur, Path(d) / "m.wav")
            self.assertAlmostEqual(produce.wav_seconds(out), s.dur, delta=0.1)


class TestLifecycle(unittest.TestCase):
    def test_pending_discard_cleanup(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        import yaml
        from content import shorts
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in ("2026-10-01-A-류현진", "2026-10-01-B-x", "2026-09-29-C-preview-y"):
                (d / name).mkdir()
                (d / name / "video.mp4").write_bytes(b"0")
            log = [{"date": "2026-10-01", "kind": "A", "key": "A-류현진", "title": "t", "video_id": "v1"},
                   {"date": "2026-10-01", "kind": "B", "key": "B-x", "title": "u"}]
            (d / "log.yaml").write_text(yaml.safe_dump(log, allow_unicode=True), encoding="utf-8")
            with mock.patch.object(shorts, "OUT", d), mock.patch.object(shorts, "LOG", d / "log.yaml"):
                self.assertEqual(shorts.pending("A"), [])            # 올린 건 대기 아님
                self.assertEqual(shorts.pending("B"), ["2026-10-01-B-x"])
                gone = shorts.cleanup("2026-10-02")
                self.assertIn("2026-10-01-A-류현진", gone)           # 올린 건 폐기
                self.assertIn("2026-09-29-C-preview-y", gone)        # 지난 미리보기 폐기
                self.assertTrue((d / "2026-10-01-B-x").exists())    # 안 올린 건 남김
                shorts.discard("2026-10-01-B-x")
                self.assertEqual(shorts.pending("B"), [])
                self.assertTrue(yaml.safe_load((d / "log.yaml").read_text(encoding="utf-8"))[1]["discarded"])

    def test_no_data_memory(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from content import autopost
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(autopost, "NO_DATA", Path(d) / "s.yaml"):
                autopost.remember_no_data({"나성범": "올해 연봉 없음"}, "2026-10-01")
                self.assertEqual(autopost.no_data_players("2026-10-05"), ["나성범"])
                self.assertEqual(autopost.no_data_players("2026-10-09"), [])
