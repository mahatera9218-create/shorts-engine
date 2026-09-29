"""썸네일 배경 사진: Pexels API (무료 상업 이용, 허용된 통로).

API 이용 조건: 글에 Pexels 링크와 작가 이름을 표시한다 ("사진: 작가 / Pexels" + 사진 주소).
선수 사진은 쓰지 않는다 (초상권). 경기장·공·배트처럼 사물·장소 위주 검색어를 쓴다.
키는 환경 변수 PEXELS_API_KEY (GitHub Secrets). 없으면 사진 없이 그린 썸네일로 대신한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

from market.common import ROOT, secret

SEARCH = "https://api.pexels.com/v1/search"
QUERIES = {
    "야구": ["baseball stadium", "baseball field", "baseball bat and ball", "baseball stadium night lights"],
    "축구": ["soccer stadium", "soccer ball field", "football stadium lights"],
    "농구": ["basketball court", "basketball hoop"],
    "골프": ["golf course", "golf ball"],
}


def used_ids() -> set[int]:
    """이미 다른 글에 쓴 사진은 다시 쓰지 않는다."""
    out = set()
    for p in (ROOT / "posts").glob("*/photo.json"):
        try:
            out.add(json.loads(p.read_text(encoding="utf-8"))["id"])
        except (ValueError, KeyError):
            pass
    return out


def fetch(folder: Path, sport: str, seed: str) -> dict | None:
    """folder/photo.jpg와 photo.json(출처)을 만든다. 키가 없거나 실패하면 None."""
    key = secret("PEXELS_API_KEY")
    if not key:
        return None
    kind = next((k for k in QUERIES if k in (sport or "")), "야구")
    queries = QUERIES[kind]
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    query = queries[h % len(queries)]
    try:
        r = requests.get(SEARCH, headers={"Authorization": key},
                         params={"query": query, "orientation": "square", "per_page": 40}, timeout=20)
        r.raise_for_status()
        photos = [p for p in r.json().get("photos", []) if p["id"] not in used_ids()]
        if not photos:
            return None
        p = photos[h % min(len(photos), 10)]  # 상위 10장 안에서 글마다 다르게
        img = requests.get(p["src"]["large2x"], timeout=30)
        img.raise_for_status()
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"사진을 받지 못해 그린 썸네일로 대신합니다: {type(e).__name__}")
        return None
    (folder / "photo.jpg").write_bytes(img.content)
    info = {"id": p["id"], "photographer": p.get("photographer", ""), "page": p.get("url", ""), "query": query}
    (folder / "photo.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def credit(folder: Path) -> str:
    """본문 끝에 붙일 출처 한 줄 (API 이용 조건)."""
    p = folder / "photo.json"
    if not p.exists():
        return ""
    info = json.loads(p.read_text(encoding="utf-8"))
    return f"대표 사진: {info['photographer']} / Pexels ({info['page']})"
