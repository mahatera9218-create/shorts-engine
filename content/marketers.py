"""마케터 3명 (대표 결정 2026-10-01, config/marketers.yaml): 전략이 다른 글쓴이를 동시에 돌려 비교한다.

- turn(today): 오늘 블로그 발행 차례인 마케터 (날마다 1→2→3)
- players(pool, m): 그 마케터가 쓸 선수 (화제형 = 최근 뉴스 많은 선수, 체감형·비교형 = 나머지를 반씩 → 같은 날 선수가 겹치지 않게)
- themes(pool, m): 그 마케터의 테마 가중치
- baseball_marketer(today): 오늘 야구를 쓰는 마케터 (하루 야구 1편, 2026-10-02). sport_ok로 선수를 거른다.
"""
from __future__ import annotations

import hashlib
from datetime import date

from market.common import load_yaml


def cfg() -> dict:
    return load_yaml("marketers.yaml")


def ids(c: dict | None = None) -> list[int]:
    return sorted(int(k) for k in (c or cfg())["marketers"])


def info(m: int, c: dict | None = None) -> dict:
    return (c or cfg())["marketers"][m]


def label(m: int | None, c: dict | None = None) -> str:
    if not m:
        return ""
    x = info(m, c)
    return f"마케터 {m} · {x['name']}"


def turn(today: str, c: dict | None = None) -> int:
    c = c or cfg()
    ms = ids(c)
    days = (date.fromisoformat(today) - date.fromisoformat(str(c["rotation_start"]))).days
    return ms[days % len(ms)]


BASEBALL = {"kbo", "mlb"}  # players.yaml sport 키


def baseball_marketer(today: str, c: dict | None = None) -> int:
    """오늘 야구를 쓰는 마케터 (대표 결정 2026-10-02: 하루 3편 중 야구 1편). 블로그 차례(turn)와 엇갈려
    1→3→2로 돌아서, 블로그 ⭐ 글은 사흘에 한 번 야구가 되고 마케터마다 야구를 고르게 쓴다."""
    c = c or cfg()
    ms = ids(c)
    days = (date.fromisoformat(today) - date.fromisoformat(str(c["rotation_start"]))).days
    return ms[(2 * days) % len(ms)]


def sport_ok(sport: str, m: int, today: str, c: dict | None = None) -> bool:
    """이 마케터가 오늘 이 종목(players.yaml sport 키)을 써도 되나: 야구 차례면 야구만, 아니면 야구 빼고."""
    return (sport in BASEBALL) == (m == baseball_marketer(today, c))


def _half(name: str) -> int:
    return int(hashlib.sha1(name.encode()).hexdigest(), 16) % 2


def players(pool_players: list[dict], m: int, c: dict | None = None) -> list[dict]:
    """선수 나누기. pool_players에는 weighted_pool이 붙인 news(최근 기사 수)가 있어야 화제 선수를 가른다."""
    c = c or cfg()
    hot_ids = [k for k in ids(c) if info(k, c).get("players") == "hot"]
    rest_ids = [k for k in ids(c) if info(k, c).get("players") != "hot"]
    ranked = sorted((p for p in pool_players if p.get("news", 0) > 0 or p.get("trending")),
                    key=lambda p: (-p.get("news", 0), p["name"]))
    hot = ranked[:max(5, len(pool_players) // 3)] if hot_ids else []
    hot_names = {p["name"] for p in hot}
    rest = [p for p in pool_players if p["name"] not in hot_names]
    if m in hot_ids:
        return hot if len(hot) >= 3 else pool_players
    if len(rest_ids) < 2:
        return rest or pool_players
    part = [p for p in rest if _half(p["name"]) == rest_ids.index(m) % 2]
    return part if len(part) >= 6 else (rest or pool_players)


def themes(all_themes: dict, m: int, c: dict | None = None) -> dict:
    """그 마케터가 쓰는 테마만, 가중치를 바꿔서 (이름·방향은 players.yaml 그대로)."""
    w = info(m, c).get("themes") or {}
    return {k: {**all_themes[k], "weight": v} for k, v in w.items() if k in all_themes}
