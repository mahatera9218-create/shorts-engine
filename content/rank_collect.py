"""순위 '호응도' 주간 수집: Grok 웹검색으로 각 서비스의 최근 공개 반응을 0~5로 받아 JSON에 반영.

- 대상: web/content/rankings/*.json 중 criteria에 'buzz'(호응도)가 있는 것.
- Grok(content.econ_flow.grok, XAI_API_KEY) 사용. 실패·빈 응답이면 기존 값을 그대로 둔다.
- 호응도는 순위의 '한 입력'일 뿐이며(가중치 일부), 메인 순위는 공개 기준으로 매긴다.
- 지어내지 않도록 Grok에 '최근 공개 언급·평판 기준'으로만 요청한다.

사용: python -m content.rank_collect [--dry-run]
비밀 값은 넣지 않는다. 커밋·푸시는 워크플로에서 한다.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market.common import ROOT
from content import econ_flow

RANK_DIR = ROOT / "web" / "content" / "rankings"
KST = timezone(timedelta(hours=9))

ASK = (
    "너는 한국 '{cat}' 분야의 최근 1주일 공개 반응을 조사하는 분석가다.\n"
    "아래 서비스 각각의 '최근 호응도'를 0.0~5.0 점수로 매겨라. "
    "기준은 최근 공개된 이용자 반응·언급량·평판이며, 과장·추측 없이 공개 정보에 근거한다.\n"
    "설명 없이 JSON 하나로만 답한다: {{\"서비스슬러그\": 점수, ...}}\n"
    "서비스(슬러그=이름): {apps}"
)


def _parse_scores(text: str) -> dict:
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if not m:
        return {}
    try:
        raw = json.loads(m.group(0))
    except Exception:
        return {}
    out = {}
    for k, v in raw.items():
        try:
            out[str(k)] = max(0.0, min(5.0, round(float(v), 1)))
        except Exception:
            pass
    return out


def collect_file(path: Path, dry: bool = False) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    if not any(c.get("key") == "buzz" for c in d.get("criteria", [])):
        return
    apps = {a["slug"]: a["name"] for a in d["apps"]}
    prompt = ASK.format(
        cat=d.get("categoryName", ""),
        apps=", ".join(f"{s}={n}" for s, n in apps.items()),
    )
    raw = econ_flow.grok(prompt, days=7, web=True, turns=2)
    scores = _parse_scores(raw)
    if not scores:
        print(f"[{path.name}] 호응도 응답 없음 — 기존 값 유지")
        return
    changed = 0
    for a in d["apps"]:
        s = scores.get(a["slug"], scores.get(a["name"]))
        if isinstance(s, (int, float)):
            a["scores"]["buzz"] = float(s)
            changed += 1
    d["buzzUpdated"] = datetime.now(KST).strftime("%Y-%m-%d")
    if not dry:
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{path.name}] 호응도 {changed}개 갱신")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="순위 호응도 주간 수집(Grok)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not RANK_DIR.exists():
        print("순위 폴더 없음:", RANK_DIR)
        return 0
    for f in sorted(RANK_DIR.glob("*.json")):
        try:
            collect_file(f, dry=args.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"[{f.name}] 실패: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
