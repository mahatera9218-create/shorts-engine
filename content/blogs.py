"""운영 블로그 3개(경제·연예·패션) 설정 (대표 결정 2026-10-05). config/blogs.yaml을 읽는다.

지금 어느 블로그 일인지는 환경 변수 BLOG(econ·ent·fashion, 기본 econ)로 정한다 (.github/workflows/econ-flow.yml이 넘김).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from market.common import ROOT

CFG = ROOT / "config" / "blogs.yaml"


def all_blogs() -> dict[str, dict]:
    data = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    for bid, b in data.items():
        b["id"] = bid
        b["base"] = ROOT / b["dir"]
    return data


def get(bid: str | None = None) -> dict:
    blogs = all_blogs()
    return blogs[bid or current()]


def current() -> str:
    return os.environ.get("BLOG", "econ").strip() or "econ"


def by_label(label: str) -> dict | None:
    return next((b for b in all_blogs().values() if b["label"] == label), None)


def folder(b: dict, name: str) -> Path:
    return b["base"] / name
