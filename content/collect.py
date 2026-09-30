"""마케터 동시 글쓰기 모으기 (2026-10-01): 마케터마다 따로 돈 작업의 결과(아티팩트)를 저장소 한곳에 합친다.

각 작업은 posts/<오늘>-*/ 폴더와, 여럿이 같이 고치는 파일(연봉 못 찾은 선수 장부, 선수 사진 장부, 비용 기록)을 올린다.
- 글 폴더: 그대로 복사 (같은 폴더면 덮어씀)
- config/skip_players.yaml, config/player_photos.yaml: 선수 이름으로 합침 (skip은 더 늦은 날짜)
- reports/costs.csv: 저장소에 없는 줄만 뒤에 붙임
그 뒤 지난 초안 정리(다시 뽑기가 아닐 때)와 글 목록(posts/README.md)을 새로 만든다.
사용법: python -m content.collect <아티팩트 폴더> [--again]
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

import yaml

from market.common import ROOT

POSTS = ROOT / "posts"
BOOKS = {"skip": ROOT / "config" / "skip_players.yaml", "photos": ROOT / "config" / "player_photos.yaml"}
COSTS = ROOT / "reports" / "costs.csv"


def _load(f: Path) -> dict:
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def _head(f: Path) -> str:
    """파일 맨 위 설명 주석 (합친 뒤에도 남긴다)."""
    lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    return "".join(l + "\n" for l in lines if l.startswith("#")) if lines and lines[0].startswith("#") else ""


def merge_books(arts: list[Path]) -> None:
    for key, base in BOOKS.items():
        book, head = _load(base), _head(base)
        for a in arts:
            f = a / base.relative_to(ROOT)
            for name, v in _load(f).items():
                if key == "skip" and name in book and str(book[name].get("until", "")) > str(v.get("until", "")):
                    continue
                if key == "photos" and name in book:
                    continue  # 사진 장부는 먼저 있던 판정을 지킨다 (대표가 none으로 고친 것 포함)
                book[name] = v
        if book:
            base.parent.mkdir(parents=True, exist_ok=True)
            base.write_text((head or _head(next((a / base.relative_to(ROOT) for a in arts
                                                  if (a / base.relative_to(ROOT)).exists()), base)))
                            + yaml.safe_dump(book, allow_unicode=True, sort_keys=True), encoding="utf-8")


def merge_costs(arts: list[Path]) -> int:
    have = COSTS.read_text(encoding="utf-8").splitlines() if COSTS.exists() else []
    seen, added = set(have), []
    for a in arts:
        f = a / COSTS.relative_to(ROOT)
        for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
            if line not in seen:
                seen.add(line)
                added.append(line)
    if added:
        COSTS.parent.mkdir(parents=True, exist_ok=True)
        COSTS.write_text("\n".join(have + added) + "\n", encoding="utf-8")
    return len(added)


def copy_posts(arts: list[Path]) -> list[str]:
    got = []
    for a in arts:
        for d in sorted((a / "posts").glob("*")) if (a / "posts").exists() else []:
            if d.is_dir():
                shutil.copytree(d, POSTS / d.name, dirs_exist_ok=True)
                got.append(d.name)
    return got


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arts")
    ap.add_argument("--again", action="store_true")
    a = ap.parse_args()
    root = Path(a.arts)
    arts = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    got = copy_posts(arts)
    merge_books(arts)
    n = merge_costs(arts)
    from .autopost import reset_drafts, write_index
    gone = [] if a.again else reset_drafts(date.today().isoformat())
    write_index()
    print(f"모으기: 마케터 결과 {len(arts)}개 · 글 폴더 {len(set(got))}개 · 비용 기록 {n}줄"
          + (f" · 지난 초안 {len(gone)}편 정리" if gone else ""))


if __name__ == "__main__":
    main()
