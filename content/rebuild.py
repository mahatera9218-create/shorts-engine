"""이미 만든 글의 이미지를 다시 그린다 (썸네일 디자인을 바꿨을 때).

사진이 없으면 Pexels에서 받고(PEXELS_API_KEY), 본문 끝에 사진 출처 한 줄을 붙인다. 숫자·본문은 바꾸지 않는다.
사용법: python -m content.rebuild [posts/폴더 ...]   (폴더를 안 주면 posts/ 아래 전부)
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from market.common import ROOT
from . import photos, receipt


def add_credit(folder: Path) -> None:
    line = photos.credit(folder)
    if not line:
        return
    body = folder / "body.txt"
    for f in (folder / "body.txt", folder / "post.md"):  # 예전 출처 줄은 지우고 새로 붙인다
        if not f.exists():
            continue
        s = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines() if "/ Pexels (" not in l)
        if f.name == "body.txt":
            s = s.rstrip() + "\n\n" + line + "\n"
        elif "\n## 출처" in s:
            s = s.replace("\n## 출처", f"\n{line}\n\n## 출처", 1)
        f.write_text(s, encoding="utf-8")


def main() -> None:
    folders = [Path(a) for a in sys.argv[1:]] or sorted(p for p in (ROOT / "posts").iterdir() if (p / "data.yaml").exists())
    for folder in folders:
        d = yaml.safe_load((folder / "data.yaml").read_text(encoding="utf-8"))
        photos.fetch_all(folder, d.get("sport", "야구"), folder.name)
        receipt.build(folder, d)
        add_credit(folder)
        print(f"{folder.name}: 이미지 다시 그림" + (" (사진 포함)" if (folder / "photo.jpg").exists() else " (사진 없음)"))


if __name__ == "__main__":
    main()
