"""계절 인기 상품 → 셀럽 조합 (대표 요청 2026-10-10 '주 독자 여성층, 계절성 반영, 이 계절 많이 찾는 상품+연예인').

1) 네이버 쇼핑인사이트(데이터랩, API HUB)로 패션의류·잡화 분야에서 상품 키워드들의 '지금 많이 찾는 정도'를 재 계절 인기 상품 상위를 뽑는다.
2) 결과를 blogs/fashion/flow/<날짜>/season.yaml에 저장하고, 패션 키워드 수집의 Grok 프롬프트에 '이 계절 상품을 착용한 화제 연예인 위주로'라고 넣는다(content/econ_flow.py).
→ 쇼핑 수요가 큰 아이템(계절성 자동 반영) + 실제 화제 연예인이 만나는 키워드가 나온다. 쇼핑 통로가 없거나 실패하면 조용히 건너뛴다.
"""
from __future__ import annotations

from datetime import datetime

from . import econ_flow as F


def rank() -> dict:
    """{상품: {level, rise}} 상위 → season.yaml 저장. 패션 블로그에서만."""
    from .econ_score import CFG, _hub
    cfg = F.load(CFG(), {}) or {}
    cats = cfg.get("shopping_products") or {}
    anchors = cfg.get("shopping_anchor") or {}
    if F.BLOG["id"] != "fashion" or not cats:
        return {}
    hub = _hub()
    if not hub:
        print("계절 상품: API HUB 키가 없어 건너뜀")
        return {}
    items: list[dict] = []
    for cat, products in cats.items():
        anchor = anchors.get(cat) or anchors.get(str(cat)) or (products[0] if products else "")
        try:
            r = hub.shopping_rank(str(cat), list(products), anchor)
        except Exception as e:  # noqa: BLE001
            print(f"쇼핑인사이트 실패(분야 {cat}): {str(e)[:120]}")
            continue
        for kw, v in r.items():
            items.append({"product": kw, "category": str(cat), "level": v["level"], "rise": v["rise"]})
    items.sort(key=lambda x: -x["level"])
    top = cfg.get("shopping_top", 10)
    out = {"date": F.today(), "updated": datetime.now(F.KST).strftime("%H:%M"), "items": items[:top]}
    path = F.FLOW / F.today() / "season.yaml"
    F.save(path, out)
    print(f"계절 인기 상품 {len(items[:top])}개 → {path}" + (f" (1위 {items[0]['product']})" if items else " (없음)"))
    return out


def top_products(n: int = 8) -> list[str]:
    """오늘 계절 인기 상품 상위 이름 (Grok 프롬프트 넣기용). 파일이 없으면 빈 목록."""
    s = F.load(F.FLOW / F.today() / "season.yaml", {}) or {}
    return [it["product"] for it in s.get("items", [])][:n]
