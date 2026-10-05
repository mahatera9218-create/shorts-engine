"""경제 글 그림 그리기 (2026-10-05): 글 폴더의 art.yaml대로 썸네일·본문 그림을 GPT Image 2 '고화질'로 그린다.

- 대표 피드백 '사진 화질이 너무 깨짐' → 발행용 그림은 high 품질, PNG 그대로(다시 압축하지 않음).
  본문 그림은 가로 1536x1024(네이버 본문 폭을 꽉 채움), 썸네일은 1024x1024.
- art.yaml: [{file, size, prompt, ref(선택: 참고 그림 경로)}]. 이미 있는 파일은 다시 그리지 않는다(돈 아낌).
- 공통 화풍·한국 전통미 원칙은 STYLE에 (DECISIONS 2026-10-05).
사용법: python -m content.post_art [글 폴더 ...]  (안 주면 econ/posts/ 아래 art.yaml이 있는 글 전부)
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import requests
import yaml

from market.common import ROOT

STYLE = ("Korean traditional art direction: a reinterpretation of Joseon-dynasty genre painting (Kim Hong-do) and "
         "Korean minhwa, with the flat bold color palette of a Korean hwatu flower card (vermilion red, black ink, "
         "cream hanji, pine green, gold). Crisp clean ink outlines, smooth flat color areas, no grain, no noise, no "
         "blur, high detail. Distinctly Korean elements only (hanbok, gat, thatched and tiled roofs, market stalls, "
         "yeopjeon coins, jogakbo patterns); nothing Chinese or Japanese. Every person is a fictional Joseon "
         "townsperson with a fully drawn, expressive face (eyes, eyebrows, nose, mouth) - never blank or faceless; "
         "no portraits of real, identifiable people, no logos, no watermark, no signature. ")


def draw(folder: Path) -> list[str]:
    spec = folder / "art.yaml"
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    log = []
    if not spec.exists() or not key:
        return ["art.yaml 또는 OPENAI_API_KEY 없음"]
    hdr = {"Authorization": f"Bearer {key}"}
    for a in yaml.safe_load(spec.read_text(encoding="utf-8")) or []:
        out = folder / a["file"]
        if out.exists():
            continue
        body = {"model": "gpt-image-2", "prompt": STYLE + a["prompt"], "size": a.get("size", "1536x1024"),
                "quality": a.get("quality", "high"), "n": 1}
        t0 = time.time()
        ref = ROOT / a["ref"] if a.get("ref") else None
        if ref and ref.exists():
            with ref.open("rb") as f:
                r = requests.post("https://api.openai.com/v1/images/edits", headers=hdr, timeout=600,
                                  data={**body, "n": "1"}, files=[("image[]", (ref.name, f, "image/png"))])
        else:
            r = requests.post("https://api.openai.com/v1/images/generations", headers=hdr, json=body, timeout=600)
        if r.status_code != 200:
            log.append(f"{a['file']} 실패 HTTP {r.status_code}: {r.text[:200]}")
            continue
        out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
        log.append(f"{a['file']} {body['size']} {body['quality']} {time.time() - t0:.0f}초")
    return log


def main() -> None:
    folders = [Path(x) for x in sys.argv[1:]] or (
        sorted(p.parent for p in (ROOT / "econ" / "posts").glob("*/art.yaml"))
        + sorted(p.parent for p in (ROOT / "assets" / "brand").glob("*/art.yaml")))
    for f in folders:
        for line in draw(f):
            print(f"{f.name}: {line}")
        if f.name == "cover":
            cover_preview(f)


def cover_preview(folder: Path) -> None:
    """블로그 상단 커버 미리보기: PC는 3:2 그대로, 모바일은 가운데 정사각형만 보인다(2026-10-05 조사).
    → 0-미리보기.jpg (후보마다 왼쪽 PC, 오른쪽 모바일 가운데 자르기)."""
    from PIL import Image, ImageDraw
    files = sorted(x for x in folder.glob("*.png") if not x.name.startswith("0-"))
    if not files:
        return
    W, H = 1200, 400
    sheet = Image.new("RGB", (W, H * len(files)), (255, 255, 255))
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB")
        pc = im.resize((570, 380), Image.LANCZOS)
        s = min(im.size)
        sq = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2)).resize((380, 380))
        sheet.paste(pc, (10, i * H + 10))
        d = ImageDraw.Draw(sheet)
        x0 = 10 + (570 - 380) // 2
        d.rectangle((x0, i * H + 10, x0 + 380, i * H + 390), outline=(200, 30, 40), width=3)
        sheet.paste(sq, (W - 400, i * H + 10))
        d.text((600, i * H + 180), f.stem, fill=(0, 0, 0))
    sheet.save(folder / "0-미리보기.jpg", quality=92)


if __name__ == "__main__":
    main()
