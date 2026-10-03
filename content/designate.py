"""대표가 도우미에서 '이 선수로 지금 쓰기'로 연 이슈를 파싱한다 (대표 결정 2026-10-03).

제목 "[선수] <이름>", 본문에 "사건: <한 줄>"이 있으면 그 줄을 글 첫 문단 훅으로 쓴다.
GITHUB_OUTPUT에 name, event를 적어 워크플로가 자동 글쓰기(--topic/--event)로 넘긴다.
사용: python -m content.designate --title "[선수] 김도영" --body-file body.txt
"""
from __future__ import annotations

import argparse
import os
import re
import sys

TITLE = re.compile(r"^\[선수\]\s*(.+?)\s*$")
EVENT = re.compile(r"^사건:\s*(.+?)\s*$", re.M)
TEAM = re.compile(r"^소속:\s*(.+?)\s*$", re.M)
# 이슈 제목에 들어오면 안 되는 것 (셸·형식 안전): 선수 이름은 짧은 한 줄
BAD = re.compile(r"[\n\r\t<>|&;`$]")


def parse(title: str, body: str) -> tuple[str, str, str]:
    """(선수 이름, 사건 한 줄, 소속). 이름이 비었거나 이상하면 ('', '', '')."""
    m = TITLE.match(title.strip())
    if not m:
        return "", "", ""
    name = m.group(1).strip()
    if not name or len(name) > 20 or BAD.search(name):
        return "", "", ""
    ev = EVENT.search(body or "")
    event = ev.group(1).strip() if ev else ""
    if len(event) > 60 or BAD.search(event):
        event = ""
    tm = TEAM.search(body or "")
    team = tm.group(1).strip() if tm else ""
    if len(team) > 20 or BAD.search(team):
        team = ""
    return name, event, team


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", default=None)
    a = ap.parse_args()
    body = ""
    if a.body_file and os.path.exists(a.body_file):
        with open(a.body_file, encoding="utf-8") as f:
            body = f.read()
    name, event, team = parse(a.title, body)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"name={name}\n")
            f.write(f"event={event}\n")
            f.write(f"team={team}\n")
    print(f"선수: {name or '(형식 오류)'}" + (f" · 사건: {event}" if event else "") + (f" · 소속: {team}" if team else ""))
    sys.exit(0 if name else 1)


if __name__ == "__main__":
    main()
