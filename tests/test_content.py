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


if __name__ == "__main__":
    unittest.main()
