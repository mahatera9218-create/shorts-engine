"""그림 창고 (대표 결정 2026-10-05): 고화질 본문 그림을 한 번 그려 두고 글마다 골라 다시 쓴다.

- config/art_library.yaml의 장면 중 없는 것만 GPT Image 2 high 1536x1024로 그린다(이미 있는 건 0원).
- 억선생이 나오는 장면은 쇼츠 1번 장면을 참고 그림으로 넘겨 얼굴·옷을 맞춘다.
- 저장: assets/art-library/<id>.jpg (원본 해상도, JPG 95·색 손실 없게 4:4:4) — PNG(4MB)는 저장소가 너무 커져서.
- 고르기: pick(tags) → 태그가 많이 겹치는 그림, 최근에 쓴 그림은 뒤로 (글쓰기에서 씀).
- 한눈에 보기: assets/art-library/0-한눈에.jpg
사용법: python -m content.art_library
"""
from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

from market.common import ROOT
from .post_art import STYLE

CFG = ROOT / "config" / "art_library.yaml"
LIB = ROOT / "assets" / "art-library"
REF = ROOT / "reports" / "쇼츠-시안" / "금값-출렁" / "scene-1.png"
HERO = ("Use the attached image only as the character reference: 'Mr. Eok' is the same cheerful middle-aged Joseon "
        "merchant with the same round face, thin mustache, black gat hat, indigo jeogori and white baji. ")
FRAME = "Wide 3:2 blog illustration, absolutely no text, letters or numbers anywhere. "


def scenes() -> list[dict]:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))["scenes"]


def draw(log: list[str]) -> None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        log.append("OPENAI_API_KEY 없음")
        return
    LIB.mkdir(parents=True, exist_ok=True)
    hdr = {"Authorization": f"Bearer {key}"}
    for s in scenes():
        out = LIB / f"{s['id']}.jpg"
        if out.exists():
            continue
        prompt = STYLE + FRAME + (HERO if s.get("hero") else "") + s["prompt"]
        body = {"model": "gpt-image-2", "prompt": prompt, "size": "1536x1024", "quality": "high"}
        t0 = time.time()
        if s.get("hero") and REF.exists():
            with REF.open("rb") as f:
                r = requests.post("https://api.openai.com/v1/images/edits", headers=hdr, timeout=600,
                                  data={**body, "n": "1"}, files=[("image[]", ("ref.png", f, "image/png"))])
        else:
            r = requests.post("https://api.openai.com/v1/images/generations", headers=hdr, json={**body, "n": 1},
                              timeout=600)
        if r.status_code != 200:
            log.append(f"- {s['id']} 실패 HTTP {r.status_code}: {r.text[:160]}")
            if r.status_code in (401, 429) and ("quota" in r.text or "billing" in r.text):
                log.append("- 잔액 부족으로 멈춤 (충전 후 다시 돌리면 남은 것만 그림)")
                return
            continue
        im = Image.open(io.BytesIO(base64.b64decode(r.json()["data"][0]["b64_json"]))).convert("RGB")
        im.save(out, quality=95, subsampling=0, optimize=True)
        log.append(f"- {s['id']} {time.time() - t0:.0f}초")


def sheet() -> None:
    have = [s for s in scenes() if (LIB / f"{s['id']}.jpg").exists()]
    if not have:
        return
    w, h, cols = 360, 240, 5
    rows = (len(have) + cols - 1) // cols
    c = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 34) + 8), (243, 235, 221))
    d = ImageDraw.Draw(c)
    f = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Pretendard-Black.otf"), 18)
    for i, s in enumerate(have):
        x, y = 8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 34)
        c.paste(Image.open(LIB / f"{s['id']}.jpg").resize((w, h), Image.LANCZOS), (x, y))
        d.text((x + 4, y + h + 6), f"{s['id']}  {' '.join(s['tags'][:3])}", fill=(22, 20, 18), font=f)
    c.save(LIB / "0-한눈에.jpg", quality=85)


def pick(tags: list[str], used: list[str] = (), n: int = 1) -> list[str]:
    """글의 태그와 많이 겹치는 그림 id (최근에 쓴 그림은 뒤로)."""
    have = [s for s in scenes() if (LIB / f"{s['id']}.jpg").exists()]
    score = lambda s: (len(set(tags) & set(s["tags"])), s["id"] not in used)
    return [s["id"] for s in sorted(have, key=score, reverse=True)[:n]]


def main() -> None:
    log: list[str] = []
    draw(log)
    sheet()
    have = sum((LIB / f"{s['id']}.jpg").exists() for s in scenes())
    log.append(f"창고: {have}/{len(scenes())}장")
    print("\n".join(log))


if __name__ == "__main__":
    main()
