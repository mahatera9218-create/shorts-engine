"""발행 도우미 버튼 처리: 글에 "발행 완료" / "다시 뽑기(버림)" 표시를 남긴다 (대표 결정 2026-09-30).

발행 도우미 페이지는 정적 페이지라 키를 둘 수 없다 → 버튼이 제목이 채워진 GitHub 이슈 작성 화면을 열고,
대표가 [Create]를 누르면 워크플로(.github/workflows/desk-button.yml)가 이 모듈로 표시를 남긴다.

- posts/<글>/status.yaml: {status: used | rejected, at: 한국 시간}
- used: 도우미 목록에서 "발행한 글"로 내려가고, 글 화면에 "이미 발행함" 경고 (중복 발행 방지)
- rejected: 목록에서 숨김. 워크플로가 이어서 다른 선수·테마로 새 글을 쓴다 (autopost --again)

사용법: python -m content.mark --title "[발행완료] 2026-09-29-오타니-영수증"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from market.common import ROOT

POSTS = ROOT / "posts"
ACTIONS = {"발행완료": "used", "다시뽑기": "rejected"}
TITLE = re.compile(r"^\[(발행완료|다시뽑기)\]\s*(\S+)\s*$")
FOLDER = re.compile(r"^\d{4}-\d{2}-\d{2}-[\w가-힣-]+$")


def parse_title(title: str) -> tuple[str, str] | None:
    """이슈 제목 → (used|rejected, 글 폴더 이름). 형식이 다르거나 없는 글이면 None."""
    m = TITLE.match(title.strip())
    if not m or not FOLDER.match(m.group(2)) or not (POSTS / m.group(2) / "post.md").exists():
        return None
    return ACTIONS[m.group(1)], m.group(2)


def status(folder: Path) -> dict:
    f = folder / "status.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def mark(name: str, action: str) -> None:
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    (POSTS / name / "status.yaml").write_text(yaml.safe_dump({"status": action, "at": now}, allow_unicode=True),
                                              encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    a = ap.parse_args()
    got = parse_title(a.title)
    if not got:
        print("형식이 다르거나 없는 글입니다.")
        sys.exit(1)
    action, name = got
    mark(name, action)
    print(f"{name}: {action}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"action={action}\nfolder={name}\n")


if __name__ == "__main__":
    main()
