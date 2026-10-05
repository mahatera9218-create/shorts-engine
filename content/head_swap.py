"""머리 바꾸기 시험 (2026-10-05, 대표 결정 '실존 인물은 조선 화풍 캐리커처로만'): 억선생 몸에 글 주인공 머리를 갈아 끼운다.

- 입력: 쇼츠 인형 조각의 초록 화면 원본(parts/hero_*-green.png). 그림체·몸·옷은 그대로, 머리만 바꾼다.
- 담당: Gemini 이미지 모델(나노바나나) → 안 되면 GPT Image 2 편집. 결과는 초록을 지워 투명 PNG.
- 규칙(DECISIONS 2026-10-05): 조선 화풍 캐리커처만, 사실에 맞는 중립·긍정 표정, 가짜 말·보증·비하 금지, 'AI 일러스트' 표시,
  로고 금지. 금·코인은 마스코트.
결과: reports/쇼츠-시안/머리바꾸기/<id>.png + 0-한눈에.png + 썸네일 시안
"""
from __future__ import annotations

import base64
import io
import os
import time
from datetime import date
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from market.common import ROOT
from .hook_thumb import make as thumb
from .motion_short import unscreen

PARTS = ROOT / "reports" / "쇼츠-시안" / "금값-출렁" / "parts"
OUT = ROOT / "reports" / "쇼츠-시안" / "머리바꾸기"
COMMON = ("Edit this image: keep the exact same Joseon ink-and-wash painting style, the same body, pose, hanbok clothes, "
          "black gat hat and the same flat pure green background. Replace ONLY the head/face. ")
RULES = (" It must look like a hand-painted Joseon-era caricature illustration, clearly not a photo. Friendly, "
         "respectful, not mocking. No text, no logos, no speech bubbles.")
HEADS = [
    {"id": "lee-jaeyong", "base": "hero_happy", "label": "이재용 회장 (삼성전자)",
     "prompt": "New head: a recognizable but gently stylized caricature of Lee Jae-yong, chairman of Samsung "
               "Electronics, smiling warmly, short neat hair under the gat."},
    {"id": "kevin-warsh", "base": "hero_point", "label": "케빈 워시 (연준)",
     "prompt": "New head: a recognizable but gently stylized caricature of Kevin Warsh, the American economist and "
               "central banker, calm and thoughtful expression, slight smile."},
    {"id": "gold-toad", "base": "hero_happy", "label": "금 (금두꺼비)",
     "prompt": "New head: a cute golden toad head (Korean lucky gold toad, geumdukkeobi) with a shiny gold skin and a "
               "happy grin, wearing the gat."},
    {"id": "coin-dokkaebi", "base": "hero_surprised", "label": "비트코인 (엽전 도깨비)",
     "prompt": "New head: a friendly Korean dokkaebi goblin head with a small horn, whose face glows gold like a "
               "yeopjeon coin with a square hole on the forehead, surprised expression, wearing the gat."},
]


def key(n: str) -> str:
    return os.environ.get(n, "").strip()


def gemini_edit(img: bytes, prompt: str) -> tuple[bytes | None, str]:
    k = key("GEMINI_API_KEY")
    if not k:
        return None, "Gemini 키 없음"
    h = {"x-goog-api-key": k}
    names = [m["name"].split("/")[-1] for m in requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models", headers=h, timeout=30).json().get("models", [])]
    cands = [m for m in ("gemini-3-pro-image-preview", "gemini-2.5-flash-image", "gemini-2.5-flash-image-preview")
             if m in names] or [m for m in names if "image" in m]
    last = "이미지 모델 없음"
    for model in cands:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          headers=h, timeout=300, json={
                              "contents": [{"parts": [{"inline_data": {"mime_type": "image/png",
                                                                       "data": base64.b64encode(img).decode()}},
                                                      {"text": prompt}]}],
                              "generationConfig": {"responseModalities": ["IMAGE"]}})
        if r.status_code != 200:
            last = f"{model} HTTP {r.status_code}: {r.text[:120]}"
            continue
        for c in r.json().get("candidates", []):
            for p in c.get("content", {}).get("parts", []):
                d = p.get("inlineData") or p.get("inline_data")
                if d and d.get("data"):
                    return base64.b64decode(d["data"]), model
        last = f"{model} 그림 없이 응답(거절 가능성)"
    return None, last


def gpt_edit(img: bytes, prompt: str) -> tuple[bytes | None, str]:
    r = requests.post("https://api.openai.com/v1/images/edits", timeout=300,
                      headers={"Authorization": f"Bearer {key('OPENAI_API_KEY')}"},
                      data={"model": "gpt-image-2", "prompt": prompt, "size": "1024x1536", "quality": "medium", "n": "1"},
                      files=[("image[]", ("hero.png", io.BytesIO(img), "image/png"))])
    if r.status_code != 200:
        return None, f"gpt-image-2 HTTP {r.status_code}: {r.text[:160]}"
    return base64.b64decode(r.json()["data"][0]["b64_json"]), "gpt-image-2"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = [f"# 머리 바꾸기 시험 ({date.today()})", ""]
    for h in HEADS:
        out = OUT / f"{h['id']}.png"
        if out.exists():
            continue
        src = (PARTS / f"{h['base']}-green.png").read_bytes()
        prompt = COMMON + h["prompt"] + RULES
        t0 = time.time()
        data, who = gemini_edit(src, prompt)
        if not data:
            log.append(f"- {h['id']}: Gemini 실패 ({who}) → GPT로")
            data, who = gpt_edit(src, prompt)
        if not data:
            log.append(f"- {h['id']}: 실패 ({who})")
            continue
        Image.open(io.BytesIO(data)).convert("RGB").save(out)
        unscreen(out)
        log.append(f"- {h['id']}: {who} {time.time() - t0:.0f}초")
    sheet(log)
    (OUT / f"결과-{date.today()}.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


def sheet(log: list[str]) -> None:
    have = [h for h in HEADS if (OUT / f"{h['id']}.png").exists()]
    if not have:
        return
    f = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Pretendard-Black.otf"), 26)
    c = Image.new("RGB", (len(have) * 330 + 20, 560), (243, 235, 221))
    d = ImageDraw.Draw(c)
    for i, h in enumerate(have):
        im = Image.open(OUT / f"{h['id']}.png").convert("RGBA")
        im = im.crop(im.getbbox())
        im.thumbnail((300, 470))
        c.paste(im, (20 + i * 330 + (300 - im.width) // 2, 10), im)
        d.text((20 + i * 330, 500), h["label"], font=f, fill=(22, 20, 18))
    c.save(OUT / "0-한눈에.png")
    # 썸네일 시안: 창고 배경 + 이재용 캐리커처 → C 구성
    lee = OUT / "lee-jaeyong.png"
    if lee.exists():
        bg = Image.open(ROOT / "assets" / "art-library" / "kr-guild.jpg").convert("RGBA")
        fig = Image.open(lee).convert("RGBA")
        fig = fig.crop(fig.getbbox())
        fig.thumbnail((int(bg.width * 0.5), int(bg.height * 0.95)))
        bg.alpha_composite(fig, (int(bg.width * 0.45), bg.height - fig.height))
        tmp = OUT / "_lee-bg.png"
        bg.convert("RGB").save(tmp)
        thumb(tmp, ["삼성전자", "회장님이", "웃은", "이유는?"], "", OUT / "썸네일-이재용.png", panel="먹", side="left",
              focus=0.8)
        tmp.unlink()
        t = Image.open(OUT / "썸네일-이재용.png").convert("RGB")  # 'AI 일러스트' 표시: 그림 쪽 오른쪽 아래(잘리지 않게)
        ImageDraw.Draw(t).text((t.width - 210, t.height - 56), "AI 일러스트", font=ImageFont.truetype(
            str(ROOT / "assets" / "fonts" / "Pretendard-Black.otf"), 32), fill=(243, 235, 221),
            stroke_width=4, stroke_fill=(22, 20, 18))
        t.save(OUT / "썸네일-이재용.png")
        log.append("- 썸네일 시안: 썸네일-이재용.png")


if __name__ == "__main__":
    main()
