"""경제 블로그 썸네일 시안 (2026-10-04, 대표 요청 "썸네일 디자인 시안 만들어봐").

홈판 카드 = 썸네일 + 제목. 썸네일은 '강한 사실(숫자)', 제목은 '긴장 + 빈칸' (money-content-writer 제목 공식).
시안 4종: A 큰 숫자 / B 전광판 / C 시간차 대조 / D 질문 카드. 한국 증시 관례대로 상승 = 빨강, 하락 = 파랑.
사진은 무료 사진(Pexels)만. 키가 없으면 그라데이션 배경으로 그린다.

사용: python -m content.econ_thumb --demo [--out reports/썸네일-시안]
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from market.common import ROOT, secret

W = H = 1080
FONT_DIRS = [os.environ.get("BRAND_FONT_DIR", ""), "/usr/share/fonts/truetype/nanum", str(ROOT / "assets" / "fonts")]
UP, DOWN = (229, 57, 53), (30, 99, 214)          # 상승 빨강, 하락 파랑 (국내 증시 관례)
UP_ON_DARK, DOWN_ON_DARK = (255, 92, 84), (88, 156, 255)  # 어두운 바탕 위 글자용 (잘 읽히게)
INK, WHITE, NAVY = (17, 24, 39), (255, 255, 255), (13, 27, 52)
ASSET = {  # 자산별 꼬리표 색
    "금": (224, 177, 58), "미국주식": (59, 130, 246), "코인": (247, 147, 26),
    "국내주식": (46, 160, 90), "돈 굴리기": (20, 184, 166), "아침 시황": (139, 92, 246),
}
BRAND = "매일 아침 경제"   # 블로그 이름이 정해지면 바꾼다 (대표 결정 대기)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        p = Path(d) / name
        if d and p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype(str(Path(FONT_DIRS[1]) / "NanumGothicBold.ttf"), size)


def heavy(size):  # 숫자·큰 글자
    return font("NanumSquareB.ttf", size)


def bold(size):
    return font("NanumGothicBold.ttf", size)


def fit(d: ImageDraw.ImageDraw, text: str, maker, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    while size > 20:
        f = maker(size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return maker(size)


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h)).convert("RGB")


def gradient(w: int, h: int, top, bottom) -> Image.Image:
    g = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        px.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g


def shade(img: Image.Image, start: float = 0.35, strength: int = 230) -> Image.Image:
    """아래쪽으로 갈수록 어둡게 (글자가 사진 위에서 읽히게)."""
    w, h = img.size
    mask = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, (y / h - start) / (1 - start))
        mask.putpixel((0, y), int(strength * min(1.0, t * 1.2)))
    dark = Image.new("RGB", (w, h), (8, 12, 20))
    return Image.composite(dark, img, mask.resize((w, h)))


def chip(d: ImageDraw.ImageDraw, xy, text: str, color, size: int = 40):
    f = bold(size)
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + size * 1.1, y + size * 1.7], radius=size * 0.85, fill=color)
    d.text((x + size * 0.55, y + size * 0.32), text, font=f, fill=WHITE if sum(color) < 600 else INK)


def corner_marks(d: ImageDraw.ImageDraw, dark: bool = True):
    col = (255, 255, 255, 200) if dark else (60, 60, 60, 200)
    d.text((48, H - 74), BRAND, font=bold(30), fill=col)
    d.text((W - 300, 44), "시안 · 가상 숫자", font=bold(26), fill=(255, 210, 0) if dark else (200, 120, 0))


def delta_pill(d: ImageDraw.ImageDraw, xy, text: str, up: bool, size: int = 46):
    f = bold(size)
    x, y = xy
    arrow = "▲ " if up else "▼ "
    tw = d.textlength(arrow + text, font=f)
    d.rounded_rectangle([x, y, x + tw + size, y + size * 1.6], radius=12, fill=UP if up else DOWN)
    d.text((x + size / 2, y + size * 0.28), arrow + text, font=f, fill=WHITE)


# ---------------------------------------------------------------- 시안 A: 큰 숫자
def design_a(photo, asset, label, big, delta, up) -> Image.Image:
    img = shade(cover(photo, W, H), 0.30)
    d = ImageDraw.Draw(img, "RGBA")
    chip(d, (48, 44), asset, ASSET[asset])
    d.text((60, H - 560), label, font=bold(52), fill=(235, 238, 245))
    f = fit(d, big, heavy, 230, W - 120)
    d.text((54, H - 490), big, font=f, fill=WHITE)
    delta_pill(d, (60, H - 205), delta, up)
    corner_marks(d)
    return img


# ---------------------------------------------------------------- 시안 B: 전광판
def design_b(photo, asset, name, price, delta, up, ticker) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    img.paste(cover(photo, W, 640), (0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    chip(d, (48, 44), asset, ASSET[asset])
    d.rectangle([0, 640, W, H], fill=NAVY)
    d.rectangle([0, 640, W, 652], fill=UP if up else DOWN)
    d.text((60, 690), name, font=bold(56), fill=(200, 210, 230))
    f = fit(d, price, heavy, 170, 640)
    d.text((56, 760), price, font=f, fill=WHITE)
    col = UP_ON_DARK if up else DOWN_ON_DARK
    arrow = "▲" if up else "▼"
    fd = heavy(84)
    txt = f"{arrow}{delta}"
    d.text((W - 60 - d.textlength(txt, font=fd), 790), txt, font=fd, fill=col)
    # 아래 작은 띠: 다른 자산 3개
    d.rectangle([0, 960, W, H], fill=(8, 16, 34))
    x = 48
    for nm, ch, u in ticker:
        s = f"{nm} {'▲' if u else '▼'}{ch}"
        d.text((x, 990), s, font=bold(34), fill=UP_ON_DARK if u else DOWN_ON_DARK)
        x += d.textlength(s, font=bold(34)) + 48
    d.text((W - 300, 44), "시안 · 가상 숫자", font=bold(26), fill=(255, 210, 0))
    return img


# ---------------------------------------------------------------- 시안 C: 시간차 대조
def design_c(photo, asset, before_label, before, after_label, after, up) -> Image.Image:
    base = cover(photo, W, H)
    left = ImageEnhance.Color(base.crop((0, 0, W // 2, H))).enhance(0.0)
    left = ImageEnhance.Brightness(left).enhance(0.45)
    right = ImageEnhance.Brightness(base.crop((W // 2, 0, W, H))).enhance(0.55)
    img = Image.new("RGB", (W, H))
    img.paste(left, (0, 0))
    img.paste(right, (W // 2, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([W // 2 - 3, 0, W // 2 + 3, H], fill=(255, 255, 255, 220))
    chip(d, (48, 44), asset, ASSET[asset])
    for x0, lab, val, col in ((0, before_label, before, (190, 195, 205)), (W // 2, after_label, after, WHITE)):
        cx = x0 + W // 4
        fl = bold(54)
        d.text((cx - d.textlength(lab, font=fl) / 2, 400), lab, font=fl, fill=col)
        fv = fit(d, val, heavy, 150, W // 2 - 190)
        d.text((cx - d.textlength(val, font=fv) / 2, 480), val, font=fv, fill=col)
    # 가운데 화살표 원
    c = (W // 2, 545)
    d.ellipse([c[0] - 52, c[1] - 52, c[0] + 52, c[1] + 52], fill=UP if up else DOWN)
    fa = heavy(60)
    d.text((c[0] - d.textlength("→", font=fa) / 2, c[1] - 38), "→", font=fa, fill=WHITE)
    corner_marks(d)
    return img


# ---------------------------------------------------------------- 시안 D: 질문 카드
def design_d(photo, asset, line1, line2, up) -> Image.Image:
    img = Image.new("RGB", (W, H), (245, 241, 232))
    ph = cover(photo, W - 120, 470)
    m = Image.new("L", ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, ph.width, ph.height], radius=36, fill=255)
    img.paste(ph, (60, 150), m)
    d = ImageDraw.Draw(img, "RGBA")
    chip(d, (60, 56), asset, ASSET[asset])
    f1 = fit(d, line1, heavy, 92, W - 120)
    d.text((60, 670), line1, font=f1, fill=INK)
    f2 = fit(d, line2, heavy, 150, W - 120)
    d.text((56, 790), line2, font=f2, fill=UP if up else DOWN)
    d.text((60, H - 74), BRAND, font=bold(30), fill=(90, 90, 90))
    d.text((W - 300, 64), "시안 · 가상 숫자", font=bold(26), fill=(200, 120, 0))
    return img


# ---------------------------------------------------------------- 사진
QUERY = {"금": ("gold bars", "gold"), "미국주식": ("stock market screen", "stock"), "코인": ("bitcoin", "bitcoin"),
         "국내주식": ("stock chart", "chart"), "돈 굴리기": ("savings coins", "coin")}
PEOPLE = ("man", "men", "woman", "women", "person", "people", "face", "portrait", "boy", "girl", "child")


def photo_for(asset: str, i: int = 0) -> Image.Image:
    q, must = QUERY.get(asset, ("finance", "money"))
    key = secret("PEXELS_API_KEY")
    if key:
        try:
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                             params={"query": q, "orientation": "square", "per_page": 30}, timeout=20)
            ok = [p for p in r.json().get("photos", []) if must in (p.get("alt") or "").lower()
                  and not any(w in (p.get("alt") or "").lower().split() for w in PEOPLE)]
            if ok:
                p = ok[i % len(ok)]
                return Image.open(io.BytesIO(requests.get(p["src"]["large2x"], timeout=30).content)).convert("RGB")
        except (requests.RequestException, ValueError, KeyError):
            pass
    base = {"금": ((120, 90, 20), (30, 22, 8)), "미국주식": ((20, 60, 120), (6, 14, 32)),
            "코인": ((150, 80, 10), (25, 14, 4))}.get(asset, ((40, 60, 80), (10, 14, 20)))
    return gradient(W, H, *base).filter(ImageFilter.GaussianBlur(2))


def feed_mock(cards: list[tuple[Image.Image, str]]) -> Image.Image:
    """휴대폰 홈판처럼 작게 줄였을 때 읽히는지 보는 판."""
    pw = 1080
    out = Image.new("RGB", (pw, 300 * len(cards) + 120), WHITE)
    d = ImageDraw.Draw(out)
    d.text((40, 36), "홈판에서 이렇게 보여요 (실제 크기 비슷)", font=bold(38), fill=INK)
    for k, (im, title) in enumerate(cards):
        y = 120 + k * 300
        out.paste(im.resize((260, 260), Image.LANCZOS), (40, y))
        f = bold(40)
        words, line, lines = title.split(), "", []
        for w in words:
            if d.textlength(line + " " + w, font=f) > pw - 360:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        for j, ln in enumerate(lines[:3]):
            d.text((330, y + 20 + j * 56), ln, font=f, fill=INK)
        d.text((330, y + 200), BRAND, font=bold(28), fill=(140, 140, 140))
        d.line([(40, y + 280), (pw - 40, y + 280)], fill=(230, 230, 230), width=2)
    return out


def sheet(imgs: list[Image.Image], labels: list[str]) -> Image.Image:
    s = 540
    out = Image.new("RGB", (s * 2, s * 2 + 120), WHITE)
    d = ImageDraw.Draw(out)
    for k, (im, lab) in enumerate(zip(imgs, labels)):
        x, y = (k % 2) * s, (k // 2) * (s + 60)
        d.text((x + 16, y + 10), lab, font=bold(34), fill=INK)
        out.paste(im.resize((s - 20, s - 20), Image.LANCZOS), (x + 10, y + 60))
    return out


def demo(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    a = design_a(photo_for("금", 0), "금", "금 1돈 (순금 3.75g)", "52만원", "1년 전보다 48%", True)
    b = design_b(photo_for("미국주식", 0), "아침 시황", "나스닥 종합", "18,240", "2.3%", False,
                 [("S&P500", "1.1%", False), ("비트코인", "3.4%", True), ("금", "0.8%", True)])
    c = design_c(photo_for("금", 1), "금", "1년 전", "35만원", "지금", "52만원", True)
    dd = design_d(photo_for("코인", 0), "코인", "비트코인, 하루 새", "+10.2%", True)
    files = []
    for name, im in (("A-큰숫자", a), ("B-전광판", b), ("C-시간차대조", c), ("D-질문카드", dd)):
        p = out / f"{name}.png"
        im.save(p)
        files.append(p)
    sheet([a, b, c, dd], ["A 큰 숫자", "B 전광판", "C 시간차 대조", "D 질문 카드"]).save(out / "0-한눈에.png")
    feed_mock([(a, "1년 전 35만원이던 금, 지금은 얼마일까?"), (b, "나스닥 하루 2% 빠졌는데 엔비디아는 왜 올랐을까?"),
               (c, "금값 1년 새 48%, 아직 더 오를 수 있을까?"), (dd, "비트코인 하루 10% 급등, 무슨 일이 있었나?")]).save(out / "0-홈판-미리보기.png")
    return files


# ---------------------------------------------------------------- 사진 후보 모으기 (디자인 시안용, 2026-10-04)
CANDIDATES = {  # 이름: (검색어, 설명에 있어야 할 말)
    "gold": [("gold bars", "gold"), ("gold bullion", "gold")],
    "stock": [("stock market screen", "stock"), ("trading chart monitor", "chart")],
    "bitcoin": [("bitcoin coin", "bitcoin"), ("cryptocurrency", "crypto")],
    "seoul": [("seoul skyline night", "seoul")],
    "wallstreet": [("wall street new york", "street"), ("stock exchange building", "exchange")],
    "savings": [("coins jar savings", "coin"), ("piggy bank", "piggy")],
}


def gather(out: Path, per: int = 4) -> None:
    """검색어별 무료 사진 후보를 받아 둔다 (사람 얼굴 빼고). 출처는 credits.json."""
    import json
    key = secret("PEXELS_API_KEY")
    out.mkdir(parents=True, exist_ok=True)
    credits = {}
    for name, qs in CANDIDATES.items():
        got = 0
        for q, must in qs:
            if got >= per:
                break
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                             params={"query": q, "per_page": 40}, timeout=20)
            for ph in r.json().get("photos", []):
                alt = (ph.get("alt") or "").lower()
                if must not in alt or any(w in alt.replace(",", " ").split() for w in PEOPLE):
                    continue
                img = Image.open(io.BytesIO(requests.get(ph["src"]["large2x"], timeout=30).content)).convert("RGB")
                img.thumbnail((1600, 1600))
                fn = f"{name}-{got + 1}.jpg"
                img.save(out / fn, quality=86)
                credits[fn] = {"id": ph["id"], "by": ph.get("photographer", ""), "page": ph.get("url", ""), "alt": ph.get("alt", "")}
                got += 1
                if got >= per:
                    break
    (out / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 옛 그림 후보 (김홍도·민화, 2026-10-04 대표 제안)
ART_SEARCH = {  # 이름: 위키미디어 공용 검색어
    "danwon": ["Kim Hong-do genre painting", "Danwon pungsokdo", "김홍도 풍속도"],
    "minhwa": ["Hojakdo tiger magpie", "Chaekgeori", "Korean folk painting minhwa"],
}
PD_OK = ("public domain", "pd", "cc0", "cc-zero")


def gather_art(out: Path, per: int = 12) -> None:
    """위키미디어 공용에서 '퍼블릭 도메인/CC0' 표시가 있는 옛 그림만 받는다. 라이선스·출처는 credits.json."""
    import json
    api = "https://commons.wikimedia.org/w/api.php"
    ua = {"User-Agent": "eoksori-thumb/1.0 (blog thumbnail research)"}
    out.mkdir(parents=True, exist_ok=True)
    credits, seen = {}, set()
    for name, queries in ART_SEARCH.items():
        got = 0
        for q in queries:
            if got >= per:
                break
            r = requests.get(api, headers=ua, timeout=30, params={
                "action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrnamespace": 6,
                "gsrlimit": 30, "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600})
            pages = (r.json().get("query") or {}).get("pages", {})
            for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
                title = pg.get("title", "")
                if title in seen or not title.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                ii = (pg.get("imageinfo") or [{}])[0]
                meta = ii.get("extmetadata") or {}
                lic = (meta.get("LicenseShortName") or {}).get("value", "")
                if not any(k in lic.lower() for k in PD_OK) or (ii.get("width") or 0) < 700:
                    continue
                try:
                    img = Image.open(io.BytesIO(requests.get(ii["thumburl"], headers=ua, timeout=60).content)).convert("RGB")
                except Exception:  # noqa: BLE001
                    continue
                img.thumbnail((1600, 1600))
                got += 1
                seen.add(title)
                fn = f"{name}-{got:02d}.jpg"
                img.save(out / fn, quality=86)
                credits[fn] = {"title": title, "license": lic, "page": ii.get("descriptionurl", ""),
                               "artist": (meta.get("Artist") or {}).get("value", "")[:200]}
                if got >= per:
                    break
    (out / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--photos", action="store_true", help="디자인 시안용 사진 후보 모으기")
    ap.add_argument("--art", action="store_true", help="김홍도·민화 퍼블릭 도메인 그림 후보 모으기")
    ap.add_argument("--out", default=str(ROOT / "reports" / "썸네일-시안"))
    a = ap.parse_args()
    if a.demo:
        for p in demo(Path(a.out)):
            print(p)
    if a.photos:
        gather(Path(a.out) / "photos")
    if a.art:
        gather_art(Path(a.out) / "art")


if __name__ == "__main__":
    main()
