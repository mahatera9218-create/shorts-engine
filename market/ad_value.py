"""광고 묶음별 광고주 수요 측정: 우리 글이 부를 수 있는 광고가 얼마짜리인가 (config/ad_keywords.yaml).

애드포스트는 문맥 광고라 글의 주제·단어가 붙는 광고를 정한다. 광고주가 검색광고에 쓰는 돈이 그 수요의 대략값이다.
- 월간 검색량·경쟁도·노출 광고 수: 검색광고 키워드 도구 (공식 API)
- 중간 입찰가(모바일, 최근 한 달): 검색광고 estimate API (공식 API) = 클릭 단가의 대략값
결과: reports/광고/광고단가-<날짜>.md. 애드포스트 단가 그 자체는 아니다 (가정 검증은 실제 수익과 비교, 설계서 0.6).
사용법: python -m market.ad_value [--sample]
"""
from __future__ import annotations

import statistics
import sys
from datetime import date

from .common import ROOT, load_yaml, missing_secrets


def measure(tool, groups: dict) -> list[dict]:
    out = []
    for key, g in groups.items():
        kws = g["keywords"]
        rows = {r["keyword"].replace(" ", ""): r for r in tool.related(kws)}
        try:
            bids = tool.median_bid(kws)
        except Exception as e:  # 입찰가 API가 안 되면 검색량·경쟁도만
            bids, err = {}, f"{type(e).__name__}: {str(e)[:120]}"
        else:
            err = ""
        items = []
        for k in kws:
            r = rows.get(k.replace(" ", ""), {})
            items.append({"keyword": k, "volume": r.get("volume", 0), "competition": r.get("competition", "-"),
                          "ad_depth": r.get("ad_depth", 0), "bid": bids.get(k.replace(" ", ""))})
        got = [i["bid"] for i in items if i["bid"]]
        out.append({"key": key, "name": g["name"], "fit": g.get("fit", ""), "items": items, "error": err,
                    "median_bid": statistics.median(got) if got else None,
                    "volume": sum(i["volume"] for i in items)})
    return out


def report(res: list[dict], sample: bool) -> str:
    L = [f"# 광고 묶음별 광고주 수요 · {date.today().isoformat()}", ""]
    if sample:
        L += ["> ⚠️ 예시 데이터입니다. 실제 값이 아닙니다.", ""]
    L += ["중간 입찰가 = 광고주가 검색광고 클릭 1번에 내는 돈의 대략값(모바일, 최근 한 달). 애드포스트 단가 자체는 아니지만,",
          "이 값이 높은 주제의 글일수록 비싼 광고가 붙을 가능성이 크다는 가정으로 본다 (실제 수익과 비교해 검증).", "",
          "## 한눈에 (중간 입찰가 높은 순)", "", "| 광고 묶음 | 우리 글과 맞는가 | 중간 입찰가 | 검색량 합 |", "| --- | --- | --- | --- |"]
    for g in sorted(res, key=lambda g: -(g["median_bid"] or 0)):
        bid = f"{int(g['median_bid']):,}원" if g["median_bid"] else "측정 안 됨"
        L.append(f"| {g['name']} | {g['fit']} | {bid} | {int(g['volume']):,} |")
    for g in res:
        L += ["", f"## {g['name']}", "", "| 키워드 | 월 검색량 | 경쟁도 | 노출 광고 수 | 중간 입찰가 |", "| --- | --- | --- | --- | --- |"]
        for i in g["items"]:
            bid = f"{int(i['bid']):,}원" if i["bid"] else "-"
            L.append(f"| {i['keyword']} | {int(i['volume']):,} | {i['competition']} | {i['ad_depth']:.0f} | {bid} |")
        if g["error"]:
            L += ["", f"입찰가 조회 실패: {g['error']}"]
    return "\n".join(L) + "\n"


def main() -> None:
    sample = "--sample" in sys.argv
    groups = load_yaml("ad_keywords.yaml")["groups"]
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
    text = report(measure(tool, groups), sample)
    out = ROOT / "reports" / "광고" / f"광고단가-{date.today().isoformat()}{'-예시' if sample else ''}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
