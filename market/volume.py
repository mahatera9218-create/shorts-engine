"""생활 물가 후보(동네 집값·차종)의 네이버 월간 검색량을 잰다 → 많이 검색하는 것만 가격표에 넣는다.

후보는 config/prices.yaml의 candidates. 검색광고 키워드 도구(공식 API)로 정확히 같은 키워드의 월간 검색량(PC+모바일)을 받는다.
결과: reports/검색량/가격후보-<날짜>.md (그룹별 순위). 가격은 여기서 정하지 않는다 (Claude가 공식 자료로 확인해 prices.yaml에).
사용법: python -m market.volume [--sample]
"""
from __future__ import annotations

import sys
from datetime import date

from .common import ROOT, load_yaml, missing_secrets

GROUPS = {"home": "집값 (지역·단지)", "car_kr": "국산차", "car_import": "수입차"}


def measure(tool, keywords: list[str]) -> dict[str, dict]:
    """키워드별 월간 검색량과, 그 키워드를 포함한 연관 검색어 중 가장 많이 찾는 것."""
    rows = tool.related(keywords)
    out = {}
    for k in keywords:
        key = k.replace(" ", "")
        exact = next((r for r in rows if r["keyword"].replace(" ", "") == key), None)
        near = sorted((r for r in rows if key in r["keyword"].replace(" ", "") and r["keyword"].replace(" ", "") != key),
                      key=lambda r: -r["volume"])[:2]
        out[k] = {"volume": exact["volume"] if exact else 0, "related": [(r["keyword"], r["volume"]) for r in near]}
    return out


def report(cands: dict, vols: dict[str, dict], sample: bool) -> str:
    L = [f"# 생활 물가 후보 검색량 · {date.today().isoformat()}", ""]
    if sample:
        L += ["> ⚠️ 예시 데이터입니다. 실제 검색량이 아닙니다.", ""]
    L += ["네이버 검색광고 키워드 도구의 월간 검색량(PC+모바일). 많이 검색하는 순. 위쪽부터 가격표에 넣습니다.", ""]
    for g, title in GROUPS.items():
        items = sorted(cands.get(g, []), key=lambda k: -vols.get(k, {}).get("volume", 0))
        L += [f"## {title}", "", "| 순위 | 키워드 | 월 검색량 | 함께 많이 찾는 말 |", "| --- | --- | --- | --- |"]
        for i, k in enumerate(items, 1):
            v = vols.get(k, {})
            rel = ", ".join(f"{a} {int(b):,}" for a, b in v.get("related", []))
            L.append(f"| {i} | {k} | {int(v.get('volume', 0)):,} | {rel} |")
        L.append("")
    return "\n".join(L)


def main() -> None:
    sample = "--sample" in sys.argv
    cands = load_yaml("prices.yaml").get("candidates", {})
    keywords = [k for g in GROUPS for k in cands.get(g, [])]
    if sample:
        from .sample import FakeKeywordTool
        tool = FakeKeywordTool()
    else:
        miss = missing_secrets("naver_ad")
        if miss:
            print(f"키가 없어 실행하지 않았습니다: {', '.join(miss)}")
            return
        from .naver_ad import KeywordTool
        tool = KeywordTool(load_yaml("global.yaml")["endpoints"]["naver_ad_base"])
    text = report(cands, measure(tool, keywords), sample)
    out = ROOT / "reports" / "검색량" / f"가격후보-{date.today().isoformat()}{'-예시' if sample else ''}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
