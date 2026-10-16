"""순위 데이터 검증: 공개(beta:false·index) 전에 반드시 통과해야 하는 게이트.

- 모든 순위 JSON(web/content/rankings/*.json)을 검사한다. 실패가 있으면 종료코드 1.
- 구조 검사(항상): 가중치 합 100, 점수 0~5, 점수 항목이 criteria와 일치, 링크 형식.
- 공개 게이트(beta:false 일 때만): status가 'verified', 모든 대상에 근거 sources(https) 1개 이상,
  평가 대기(pending) 대상 없음, 예시 데이터 아님. 하나라도 어기면 실패 → 예시·미검증 순위가 색인되는 걸 막는다.
- 베타(beta:true)는 구조만 통과하면 OK(색인 제외 상태).

사용: python -m content.rank_verify
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from market.common import ROOT

RANK_DIR = ROOT / "web" / "content" / "rankings"


def verify(d: dict, name: str = "") -> list[str]:
    errs: list[str] = []
    crit = d.get("criteria", [])
    keys = [c.get("key") for c in crit]
    if not crit:
        errs.append("criteria 없음")
    elif sum(c.get("weight", 0) for c in crit) != 100:
        errs.append(f"가중치 합이 100이 아님({sum(c.get('weight', 0) for c in crit)})")
    slugs = [a.get("slug") for a in d.get("apps", [])]
    if len(slugs) != len(set(slugs)):
        errs.append("대상 slug 중복")
    for a in d.get("apps", []):
        who = a.get("slug", "?")
        url = a.get("url", "#")
        if url != "#" and not url.startswith("https://"):
            errs.append(f"{who}: url은 https 또는 '#'")
        if a.get("pending"):
            continue
        sc = a.get("scores", {})
        for k, v in sc.items():
            if k not in keys:
                errs.append(f"{who}: 모르는 점수 항목 {k}")
            if not isinstance(v, (int, float)) or not 0 <= v <= 5:
                errs.append(f"{who}: {k} 점수는 0~5")
        miss = [k for k in keys if k not in sc]
        if miss:
            errs.append(f"{who}: 점수 빠짐 {miss}")
    if not d.get("beta", True):  # 공개 게이트
        if d.get("status") != "verified":
            errs.append("공개(beta:false)는 status='verified' 필요(예시·준비 중 데이터 공개 금지)")
        if not d.get("apps"):
            errs.append("공개 순위에 대상이 없음")
        for a in d.get("apps", []):
            if a.get("pending"):
                errs.append(f"{a.get('slug')}: 평가 대기 상태로 공개 불가")
            srcs = a.get("sources") or []
            if not srcs or not all(str(s).startswith("https://") for s in srcs):
                errs.append(f"{a.get('slug')}: 근거 sources(https) 1개 이상 필요")
    return errs


def main() -> int:
    bad = 0
    for f in sorted(RANK_DIR.glob("*.json")):
        errs = verify(json.loads(f.read_text(encoding="utf-8")), f.name)
        state = "OK" if not errs else "FAIL"
        print(f"[{state}] {f.name}")
        for e in errs:
            print(f"   - {e}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
