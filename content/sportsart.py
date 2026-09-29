"""종목 아이콘을 도형으로 직접 그린다 (사진·남의 그림 없음 → 저작권 걱정 없음).

2배 크기로 그린 뒤 줄여서 테두리를 매끄럽게 한다. 돌려주는 것은 투명 배경 RGBA 이미지.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

RED = (214, 40, 40)
INK = (25, 25, 30)


def _canvas(size: int):
    s = size * 2
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im), s


def _done(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.LANCZOS)


def baseball(size: int) -> Image.Image:
    im, d, s = _canvas(size)
    d.ellipse((0, 0, s - 1, s - 1), fill=(248, 246, 240), outline=(200, 196, 188), width=s // 60)
    r = s / 2
    for side in (-1, 1):  # 양쪽 실밥: 공 가장자리를 따라 휘는 곡선 + 짧은 바늘땀
        pts = []
        for t in range(-60, 61, 3):
            a = math.radians(t)
            x = r + side * r * (0.9 - 0.55 * math.cos(a))
            y = r + r * 0.85 * math.sin(a)
            pts.append((x, y))
        d.line(pts, fill=RED, width=s // 45, joint="curve")
        for (x0, y0), (x1, y1) in zip(pts[2::4], pts[3::4]):
            nx, ny = -(y1 - y0), x1 - x0
            n = math.hypot(nx, ny) or 1
            k = s * 0.03
            d.line((x0 - nx / n * k, y0 - ny / n * k, x0 + nx / n * k, y0 + ny / n * k), fill=RED, width=s // 90)
    return _done(im, size)


def soccer(size: int) -> Image.Image:
    im, d, s = _canvas(size)
    d.ellipse((0, 0, s - 1, s - 1), fill=(248, 248, 248), outline=(190, 190, 195), width=s // 60)
    r, c = s / 2, s / 2

    def pent(cx, cy, rad, rot):
        return [(cx + rad * math.cos(math.radians(rot + 72 * i)), cy + rad * math.sin(math.radians(rot + 72 * i)))
                for i in range(5)]

    center = pent(c, c, r * 0.3, -90)
    d.polygon(center, fill=INK)
    for i in range(5):  # 가운데 오각형에서 바깥 오각형으로 선을 잇고, 가장자리에 잘린 오각형
        a = math.radians(-90 + 72 * i)
        ox, oy = c + r * 0.78 * math.cos(a), c + r * 0.78 * math.sin(a)
        d.line((center[i], (c + r * 0.55 * math.cos(a), c + r * 0.55 * math.sin(a))), fill=INK, width=s // 70)
        d.polygon(pent(ox, oy, r * 0.22, -90 + 72 * i + 36), fill=INK)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
    im.putalpha(Image.composite(im.getchannel("A"), Image.new("L", (s, s), 0), mask))
    return _done(im, size)


def basketball(size: int) -> Image.Image:
    im, d, s = _canvas(size)
    d.ellipse((0, 0, s - 1, s - 1), fill=(232, 110, 30), outline=INK, width=s // 50)
    w = s // 55
    d.line((s / 2, 0, s / 2, s), fill=INK, width=w)
    d.line((0, s / 2, s, s / 2), fill=INK, width=w)
    d.arc((-s * 0.55, s * 0.08, s * 0.42, s * 0.92), -60, 60, fill=INK, width=w)
    d.arc((s * 0.58, s * 0.08, s * 1.55, s * 0.92), 120, 240, fill=INK, width=w)
    return _done(im, size)


def coin(size: int) -> Image.Image:
    im, d, s = _canvas(size)
    d.ellipse((0, 0, s - 1, s - 1), fill=(245, 190, 40), outline=(190, 140, 20), width=s // 30)
    d.ellipse((s * 0.12, s * 0.12, s * 0.88, s * 0.88), outline=(200, 150, 25), width=s // 60)
    return _done(im, size)


def icon(sport: str, size: int) -> Image.Image:
    sport = sport or ""
    if "축구" in sport:
        return soccer(size)
    if "농구" in sport:
        return basketball(size)
    if "야구" in sport or not sport:
        return baseball(size)
    return coin(size)
