"""캐시미어 다이어리 커버·프로필 후보 (대표 지시 2026-10-05). GPT Image, 고화질.

- 페르소나: 차분하고 우아한 여성 패션 블로거, 조용한 럭셔리·올드머니 (prompts/addon-fashion.md)
- 사람 얼굴 없음(실존하지 않는 인물 금지), 글자·로고·브랜드 표시 없음
- 커버 1536x1024: 휴대폰 앱은 가운데 정사각형만 보이므로 주인공을 가운데에
- 프로필 1024x1024: 작은 동그라미로 보임 → 주인공 하나 크게, 배경 단순
결과: reports/브랜드/캐시미어/커버-*.png · 프로필-*.png + 0-미리보기.png (동그라미·휴대폰 자르기)
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

OUT = Path("reports/브랜드/캐시미어")
MODEL, QUALITY = "gpt-image-2", "high"
STYLE = ("Editorial still-life photograph for an elegant Korean women's fashion blog called Cashmere Diary. "
         "Quiet luxury, old-money mood: soft natural window light, warm neutral palette of cream, oatmeal, camel, "
         "ivory and a touch of muted gold, fine textures of cashmere knit, wool, linen and aged paper. Calm, refined, "
         "magazine quality, shallow depth of field. No people, no faces, no hands, no text, no letters, no numbers, "
         "no logos, no brand marks. ")
COVERS = {  # 1536x1024, 가운데에 주인공
    "1-다이어리-플랫레이": "Top-down flat lay centered in the frame: an open vintage leather-bound diary with blank cream "
                     "pages, a folded camel cashmere scarf, a single strand of pearls and a fountain pen on ivory linen; "
                     "generous calm empty space at the left and right edges.",
    "2-캐시미어-옷장": "A refined wooden wardrobe, centered, with cashmere coats and knits in cream, camel and oatmeal "
                  "hanging neatly, a structured leather handbag without logos on the shelf, soft morning light; "
                  "quiet symmetrical composition.",
    "3-화장대-오후": "An elegant antique vanity table, centered: a stack of folded cashmere sweaters tied with a silk "
                 "ribbon, a small vase of white garden roses, a closed leather diary and a pair of gold earrings, "
                 "afternoon sunlight through sheer curtains.",
}
PROFILES = {  # 1024x1024, 동그라미 안에 하나 크게
    "1-개킨-니트": "Close-up of a neatly folded cream cashmere sweater with a camel one on top, filling the center, "
               "plain warm ivory background, strong soft shadow for contrast.",
    "2-리본-다이어리": "A small vintage leather diary tied with a camel cashmere ribbon, centered and large, plain soft "
                  "oatmeal background.",
    "3-진주-캐시미어": "A single strand of pearls coiled in a circle on top of a camel cashmere knit texture, filling "
                  "the frame, minimal and elegant.",
}

# 상점 그림 프로필 (대표 지시 2026-10-06: "작지만 아우라와 따뜻함이 느껴지는 상점 건물"). 간판에 글자 없음.
SHOP = ("Square 1:1 profile picture for an elegant Korean women's fashion blog called Cashmere Diary, shown as a small "
        "circle: one small boutique shop building, large and centered, the whole facade visible. Small but with a "
        "quiet aura of luxury and a warm, welcoming glow from the windows. Hand-painted illustration, not a photo. "
        "Palette of cream, warm beige #E0D3BB, camel, ivory, deep green and soft gold light. Simple plain background "
        "so it reads well when small. No people, no text, no letters, no numbers, no logos on the sign or awning. ")
SHOPS = {
    "상점-1-해질녘-부티크": "Watercolor and ink: a narrow two-storey European boutique at dusk, cream stone facade, "
                      "camel striped awning, tall arched shop window glowing warm gold with folded cashmere knits "
                      "and a coat on a mannequin, a little lantern by the door.",
    "상점-2-담쟁이-코너숍": "Soft gouache: a tiny corner shop with deep green wooden frontage and ivy climbing the "
                      "walls, warm light spilling from the window display of cashmere scarves, potted olive tree and "
                      "a bench by the door, early evening.",
    "상점-3-정면-대칭": "Elegant flat illustration, perfectly symmetrical front view: a small jewel-box boutique with "
                    "a rounded doorway, ivory facade, camel awning, two glowing windows with folded knits, wall "
                    "lamps on both sides, calm and timeless.",
}


def draw(prompt: str, size: str, out: Path) -> None:
    if out.exists():
        return
    t0 = time.time()
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                      json={"model": MODEL, "prompt": prompt, "size": size, "quality": QUALITY, "n": 1}, timeout=600)
    if r.status_code != 200:
        print(f"{out.name} 실패 HTTP {r.status_code}: {r.text[:200]}")
        return
    out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    print(f"{out.name} {time.time() - t0:.0f}초")


def preview() -> None:
    covers, profs = sorted(OUT.glob("커버-*.png")), sorted(OUT.glob("프로필-*.png"))
    sheet = Image.new("RGB", (1000, 40 + len(covers) * 330 + 300), (250, 248, 244))
    d = ImageDraw.Draw(sheet)
    y = 20
    for f in covers:  # 왼쪽 전체, 오른쪽 휴대폰(가운데 정사각형)
        im = Image.open(f).convert("RGB")
        sheet.paste(im.resize((450, 300), Image.LANCZOS), (20, y))
        w, h = im.size
        sheet.paste(im.crop(((w - h) // 2, 0, (w + h) // 2, h)).resize((300, 300), Image.LANCZOS), (500, y))
        d.text((820, y + 140), f.stem, fill=(0, 0, 0))
        y += 330
    for i, f in enumerate(profs):
        im = Image.open(f).convert("RGB").resize((220, 220), Image.LANCZOS)
        m = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(m).ellipse((0, 0, 219, 219), fill=255)
        sheet.paste(im, (20 + i * 320, y), m)
        d.text((20 + i * 320, y + 230), f.stem, fill=(0, 0, 0))
    sheet.save(OUT / "0-미리보기.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scene in COVERS.items():
        draw(STYLE + scene, "1536x1024", OUT / f"커버-{name}.png")
    for name, scene in PROFILES.items():
        draw(STYLE + scene, "1024x1024", OUT / f"프로필-{name}.png")
    for name, scene in SHOPS.items():
        draw(SHOP + scene, "1024x1024", OUT / f"프로필-{name}.png")
    preview()


if __name__ == "__main__":
    main()
