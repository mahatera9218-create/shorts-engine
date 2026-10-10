"""도우미 버튼 실행이 실패하면 이유를 쉬운 말로 남긴다 (대표 지적 2026-10-10 "크레딧이 없어서 실패한 거면 알려줘야지").
run.log(실행 기록)에서 이유를 찾아 status/desk_error.yaml에 쓰고, 이슈 댓글용 한 줄을 출력한다. 도우미 맨 위에 빨간 띠로 뜬다.
python -m content.run_error run.log <명령> <키워드>   → 한 줄 이유 출력 + 파일 저장
python -m content.run_error --clear                 → 파일 지움 (클로드를 쓰는 실행이 성공했을 때)
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from market.common import ROOT

FILE = ROOT / "status" / "desk_error.yaml"
REASONS = [  # (찾을 말, 쉬운 설명) — 위에서부터 먼저 맞는 것
    (r"credit balance is too low", "클로드(Anthropic) 크레딧이 바닥났어요. console.anthropic.com → Billing에서 충전해 주세요. 충전 뒤 같은 버튼을 다시 누르면 돼요."),
    (r"insufficient_quota|exceeded your current quota", "OpenAI 크레딧이 바닥났어요. platform.openai.com → Billing에서 충전해 주세요."),
    (r"api\.x\.ai.*\b4\d\d\b|grok.*(credit|balance|quota)", "Grok(xAI) 크레딧이나 한도 문제예요. console.x.ai에서 잔액을 확인해 주세요."),
    (r"rate_limit|429|overloaded|529", "AI 서버가 잠깐 붐볐어요. 10분쯤 뒤 같은 버튼을 다시 눌러 주세요."),
    (r"월 상한|MONTH_CAP|이번 달 비용", "이번 달 비용 상한에 닿아 멈췄어요. 상한을 올릴지 정해 주세요."),
    (r"authentication_error|invalid x-api-key|401", "API 키가 맞지 않아요. GitHub Secrets의 키를 확인해야 해요 (Claude에게 알려 주세요)."),
]


def reason(log: str) -> str:
    for pat, msg in REASONS:
        if re.search(pat, log, re.I):
            return msg
    return "알 수 없는 오류로 멈췄어요. 이 화면을 Claude에게 알려 주세요."


def main() -> None:
    if sys.argv[1:2] == ["--clear"]:  # 어떤 명령이든 성공하면 지난 실패 띠를 지운다 (대표 지적 2026-10-10: 옛 에러가 남아 있음)
        FILE.unlink(missing_ok=True)
        return
    path, cmd, kw = (sys.argv[1:] + ["", "", ""])[:3]
    try:
        log = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        log = ""
    msg = reason(log)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(yaml.safe_dump({"at": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M"),
                                    "cmd": cmd, "kw": kw[:40], "reason": msg}, allow_unicode=True), encoding="utf-8")
    print(msg)


if __name__ == "__main__":
    main()
