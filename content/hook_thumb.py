"""억선생의 경제판 썸네일 (대표 결정 2026-10-05: C 구성 위주, 색·위치만 바꿔 가며).

C 구성 = 한쪽은 그림(창고 그림을 잘라 씀), 다른 쪽은 단색 판 위에 굵은 고딕 훅 문구.
- 판 위치: 오른쪽/왼쪽 번갈아. 판 색: 화투 팔레트 5가지(홍·먹·솔잎·금·미색)를 돌려 쓰고, 바로 앞 글과 겹치지 않게.
- 문구: 2~4줄, 한 줄 4~8자. 강조(숫자 등) 한 덩어리만 다른 색. 붓글씨 안 씀(작게 보면 안 읽힘).
- 구석에 '억' 낙관. 글자는 코드로 얹어 늘 또렷하고 정확(썸네일 0원, 그림은 창고).
사용법: from content.hook_thumb import make; make(그림경로, ["금값", "출렁인", "이유", "딱 3가지"], "3가지", 출력, seed=글이름)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from market.common import ROOT

FONT = ROOT / "assets" / "fonts" / "Pretendard-Black.otf"
SEAL_FONT = ROOT / "assets" / "fonts" / "SongMyung-Regular.ttf"
RED, INK, PAPER, PINE, GOLD = (200, 30, 40), (22, 20, 18), (243, 235, 221), (30, 90, 58), (232, 180, 34)
# 판 색: (판, 글자, 강조, 낙관 바탕, 낙관 글자)
PANELS = {
    "홍": (RED, PAPER, GOLD, PAPER, RED),
    "먹": (INK, PAPER, GOLD, RED, PAPER),
    "솔잎": (PINE, PAPER, GOLD, RED, PAPER),
    "금": (GOLD, INK, RED, RED, PAPER),
    "미색": (PAPER, INK, RED, RED, PAPER),
}
ORDER = ["홍", "먹", "홍", "솔잎", "홍", "미색", "홍", "금"]  # 홍이 기본(브랜드색), 사이사이 다른 색
W = 1080


def style_for(seed: str, prev: tuple[str, str] | None = None) -> tuple[str, str]:
    """글 이름으로 정해지는 (판 색, 위치). 바로 앞 글과 같은 조합은 피한다."""
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    for k in range(len(ORDER) * 2):
        st = (ORDER[(h + k) % len(ORDER)], "right" if (h // 7 + k) % 3 else "left")
        if st != prev and (not prev or st[0] != prev[0]):
            return st
    return st


def _cover(im: Image.Image, w: int, h: int, cx: float) -> Image.Image:
    r = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    x = int((im.width - w) * cx)
    y = int((im.height - h) * 0.5)
    return im.crop((x, y, x + w, y + h))


def _seal(c: Image.Image, x: int, y: int, s: int, bg, fg) -> None:
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((x, y, x + s, y + s), radius=12, fill=bg)
    d.rounded_rectangle((x + 8, y + 8, x + s - 8, y + s - 8), radius=8, outline=fg, width=4)
    f = ImageFont.truetype(str(SEAL_FONT), int(s * 0.62))
    d.text((x + (s - d.textlength("억", font=f)) / 2, y + s * 0.12), "억", font=f, fill=fg)


def make(art: Path, lines: list[str], accent: str, out: Path, seed: str = "", panel: str | None = None,
         side: str | None = None, focus: float = 0.5, prev: tuple[str, str] | None = None) -> tuple[str, str]:
    """썸네일 1장. 돌려주는 값 = 쓴 (판 색, 위치) — 다음 글이 겹치지 않게 넘겨 주면 된다."""
    p, s = style_for(seed or out.stem, prev)
    panel, side = panel or p, side or s
    bg, fg, ac, sb, sf = PANELS[panel]
    pw = 470  # 판 폭 (그림 610 : 판 470 ≈ 57 : 43)
    c = Image.new("RGB", (W, W), bg)
    pic = _cover(Image.open(art).convert("RGB"), W - pw, W, focus)
    px, tx = (0, W - pw) if side == "right" else (pw, 0)
    c.paste(pic, (px, 0))
    d = ImageDraw.Draw(c)
    # 글자 크기: 줄마다 판 폭(여백 빼고)에 꽉 차게, 최대 170. 짧은 줄이 튀지 않게 가장 작은 줄의 1.35배까지
    def fit(l: str) -> int:
        size = 170
        while size > 60 and d.textlength(l, font=ImageFont.truetype(str(FONT), size)) > pw - 64:
            size -= 2
        return size
    sizes = [fit(l) for l in lines]
    sizes = [min(z, int(min(sizes) * 1.35)) for z in sizes]
    gap = 14
    y = (W - sum(int(z * 1.08) for z in sizes) - gap * (len(lines) - 1)) // 2 - 40
    for l, z in zip(lines, sizes):
        f = ImageFont.truetype(str(FONT), z)
        x = tx + 32
        if accent and accent in l:
            a, b = l.split(accent, 1)
            for part, col in ((a, fg), (accent, ac), (b, fg)):
                d.text((x, y), part, font=f, fill=col)
                x += d.textlength(part, font=f)
        else:
            d.text((x, y), l, font=f, fill=fg)
        y += int(z * 1.08) + gap
    _seal(c, tx + pw - 136, W - 136, 100, sb, sf)
    out.parent.mkdir(parents=True, exist_ok=True)
    c.save(out)
    return panel, side


if __name__ == "__main__":
    # 시안: 같은 글로 색·위치 5가지
    import sys
    art = ROOT / "assets" / "art-library" / "fall-tiger.jpg"
    o = Path(sys.argv[1] if len(sys.argv) > 1 else "hook-samples")
    combos = [("홍", "right"), ("먹", "left"), ("솔잎", "right"), ("금", "left"), ("미색", "right")]
    for pnl, sd in combos:
        make(art, ["금값", "출렁인", "이유", "딱 3가지"], "3가지", o / f"{pnl}-{sd}.png", panel=pnl, side=sd,
             focus=0.75 if sd == "right" else 0.75)
