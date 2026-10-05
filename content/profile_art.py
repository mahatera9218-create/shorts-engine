"""블로그 프로필 사진 후보 (2026-10-05): 억선생 캐릭터 + 화투 팔레트 + 한국 전통미.

네이버 프로필은 작은 동그라미로 보인다 → 얼굴 크게, 배경 단순, 색 대비 강하게, 그림 속 글자 없음.
장사꾼(억선생)은 쇼츠의 1번 장면을 참고 그림으로 넘겨 같은 얼굴·옷으로 맞춘다.
결과: reports/브랜드/프로필/후보-*.png + 동그라미 미리보기 0-미리보기.png
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from . import ai_short as base
from .motion_short import seal

OUT = Path("reports/브랜드/프로필")
REF = base.OUT / "scene-1.png"
COMMON = ("Square 1:1 profile picture for a Korean economy blog, shown as a small circle on phones: the subject is "
          "centered and large, simple background, strong contrast. Bold flat style of a Korean hwatu flower card "
          "crossed with Kim Hong-do genre painting: thick black ink outlines, flat vermilion red, black, cream, pine "
          "green and gold only. Distinctly Korean (Joseon) elements only, nothing Chinese or Japanese. No text, no "
          "letters, no numbers, no logo. Use the attached image only as the character reference: the same merchant "
          "with the same round face, mustache, black gat and indigo jeogori, drawn a little older and wiser, "
          "a warm trustworthy middle-aged 'Mr. Eok' teacher-merchant. ")
CANDIDATES = {
    "1-얼굴-홍색": "Head-and-shoulders portrait, friendly confident smile, looking at the viewer, plain bold "
                  "vermilion red background with a faint gold full-moon disc behind his head.",
    "2-엽전-들고": "Upper body, holding up a string of brass yeopjeon coins next to his face with a wink, cream "
                  "background with a stylized black pine branch at the top corner.",
    "3-엽전-테두리": "His smiling face framed inside a big round brass yeopjeon coin (round coin with a square "
                   "hole motif around him as a frame), red background.",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hdr = {"Authorization": f"Bearer {base.key('OPENAI_API_KEY')}"}
    for name, scene in CANDIDATES.items():
        out = OUT / f"후보-{name}.png"
        if out.exists() or not base.key("OPENAI_API_KEY"):
            continue
        t0 = time.time()
        with REF.open("rb") as f:
            r = requests.post("https://api.openai.com/v1/images/edits", headers=hdr,
                              data={"model": base.MODEL, "prompt": COMMON + scene, "size": "1024x1024",
                                    "quality": base.QUALITY, "n": "1"},
                              files=[("image[]", ("ref.png", f, "image/png"))], timeout=300)
        if r.status_code != 200:
            print(f"{name} 실패 HTTP {r.status_code}: {r.text[:200]}")
            continue
        out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
        print(f"{name} {time.time() - t0:.0f}초")
    # 4번: 코드로 만든 낙관 '억' (AI 없음, 0원)
    s = Image.new("RGBA", (1024, 1024), (243, 235, 221, 255))
    s.alpha_composite(seal(760).resize((760, 760), Image.LANCZOS), (132, 132))
    s.convert("RGB").save(OUT / "후보-4-낙관.png")
    # 동그라미 미리보기 (네이버 프로필처럼 작게)
    files = sorted(OUT.glob("후보-*.png"))
    sheet = Image.new("RGB", (len(files) * 260 + 20, 300), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB").resize((220, 220), Image.LANCZOS)
        m = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(m).ellipse((0, 0, 219, 219), fill=255)
        sheet.paste(im, (20 + i * 260, 20), m)
        small = Image.open(f).convert("RGB").resize((48, 48), Image.LANCZOS)
        m2 = Image.new("L", (48, 48), 0)
        ImageDraw.Draw(m2).ellipse((0, 0, 47, 47), fill=255)
        sheet.paste(small, (106 + i * 260, 246), m2)
        d.text((20 + i * 260, 250), f.stem.split("-")[1], fill=(0, 0, 0))
    sheet.save(OUT / "0-미리보기.png")


if __name__ == "__main__":
    main()
