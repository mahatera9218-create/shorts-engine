"""유니폼 등판 그림 (대표 결정 2026-09-30): 선수 사진 대신 코드로 그린 등판 = 영문 이름 + 등번호.

- 선수 얼굴·실제 사진은 쓰지 않는다 (초상권·퍼블리시티권). 구단 로고·실제 유니폼 디자인도 쓰지 않는다 (상표).
- 색은 "느낌만" 비슷하게: 바탕색 계열, 번호색, 테두리색, 줄무늬 유무 (config/players.yaml의 teams).
- 등번호는 보도로 확인한 값만 (players.yaml number). 없으면 번호 없이 이름만. 골프는 등판을 그리지 않는다.
"""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from market.common import load_yaml
from .brand import fit

DEFAULT = {"base": [245, 245, 248], "num": [25, 40, 85], "trim": [25, 40, 85], "stripes": "none"}

# 등판 모양 (0~1 좌표): 목 → 어깨 → 소매 → 겨드랑이 → 밑단
SHAPE = [(0.36, 0.07), (0.14, 0.15), (0.02, 0.40), (0.18, 0.47), (0.23, 0.36), (0.23, 0.97),
         (0.77, 0.97), (0.77, 0.36), (0.82, 0.47), (0.98, 0.40), (0.86, 0.15), (0.64, 0.07)]


@lru_cache(maxsize=1)
def _pool() -> dict:
    return load_yaml("players.yaml")


def spec(player: str) -> dict | None:
    """선수 이름(긴 이름) → 등판 정보. 골프·풀에 없는 선수는 None."""
    pool = _pool()
    p = next((x for x in pool["players"] if x["name"] == player or x.get("short") == player), None)
    if not p or p["sport"] == "golf":
        return None
    colors = {**DEFAULT, **(pool.get("teams", {}).get(p.get("team", ""), {}))}
    return {"name": p.get("en", ""), "number": p.get("number"), **colors}


def draw(sp: dict, size: int = 600) -> Image.Image:
    """등판 한 장 (투명 배경, 그림자 포함). 2배로 그려 줄여서 가장자리를 부드럽게."""
    S = size * 2
    base, num, trim = tuple(sp["base"]), tuple(sp["num"]), tuple(sp["trim"])
    pts = [(x * S, y * S) for x, y in SHAPE]
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    body = Image.new("RGBA", (S, S), base + (255,))
    d = ImageDraw.Draw(body)
    if sp.get("stripes") == "pin":
        for x in range(0, S, S // 26):
            d.line((x, 0, x, S), fill=num + (255,), width=max(2, S // 220))
    elif sp.get("stripes") == "wide":
        w = S // 9
        for x in range(0, S, w * 2):
            d.rectangle((x, 0, x + w, S), fill=(250, 250, 250, 255))
    # 옆구리 음영 (입체감)
    shade = Image.linear_gradient("L").rotate(90).resize((S, S))
    edge = Image.eval(shade, lambda v: int(55 * (abs(v - 128) / 128) ** 2))
    body = Image.composite(Image.new("RGBA", (S, S), (0, 0, 0, 255)), body, edge)
    d = ImageDraw.Draw(body)
    # 목둘레·소매 끝단 (테두리색)
    d.chord((0.36 * S, -0.02 * S, 0.64 * S, 0.16 * S), 0, 180, fill=trim + (255,))
    for a, b in (((0.02, 0.40), (0.18, 0.47)), ((0.98, 0.40), (0.82, 0.47))):
        d.line((a[0] * S, a[1] * S, b[0] * S, b[1] * S), fill=trim + (255,), width=S // 28)
    if sp.get("name"):
        f = fit(d, sp["name"], "display", int(S * 0.11), S * 0.46)
        d.text((S / 2, S * 0.25), sp["name"], font=f, fill=num + (255,), anchor="mm")
    if sp.get("number") is not None:
        n = str(sp["number"])
        f = fit(d, n, "display", int(S * 0.42), S * 0.5)
        d.text((S / 2, S * 0.60), n, font=f, fill=num + (255,), anchor="mm", stroke_width=S // 70,
               stroke_fill=trim + (255,) if trim != num else (255, 255, 255, 255))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(body, (0, 0), mask)
    ImageDraw.Draw(out).polygon(pts, outline=trim + (255,), width=S // 90)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", (S, S), (0, 0, 0, 150)), (S // 40, S // 30), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(S // 60))
    shadow.alpha_composite(out)
    return shadow.resize((size, size), Image.LANCZOS)


def for_players(names: list[str], size: int = 600) -> list[Image.Image]:
    return [draw(s, size) for s in (spec(n) for n in names) if s]
