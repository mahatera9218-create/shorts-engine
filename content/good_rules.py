"""반응 좋은 글의 규칙 (config/good_rules.yaml) — 도우미 제목 칸 표시 + 제목 만들 때 참고 (대표 지시 2026-10-08)."""
from __future__ import annotations

from market.common import load_yaml


def rules(bid: str) -> dict:
    try:
        return (load_yaml("good_rules.yaml") or {}).get(bid) or {}
    except FileNotFoundError:
        return {}


def title_hint(bid: str) -> str:
    """제목 만들 때 덧붙일 참고. 규칙이 없으면 빈칸."""
    r = rules(bid)
    if not r.get("title"):
        return ""
    return ("\n\n[같은 분야 블로그에서 반응 좋은 글의 제목 규칙 — 후보 중 여러 개에 골고루 적용하되 사실과 맞을 때만]\n"
            + "\n".join(f"- {x}" for x in r["title"]))
