"""대표가 '[선수] <이름>' 이슈에 연봉·주급을 댓글로 달면 확인 연봉표(salaries.yaml)에 넣는다 (대표 결정 2026-10-03).

지정 글쓰기가 '올해 연봉이 뉴스에 없음'으로 실패했을 때, 대표가 그 선수 연봉을 알려 주면
바로 연봉표에 추가하고 다시 쓰게 하는 통로다. 대표가 준 값은 공식 발표라고 볼 수 없어
모두 '추정치(공식 발표 아님)'로 표시한다 — 틀려도 거짓이 아니게.

사용: python -m content.salarycomment --title "[선수] 엄지성" --body-file issue_body.txt --comment-file comment.txt
GITHUB_OUTPUT에 name/event/team/added를 적어 워크플로가 다시 쓰기로 넘긴다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from market.common import ROOT
from .designate import parse

# 통화: 말·기호 → (코드, 범위 하한·상한은 autopost.FX와 맞춘다)
CURRENCY = [
    ("USD", ("달러", "$", "usd")),
    ("EUR", ("유로", "€", "eur")),
    ("GBP", ("파운드", "£", "gbp")),
    ("KRW", ("원", "krw")),
]
UNIT = {"억": 10**8, "천만": 10**7, "백만": 10**6, "만": 10**4, "천": 10**3}
# 주급·월급이면 연봉으로 환산한다 (주 52주, 월 12개월)
PERIOD = [("주급", 52, "주급"), ("주당", 52, "주급"), ("월급", 12, "월급"), ("월봉", 12, "월급")]


def _currency(text: str) -> str:
    low = text.lower()
    for code, words in CURRENCY:
        if any(w in text or w in low for w in words):
            return code
    return "KRW"


def _amount(text: str) -> float | None:
    """'2천만', '1억 2천만', '26만', '5천', '5000' → 숫자. 못 읽으면 None."""
    total = 0.0
    found = False
    # 단위가 붙은 수 (억·천만·백만·만·천)
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(천만|백만|억|만|천)", text):
        total += float(m.group(1).replace(",", "")) * UNIT[m.group(2)]
        found = True
    if found:
        return total
    # 단위 없는 맨 숫자 (예: '5000파운드', '연봉 260000') — 가장 큰 수 하나
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    nums = [n for n in nums if n >= 100]  # 52·12 같은 환산 계수·연도는 거른다
    return max(nums) if nums else None


def _period(text: str) -> tuple[int, str]:
    for word, mult, label in PERIOD:
        if word in text:
            return mult, label
    return 1, "연봉"


TEAM_IN_COMMENT = re.compile(r"소속:\s*(.+?)\s*$", re.M)


def _team_from_comment(comment: str) -> str:
    """댓글에서 소속·종목을 뽑는다 (원래 이슈에 소속이 없을 때). '소속: X' 줄 또는 종목어."""
    m = TEAM_IN_COMMENT.search(comment)
    if m:
        t = m.group(1).strip()
        return t if len(t) <= 20 and not re.search(r"[\n\r\t<>|&;`$]", t) else ""
    from .autopost import SPORT_WORDS
    low = comment.replace(" ", "").lower()
    for ws in SPORT_WORDS.values():
        for w in ws:
            if w in low:
                return w
    return ""


def read_comment(title: str, body: str, comment: str, today: str) -> tuple[str, str, str, dict | None, str]:
    """(이름, 사건, 소속, 연봉표에 넣을 값 또는 None, 안내 메모)."""
    name, event, team = parse(title, body)
    if not name:
        return "", "", "", None, "선수 이름을 못 읽었어요."
    team = team or _team_from_comment(comment)
    amount = _amount(comment)
    if amount is None:
        return name, event, team, None, "금액을 못 읽었어요. 예: '연봉 5억' 또는 '주급 2천만원'처럼 적어 주세요."
    cur = _currency(comment)
    mult, plabel = _period(comment)
    yearly = round(amount * mult)
    note_period = f"{plabel} {int(amount):,}{'원' if cur == 'KRW' else ' ' + cur} 기준 연 환산" if mult != 1 else ""
    entry = {
        "amount": yearly,
        "currency": cur,
        "basis": f"추정치(공식 발표 아님), 대표 제공" + (f" ({note_period})" if note_period else ""),
        "as_of": today,
        "source": "대표 제공",
        "estimate": True,
    }
    return name, event, team, entry, ""


HEADER = (
    "# 확인된 올해 연봉 (대표 결정 2026-09-30): 뉴스 요약문에 올해 연봉 1년치가 없으면 여기 값을 쓴다.\n"
    "# 공식 발표·보도로 확인한 값만, 출처·기준일과 함께. 계약 총액을 연수로 나눈 값·추측 금지.\n"
    "# 뉴스에서 연봉이 뽑히면 뉴스 값이 우선이고, 여기 값과 다르면 발행 패키지에 차이가 표시된다.\n"
    "# 대표가 이슈에 댓글로 알려 준 값은 estimate: true (추정치)로 넣는다 (content/salarycomment.py, 2026-10-03).\n"
    "# currency: KRW | USD | EUR | GBP (외화는 그날 환율로 원화 환산). 시즌이 바뀌면 새로 확인해 고친다.\n"
)


def add_to_table(name: str, entry: dict) -> None:
    """salaries.yaml에 선수 연봉을 넣는다 (이미 있으면 덮어쓰기). 머리말은 지키고 players만 다시 쓴다."""
    f = ROOT / "config" / "salaries.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {"season": int(datetime.now().year), "players": {}}
    data.setdefault("players", {})[name] = entry
    out = HEADER + f"season: {data.get('season')}\n" + yaml.safe_dump(
        {"players": data["players"]}, allow_unicode=True, sort_keys=True, default_flow_style=False)
    f.write_text(out, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file")
    ap.add_argument("--comment-file", required=True)
    a = ap.parse_args()
    body = ""
    if a.body_file and os.path.exists(a.body_file):
        body = open(a.body_file, encoding="utf-8").read()
    comment = open(a.comment_file, encoding="utf-8").read() if os.path.exists(a.comment_file) else ""
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    name, event, team, entry, memo = read_comment(a.title, body, comment, today)
    added = ""
    if entry:
        add_to_table(name, entry)
        added = "1"
        print(f"연봉표에 넣었어요: {name} = {entry['amount']:,} {entry['currency']} (추정) · {entry['basis']}")
    else:
        print(memo)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"name={name}\nevent={event}\nteam={team}\nadded={added}\nmemo={memo}\n")
    sys.exit(0 if entry else 1)


if __name__ == "__main__":
    main()
