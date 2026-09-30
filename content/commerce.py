"""쇼핑커넥트 상품군 (대표 결정 2026-09-30, config/commerce.yaml): 글의 테마·비교 물건 → 붙일 상품군.

가입 전(active: false)에는 계산만 하고 도우미에 보이지 않는다. 가입 뒤 상품을 채우면 도우미 글 화면에 상품군·상품·고지 문구가 나온다.
"""
from __future__ import annotations

from market.common import load_yaml


def category(d: dict) -> str | None:
    """글 데이터(data.yaml) → 상품군 key (없으면 None)."""
    th = d.get("theme", "receipt")
    if th == "tax":
        return None
    if th in ("life", "place"):
        group = next((p.get("group", "") for p in d.get("prices", [])), "")
        return "car" if group.startswith("car") else "home" if group == "home" or th == "place" else None
    if th == "trip":
        return "travel"
    if th == "jersey":
        return "fan"
    return "sport"


def info(d: dict) -> dict | None:
    """도우미에 보여 줄 상품군 정보 (가입 전이면 None)."""
    cfg = load_yaml("commerce.yaml")
    key = category(d)
    if not cfg.get("active") or not key:
        return None
    c = cfg["categories"][key]
    return {"key": key, "name": c["name"], "products": c.get("products") or [], "disclosure": cfg["disclosure"]}
