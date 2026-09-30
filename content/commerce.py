"""쇼핑커넥트 상품군 (대표 결정 2026-09-30, config/commerce.yaml): 글의 테마·비교 물건 → 붙일 상품군과 검색어.

상품 목록이 너무 많아(모바일에서 정렬도 안 됨) 대표가 캡처하는 대신, 도우미가 글마다 검색어 하나를 준다.
대표는 발행할 때 브랜드 커넥트에서 그 검색어로 찾아 기준(pick)에 맞는 상품 1개를 붙인다.
"""
from __future__ import annotations

import hashlib

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


def keywords(key: str, d: dict, cfg: dict) -> list[str]:
    kw = cfg["categories"][key].get("keywords") or []
    if isinstance(kw, dict):  # 종목별 (sport: "야구 (메이저리그)" → 야구)
        kw = kw.get(str(d.get("sport", "야구")).split()[0], [])
    team = d.get("team") or (d.get("a") or {}).get("team", "")
    return [k.replace("{team}", team) for k in kw if team or "{team}" not in k]


def info(d: dict, seed: str = "") -> dict | None:
    """도우미에 보여 줄 상품군·오늘 검색어 (꺼져 있거나 상품군이 없으면 None)."""
    cfg = load_yaml("commerce.yaml")
    key = category(d)
    if not cfg.get("active") or not key:
        return None
    kws = keywords(key, d, cfg)
    pick = kws[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(kws)] if kws else ""
    c = cfg["categories"][key]
    return {"key": key, "name": c["name"], "products": c.get("products") or [], "keyword": pick, "others": kws,
            "pick": cfg.get("pick", ""), "disclosure": cfg["disclosure"]}
