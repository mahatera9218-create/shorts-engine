"""순위 데이터 검증: 공개(beta:false·index) 전에 반드시 통과해야 하는 게이트.

- 모든 순위 JSON(web/content/rankings/*.json)을 검사한다. 실패가 있으면 종료코드 1.
- 구조 검사(항상): 점수 0~5(가중치·종합점수 없음), 점수 항목이 criteria와 일치, 링크 형식, 모든 점수에 근거(evidence: 자동/수동·라벨·확인일, 수동은 https 링크).
- 점수가 없는 항목은 허용('근거 확인 중'으로 표시). 근거 있는 점수가 3개 미만이면 화면에서 평가 대기로 처리한다.
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
    slugs = [a.get("slug") for a in d.get("apps", [])]
    if len(slugs) != len(set(slugs)):
        errs.append("대상 slug 중복")
    for a in d.get("apps", []):
        who = a.get("slug", "?")
        url = a.get("url", "#")
        if url != "#" and not url.startswith("https://"):
            errs.append(f"{who}: url은 https 또는 '#'")
        for f in a.get("facts", []):
            if not (f.get("label") and f.get("value") and f.get("checked")) or not str(f.get("url", "")).startswith("https://"):
                errs.append(f"{who}: facts는 label·value·checked와 https url 필요")
        if a.get("pending"):
            continue
        sc = a.get("scores", {})
        for k, v in sc.items():
            if k not in keys:
                errs.append(f"{who}: 모르는 점수 항목 {k}")
            if not isinstance(v, (int, float)) or not 0 <= v <= 5:
                errs.append(f"{who}: {k} 점수는 0~5")
        ev = a.get("evidence", {})
        for k in sc:
            e = ev.get(k)
            if not e:
                errs.append(f"{who}: {k} 점수에 근거(evidence) 없음")
                continue
            if e.get("type") not in ("auto", "manual") or not e.get("checked") or not e.get("label"):
                errs.append(f"{who}: {k} evidence에 type/label/checked 필요")
            if e.get("type") == "manual" and not str(e.get("url", "")).startswith("https://"):
                errs.append(f"{who}: {k} 직접 확인 근거는 https 링크 필요")
    if not d.get("beta", True):  # 공개 게이트
        if d.get("status") != "verified":
            errs.append("공개(beta:false)는 status='verified' 필요(예시·준비 중 데이터 공개 금지)")
        if not d.get("apps"):
            errs.append("공개 비교에 대상이 없음")
        if not any(a.get("scores") or a.get("facts") for a in d.get("apps", [])):
            errs.append("공개하려면 근거 있는 점수나 사실이 하나 이상 필요")
        for a in d.get("apps", []):
            if a.get("pending"):
                errs.append(f"{a.get('slug')}: 평가 대기 상태로 공개 불가")
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
