"""블로그 프로필·커버 이미지 생성 (억소리 나는 스포츠). 사진 없이 글자·도형만 쓴다.

글꼴: 나눔고딕(SIL OFL, 상업 이용 가능). 경로는 환경 변수 BRAND_FONT_DIR (기본: 시스템 글꼴 폴더에서 찾기).
사용법: BRAND_FONT_DIR=/path/to/fonts python -m content.brand
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "brand"
BG = (14, 17, 26)          # 짙은 남색
GOLD = (245, 190, 40)      # 돈 느낌 노랑
WHITE = (245, 245, 245)
GRAY = (150, 158, 175)


FONTS = ROOT / "assets" / "fonts"  # 저장소에 넣은 글꼴 (모두 SIL OFL, 라이선스 파일 같이 있음)
BUNDLED = {"display": "Pretendard-Black.otf",           # 제목·큰 숫자 (2026-09-30: Black Han Sans의 5가 S처럼 보여 교체)
           "mono": "NanumGothicCoding-Regular.ttf",      # 영수증 (고정폭)
           "monob": "NanumGothicCoding-Bold.ttf"}


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    if weight in BUNDLED:
        if (FONTS / BUNDLED[weight]).exists():
            return ImageFont.truetype(str(FONTS / BUNDLED[weight]), size)
        weight = "xb" if weight == "display" else "b"
    name = {"xb": "NanumGothicExtraBold.ttf", "b": "NanumGothicBold.ttf", "r": "NanumGothic.ttf"}[weight]
    base = Path(os.environ.get("BRAND_FONT_DIR", "/usr/share/fonts"))
    hits = list(base.rglob(name))
    if not hits and weight == "xb":  # 서버에 ExtraBold가 없으면 Bold로 대신한다
        hits = list(base.rglob("NanumGothicBold.ttf"))
    if not hits:
        raise SystemExit(f"글꼴 {name}을 {base}에서 찾지 못했습니다")
    return ImageFont.truetype(str(hits[0]), size)


def center_text(d: ImageDraw.ImageDraw, xy_center, text, f, fill):
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text((xy_center[0] - (r - l) / 2 - l, xy_center[1] - (b - t) / 2 - t), text, font=f, fill=fill)


def fit(d: ImageDraw.ImageDraw, text: str, weight: str, size: int, max_w: float) -> ImageFont.FreeTypeFont:
    """글자가 max_w보다 넓으면 글꼴 크기를 줄인다."""
    while size > 10:
        f = font(weight, size)
        l, _, r, _ = d.textbbox((0, 0), text, font=f)
        if r - l <= max_w:
            return f
        size -= 2
    return font(weight, size)


def bars(d: ImageDraw.ImageDraw, x0: int, base_y: int, w: int, gap: int, heights: list[int], color):
    for i, h in enumerate(heights):
        x = x0 + i * (w + gap)
        d.rounded_rectangle((x, base_y - h, x + w, base_y), radius=w // 5, fill=color)


def profile(size: int = 800) -> Image.Image:
    """프로필은 원형으로 잘려 보이므로 가운데 70% 안에 모두 넣는다."""
    im = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(im)
    c = size // 2
    d.ellipse((c - size * 0.42, c - size * 0.42, c + size * 0.42, c + size * 0.42), outline=GOLD, width=size // 60)
    center_text(d, (c, c - size * 0.05), "억", font("xb", int(size * 0.42)), GOLD)
    center_text(d, (c, c + size * 0.25), "백억소리", font("b", int(size * 0.075)), WHITE)
    return im


def cover(w: int = 1600, h: int = 900) -> Image.Image:
    """커버는 앱마다 위아래·좌우가 잘릴 수 있어 핵심 글자를 가운데 80% 안에 둔다."""
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    # 뒤쪽 오르는 막대 (연봉 그래프 느낌)
    bars(d, int(w * 0.62), int(h * 0.86), int(w * 0.045), int(w * 0.02),
         [int(h * k) for k in (0.12, 0.2, 0.3, 0.44, 0.62)], (34, 40, 58))
    max_w = w * 0.8
    square = h / w > 0.8
    titles = ["억소리 나는", "스포츠"] if square else ["억소리 나는 스포츠"]
    tsize = int(h * (0.12 if square else 0.13))
    y = h * (0.30 if square else 0.40)
    for t in titles:
        center_text(d, (w * 0.5, y), t, fit(d, t, "xb", tsize, max_w), WHITE)
        y += tsize * 1.15
    y += h * (0.02 if square else -0.01)
    center_text(d, (w * 0.5, y), "선수 몸값, 1경기에 얼마?", fit(d, "선수 몸값, 1경기에 얼마?", "b", int(h * 0.065), max_w), GOLD)
    y += h * 0.11
    sub = "연봉 · 이적료 · 계약금을 숫자로 쪼개 봅니다"
    center_text(d, (w * 0.5, y), sub, fit(d, sub, "r", int(h * 0.04), max_w), GRAY)
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profile().save(OUT / "profile.png")
    cover().save(OUT / "cover-16x9.png")
    cover(1080, 1080).save(OUT / "cover-square.png")
    print("저장:", ", ".join(p.name for p in sorted(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
