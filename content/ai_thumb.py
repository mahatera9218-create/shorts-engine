"""조선 화풍 AI 썸네일 시험: 같은 프롬프트를 GPT Image 2와 Nano Banana Pro에 나란히 보낸다.

출력: reports/썸네일-시안/ai/<모델>-<번호>.png + 결과 보고서(md).
키는 GitHub Secrets(OPENAI_API_KEY, GEMINI_API_KEY)에서만 읽는다. 없는 모델은 건너뛴다.
"""
from __future__ import annotations

import base64
import os
import time
from datetime import date
from pathlib import Path

import requests

OUT = Path("reports/썸네일-시안/ai")

STYLE = (
    "Square 1:1 blog thumbnail. A reinterpretation of Joseon-dynasty Korean genre painting "
    "in the manner of Kim Hong-do (danwon pungsokdo) and Korean folk painting (minhwa): "
    "ink brush outlines, light ochre/indigo/vermilion washes, aged hanji paper texture, "
    "lively everyday figures in hanbok. Clean, bold composition readable at 108px on a phone. "
    "No modern company logos, no real people's faces, no watermark, no signature, no extra text "
    "besides the title. "
)

TOPICS = [
    {
        "slug": "1-금급락",
        "title": "금값이 하루에 5% 빠졌다, 왜?",
        "scene": (
            "Scene: a big friendly-fierce minhwa tiger leaping down a mountain slope, scattering "
            "gold ingots (geumgoe) from a toppled merchant's A-frame jige; a startled magpie on a "
            "pine branch. Leave the lower 35% as plain hanji paper for the title."
        ),
    },
    {
        "slug": "2-코스피나스닥",
        "title": "코스피 vs 나스닥, 오늘은 누가 이겼나?",
        "scene": (
            "Scene: Kim Hong-do style ssireum wrestling match, two wrestlers grappling in the center, "
            "a circle of cheering spectators; one wrestler wears a small red sash, the other a blue "
            "sash. Leave the lower 35% as plain hanji paper for the title."
        ),
    },
    {
        "slug": "3-파킹통장CMA",
        "title": "파킹통장 vs CMA, 이자는 어디가 더 붙을까?",
        "scene": (
            "Scene: Kim Hong-do style village seodang classroom; a kindly teacher with a long pipe, "
            "students in hanbok, one boy holding up two coin pouches (yeopjeon strings) to compare. "
            "Leave the lower 35% as plain hanji paper for the title."
        ),
    },
]


def prompt_for(t: dict) -> str:
    return (
        STYLE
        + t["scene"]
        + f' Title text, exactly as written, in bold black Korean brush-calligraphy lettering, '
        f'two lines, centered in the lower area: "{t["title"]}". '
        "Every Hangul character must be correct and fully legible. "
        "Add a small red square seal stamp (nakgwan) with the single Hangul character \"억\" "
        "in the bottom-right corner."
    )


def gpt_image(prompt: str, key: str) -> bytes:
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-image-2", "prompt": prompt, "size": "1024x1024", "quality": "high", "n": 1},
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return base64.b64decode(r.json()["data"][0]["b64_json"])


def nano_banana(prompt: str, key: str) -> bytes:
    r = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}},
        },
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    for cand in r.json().get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            data = part.get("inlineData") or part.get("inline_data")
            if data and data.get("data"):
                return base64.b64decode(data["data"])
    raise RuntimeError("응답에 그림이 없음")


MODELS = [
    ("gpt", "GPT Image 2 (high)", "OPENAI_API_KEY", gpt_image, "약 $0.21"),
    ("nano", "Nano Banana Pro", "GEMINI_API_KEY", nano_banana, "약 $0.13"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 조선 화풍 AI 썸네일 시험 ({date.today()})",
        "",
        "같은 프롬프트를 두 모델에 보내 나란히 비교한 결과예요. 그림 속 숫자는 예시예요.",
        "",
    ]
    for code, name, env, fn, cost in MODELS:
        key = os.environ.get(env, "").strip()
        lines += [f"## {name}", ""]
        if not key:
            lines += [f"- 키({env})가 없어 건너뜀", ""]
            print(f"[{code}] 키 없음, 건너뜀")
            continue
        for t in TOPICS:
            path = OUT / f"{code}-{t['slug']}.png"
            t0 = time.time()
            try:
                path.write_bytes(fn(prompt_for(t), key))
                sec = time.time() - t0
                lines.append(f"- {t['title']} → `{path.name}` ({sec:.0f}초, {cost})")
                print(f"[{code}] {t['slug']} ok {sec:.0f}s")
            except Exception as e:  # 실패도 그대로 보고
                msg = str(e).replace(key, "***")
                lines.append(f"- {t['title']} → 실패: {msg}")
                print(f"[{code}] {t['slug']} 실패: {msg}")
        lines.append("")
    lines += ["## 보낸 프롬프트", ""]
    for t in TOPICS:
        lines += [f"### {t['slug']}", "", "```", prompt_for(t), "```", ""]
    (OUT / f"결과-{date.today()}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
