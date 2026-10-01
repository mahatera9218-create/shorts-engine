"""대표가 도우미에서 고친 제목·본문을 글에 반영한다 (대표 요청 2026-09-30).

도우미 글 화면에서 제목·문단을 바로 고칠 수 있다 (그 휴대폰에 자동 저장, 복사 버튼은 고친 글을 복사).
[✏️ 고친 내용 저장]을 누르면 제목이 "[수정] <글 폴더>"인 이슈 작성 화면이 열리고, 본문에 고친 것만 담긴다:

    제목: 새 제목
    [문단 3]
    새 문단 내용

Create를 누르면 워크플로(desk-button.yml)가 이 모듈로
- post.md의 추천(★) 제목, body.txt의 그 문단을 바꾸고 (도우미·발행 확인이 고친 제목을 쓴다)
- posts/<글>/edits.md에 원래 글 → 고친 글을 남긴다 (대표가 어떻게 고치는지 모아 글쓰기 규칙에 반영)
사용법: python -m content.edits --title "[수정] 2026-10-01-life-이정후" --body-file body.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from market.common import ROOT
from .mark import FOLDER

POSTS = ROOT / "posts"
TITLE = re.compile(r"^\[수정\]\s*(\S+)\s*$")
BLOCK = re.compile(r"^\[문단 (\d+)\]\s*$", re.M)
FOOTER = "아래 초록색 Create 버튼만 누르면 됩니다."  # 도우미가 붙이는 안내 (desk.py saveEdits와 같게)
STAR = re.compile(r"^(\d+\.\s+★\s+)(.+?)(\s+—\s+\S+)$", re.M)


def parse(body: str) -> tuple[str | None, dict[int, str]]:
    """이슈 본문 → (새 제목 또는 None, {문단 번호: 새 내용}). 문단 번호는 도우미 화면 순서(0부터, 사진 자리 포함)."""
    body = body.replace("\r\n", "\n").replace(FOOTER, "")
    title = re.search(r"^제목:[ \t]*(.+)$", body.split("[문단", 1)[0], re.M)
    parts = BLOCK.split(body)
    blocks = {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return (title.group(1).strip() if title else None), {k: v for k, v in blocks.items() if v}


def apply(folder: Path, title: str | None, blocks: dict[int, str]) -> list[str]:
    """고친 것을 반영하고, 바뀐 것 목록을 돌려준다. 사진 자리([이미지 …]) 문단은 고치지 않는다."""
    done, log = [], []
    md = folder / "post.md"
    t = md.read_text(encoding="utf-8")
    m = STAR.search(t)
    if title and m and m.group(2) != title:
        t = t[:m.start(2)] + title + t[m.end(2):]
        md.write_text(t, encoding="utf-8")
        done.append("제목")
        log += [f"- 제목: {m.group(2)}", f"  → {title}"]
    bf = folder / "body.txt"
    if blocks and bf.exists():
        paras = [p.strip() for p in bf.read_text(encoding="utf-8").strip().split("\n\n") if p.strip()]
        for i, text in sorted(blocks.items()):
            if not 0 <= i < len(paras) or paras[i].startswith(("[이미지 ", "[표 ", "[상품 자리")) or paras[i] == text:
                continue
            log += [f"- 문단 {i}: {paras[i]}", f"  → {text}"]
            paras[i] = text
            done.append(f"문단 {i}")
        bf.write_text("\n\n".join(paras) + "\n", encoding="utf-8")
    if log:
        now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
        ef = folder / "edits.md"
        head = "" if ef.exists() else "# 대표가 고친 곳 (원래 → 고친 글, 글쓰기 규칙 개선용)\n"
        ef.write_text((ef.read_text(encoding="utf-8") if ef.exists() else head) + f"\n## {now}\n" + "\n".join(log) + "\n",
                      encoding="utf-8")
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    a = ap.parse_args()
    m = TITLE.match(a.title.strip())
    if not m or not FOLDER.match(m.group(1)) or not (POSTS / m.group(1) / "post.md").exists():
        print(f"형식이 다르거나 없는 글: {a.title}")
        sys.exit(1)
    title, blocks = parse(Path(a.body_file).read_text(encoding="utf-8"))
    done = apply(POSTS / m.group(1), title, blocks)
    print(f"반영: {', '.join(done) if done else '바뀐 것 없음'}")


if __name__ == "__main__":
    main()
