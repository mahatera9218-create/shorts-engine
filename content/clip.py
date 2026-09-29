"""네이버 클립용 세로 영상: 블로그 글의 카드를 9:16 영상(약 20초)으로 이어 붙인다 (대표 결정 2026-09-30).

- 재료는 그 글의 카드 이미지뿐 (직접 계산한 숫자로 그린 그림). 경기 영상·남의 영상·AI 목소리·음악은 쓰지 않는다.
- 순서는 본문 사진 순서 그대로: 썸네일 → 퀴즈(3·2·1 카운트다운) → 정답 → 표 … → 마지막 안내 화면.
- 결과: posts/<글>/clip.mp4, clip.txt (클립 설명 + 해시태그). 발행 도우미 페이지에 저장·복사 버튼이 생긴다.
- ffmpeg가 필요하다 (GitHub Actions 우분투는 apt로 설치, 로컬은 imageio-ffmpeg도 된다).

사용법: python -m content.clip [posts/폴더 ...]   (폴더를 안 주면 posts/ 아래 전부)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from market.common import ROOT
from . import desk, photos
from .brand import center_text, fit, font

W, H = 1080, 1920
BG = (14, 17, 26)
GOLD = (245, 190, 40)
WHITE = (245, 245, 245)
GRAY = (150, 158, 175)
RED = (217, 54, 54)
BLOG = "억소리 나는 스포츠"
SECONDS = {"퀴즈": 1.5, "정답": 3.0, "첫문단아래": 2.5}  # 그 밖의 카드는 3.5초
COUNTDOWN = 3
OUTRO = 2.5
MAX_TAGS = 8


def ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def frame(card: Image.Image, hook: str, foot: str = "", badge: str = "") -> Image.Image:
    """세로 화면 한 장: 위에 후킹 문구, 가운데 카드, 아래 안내."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    center_text(d, (W / 2, 150), BLOG, font("b", 34), GRAY)
    lines = wrap(d, hook, 2)
    for i, ln in enumerate(lines):
        center_text(d, (W / 2, 290 + i * 120 - (len(lines) - 1) * 60), ln, fit(d, ln, "display", 96, W * 0.9), WHITE)
    im.paste(card.convert("RGB").resize((W, W)), (0, 440))
    if badge:
        d.ellipse((W / 2 - 110, 1560, W / 2 + 110, 1780), fill=RED)
        center_text(d, (W / 2, 1668), badge, font("display", 150), WHITE)
    elif foot:
        center_text(d, (W / 2, 1680), foot, fit(d, foot, "b", 48, W * 0.9), GOLD)
    return im


def wrap(d: ImageDraw.ImageDraw, text: str, n: int) -> list[str]:
    """후킹 문구를 한두 줄로 (띄어쓰기에서 가장 균형 있게 자른다)."""
    words = text.split()
    if len(words) < 2 or d.textbbox((0, 0), text, font=font("display", 96))[2] <= W * 0.9:
        return [text]
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])][:n]


def outro() -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    center_text(d, (W / 2, 760), "계산 과정·출처는", font("display", 90), WHITE)
    center_text(d, (W / 2, 890), "블로그에", font("display", 90), WHITE)
    center_text(d, (W / 2, 1060), BLOG, font("display", 76), GOLD)
    center_text(d, (W / 2, 1200), "매일 새 몸값 퀴즈", font("b", 46), GRAY)
    return im


def scenes(folder: Path, p: dict) -> list[tuple[Image.Image, float]]:
    hook = next((t["text"] for t in p["titles"] if t["best"]), p["titles"][0]["text"] if p["titles"] else "")
    out = []
    for x in p["images"]:
        f = folder / x["file"]
        if not f.exists():
            continue
        card = Image.open(f)
        if x["label"] == "퀴즈":
            out.append((frame(card, hook, "정답은 몇 번?"), SECONDS["퀴즈"]))
            out += [(frame(card, hook, badge=str(k)), 1.0) for k in range(COUNTDOWN, 0, -1)]
        else:
            out.append((frame(card, hook), SECONDS.get(x["label"], 3.5)))
    if out:
        out.append((outro(), OUTRO))
    return out


def caption(folder: Path, p: dict) -> str:
    """클립 설명: 제목 한 줄 + 블로그 안내 + 사진 출처(있으면) + 해시태그."""
    hook = next((t["text"] for t in p["titles"] if t["best"]), p["titles"][0]["text"] if p["titles"] else "")
    tags = " ".join("#" + t.replace(" ", "") for t in (p["tags"] + ["몸값퀴즈", "스포츠"])[:MAX_TAGS])
    credit = photos.credit(folder)
    return "\n\n".join(x for x in [hook, f"정답 맞히셨나요? 계산 과정과 출처는 블로그 '{BLOG}'에 있어요.",
                                   credit, tags] if x) + "\n"


def make(folder: Path) -> str:
    """clip.mp4 · clip.txt를 만든다. 결과 한 줄을 돌려준다 (실패해도 글쓰기는 멈추지 않는다)."""
    p = desk.parse(folder)
    if not p or not p["images"]:
        return "클립: 글·이미지가 없어 건너뜀"
    exe = ffmpeg()
    if not exe:
        return "클립: ffmpeg가 없어 영상을 만들지 못함"
    sc = scenes(folder, p)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        lines = []
        for i, (im, sec) in enumerate(sc):
            im.save(t / f"{i:02d}.png")
            lines += [f"file '{i:02d}.png'", f"duration {sec}"]
        lines.append(f"file '{len(sc) - 1:02d}.png'")  # concat은 마지막 장을 한 번 더 적어야 길이가 맞는다
        (t / "list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        total = sum(s for _, s in sc)
        cmd = [exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(t / "list.txt"),
               "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",  # 무음 소리 트랙 (소리 없는 영상을 거부하는 곳 대비)
               "-t", f"{total}", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
               "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(folder / "clip.mp4")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            return f"클립: 영상 만들기 실패 ({r.stderr.strip()[-200:]})"
    (folder / "clip.txt").write_text(caption(folder, p), encoding="utf-8")
    return f"클립: 세로 영상 {total:.0f}초 완성"


def main() -> None:
    folders = [Path(a) for a in sys.argv[1:]] or sorted(p for p in (ROOT / "posts").iterdir() if (p / "post.md").exists())
    for f in folders:
        print(f"{f.name}: {make(f)}")


if __name__ == "__main__":
    main()
