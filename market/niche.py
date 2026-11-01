"""틈새 키워드 조사 (대표 2026-10-23). LLM 없이 순수 계산.

증시·부동산 씨앗 → 연관 키워드의 월 검색량(PC·모바일, 검색광고 API) + 블로그 문서수(API HUB)
→ 경쟁강도(문서수÷검색량)·틈새(검색량 많고 경쟁 낮을수록 높음)를 그룹별 표로 낸다.
금·환율은 고정이라 조사하지 않는다(config/niche_keywords.yaml).

사용법:
  python -m market.niche            # 실제 (GitHub Actions, Secrets 5개 필요)
  python -m market.niche --sample   # 예시 데이터로 표 모양만 확인 (키 불필요)

결과: reports/검색량/틈새-<날짜>.md
"""
from __future__ import annotations

import sys
from datetime import date

from .common import ROOT, load_yaml, missing_secrets


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def gather(tool, hub, seeds: list[str], cap: int, min_volume: int) -> list[dict]:
    """씨앗 → 연관 키워드(검색량) → 검색량 상위 cap개의 블로그 문서수까지 조사."""
    rows = []
    for batch in chunks(seeds, 5):          # 검색광고 씨앗은 한 번에 5개까지
        rows += tool.related(batch)
    # 키워드 중복 제거(검색량 큰 것 우선), 최소 검색량 필터
    best: dict[str, dict] = {}
    for r in rows:
        k = r["keyword"].replace(" ", "")
        if r["volume"] < min_volume:
            continue
        if k not in best or r["volume"] > best[k]["volume"]:
            best[k] = r
    top = sorted(best.values(), key=lambda r: -r["volume"])[:cap]
    out = []
    for r in top:
        docs = int(hub.blog(r["keyword"]).get("total", 0))   # 정확도순 전체 문서 수
        vol = max(r["volume"], 1)
        out.append({
            "keyword": r["keyword"],
            "pc": int(r["volume_pc"]),
            "mobile": int(r["volume_mobile"]),
            "volume": int(r["volume"]),
            "docs": docs,
            "comp": docs / vol,               # 경쟁강도 = 문서수 ÷ 검색량 (낮을수록 틈새)
            "niche": vol / max(docs, 1),       # 틈새 = 검색량 ÷ 문서수 (높을수록 좋음)
        })
    return sorted(out, key=lambda x: -x["niche"])


def table(rows: list[dict]) -> str:
    L = ["| 순위 | 키워드 | 검색량 PC | 검색량 모바일 | 합계 | 블로그 문서수 | 경쟁강도 | 틈새 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | {r['keyword']} | {r['pc']:,} | {r['mobile']:,} | {r['volume']:,} "
                 f"| {r['docs']:,} | {r['comp']:.2f} | {r['niche']:.2f} |")
    return "\n".join(L)


def main() -> int:
    sample = "--sample" in sys.argv
    cfg = load_yaml("niche_keywords.yaml")
    g = load_yaml("global.yaml")
    groups = {k: v for k, v in cfg.items() if k != "settings" and isinstance(v, list)}
    s = cfg.get("settings", {})
    cap, min_volume = int(s.get("per_group_cap", 40)), int(s.get("min_volume", 500))

    if sample:
        from .sample import FakeHub, FakeKeywordTool
        tool, hub = FakeKeywordTool(), FakeHub()
    else:
        missing = missing_secrets("naver_ad") + missing_secrets("naver_hub")
        if missing:
            print("키가 없습니다. GitHub Secrets에 넣어 주세요: " + ", ".join(missing))
            print("(검색광고: NAVER_AD_API_KEY·NAVER_AD_SECRET_KEY·NAVER_AD_CUSTOMER_ID / "
                  "API HUB: NCP_APIGW_API_KEY_ID·NCP_APIGW_API_KEY)")
            return 1
        from .naver_ad import KeywordTool
        from .naver_hub import ApiHub
        tool = KeywordTool(g["endpoints"]["naver_ad_base"])
        hub = ApiHub(g["endpoints"]["naver_hub"])

    today = date.today().isoformat()
    parts = [f"# 틈새 키워드 조사 · {today}", ""]
    if sample:
        parts.append("> ⚠️ 예시 데이터입니다. 실제 숫자가 아니니 판단에 쓰지 마세요.\n")
    parts.append("경쟁강도 = 블로그 문서수 ÷ 월 검색량 (낮을수록 틈새). 틈새 = 검색량 ÷ 문서수 (높을수록 노려볼 만함).\n")
    for name, seeds in groups.items():
        parts.append(f"## {name}")
        rows = gather(tool, hub, seeds, cap, min_volume)
        parts.append(table(rows) if rows else "_검색량 조건을 넘는 키워드가 없습니다._")
        parts.append("")

    out_dir = ROOT / "reports" / "검색량"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"틈새-{today}.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    print(f"결과 저장: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
