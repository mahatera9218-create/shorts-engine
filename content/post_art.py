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
         "yeopjeon coins, jogakbo patterns); nothing Chinese or Japanese. No real people's faces, no logos, no "
         "watermark, no signature. ")


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
    folders = [Path(x) for x in sys.argv[1:]] or sorted(p.parent for p in (ROOT / "econ" / "posts").glob("*/art.yaml"))
    for f in folders:
        for line in draw(f):
            print(f"{f.name}: {line}")


if __name__ == "__main__":
    main()
