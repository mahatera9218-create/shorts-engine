"""썸네일 배경 사진: Pexels API (무료 상업 이용, 허용된 통로).

API 이용 조건: 글에 Pexels 링크와 작가 이름을 표시한다 ("사진: 작가 / Pexels" + 사진 주소).
선수 사진은 쓰지 않는다 (초상권). 경기장·공·배트처럼 사물·장소 위주 검색어를 쓰고, 사람이 나온 사진은 설명(alt)으로 거른다.
키는 환경 변수 PEXELS_API_KEY (GitHub Secrets). 없으면 사진 없이 그린 썸네일로 대신한다.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageStat

from market.common import ROOT, secret

SEARCH = "https://api.pexels.com/v1/search"
MUST = {"야구": "baseball", "축구": "soccer", "농구": "basketball", "골프": "golf"}  # 사진 설명에 있어야 할 말 (축구는 soccer만: football은 Pexels에서 미식축구가 섞인다, 2026-10-03)
GRAYISH = ("black and white", "black-and-white", "monochrome", "grayscale")
# 사람이 알아볼 수 있게 나온 사진은 뺀다 (2026-09-30): 모르는 사람이 그 선수처럼 보이면 오해·초상권 문제. 관중석처럼 작게 보이는 건 괜찮다
PEOPLE = ("man", "men", "woman", "women", "boy", "girl", "child", "kid", "person", "people", "player", "batter",
          "pitcher", "catcher", "coach", "umpire", "athlete", "portrait", "face", "father", "son", "team", "golfer")
QUERIES = {  # photo = 썸네일 배경 (본문은 카드뉴스라 사진을 쓰지 않는다)
    "photo": {"야구": ["baseball stadium", "baseball field", "baseball stadium night lights"],
              "축구": ["soccer stadium", "soccer field", "soccer pitch"],
              "농구": ["basketball court"], "골프": ["golf course"]},
}


def used_ids() -> set[int]:
    """이미 다른 글에 쓴 사진은 다시 쓰지 않는다."""
    out = set()
    for p in (ROOT / "posts").glob("*/photo*.json"):
        try:
            out.add(json.loads(p.read_text(encoding="utf-8"))["id"])
        except (ValueError, KeyError):
            pass
    return out


def colorful(data: bytes, min_saturation: int = 40) -> bool:
    """설명에 흑백이라고 안 적힌 흑백 사진도 있어서, 받은 사진의 평균 채도로 한 번 더 거른다."""
    im = Image.open(io.BytesIO(data)).convert("HSV").resize((64, 64))
    return ImageStat.Stat(im).mean[1] >= min_saturation


def fetch(folder: Path, sport: str, seed: str, name: str = "photo") -> dict | None:
    """folder/<name>.jpg와 <name>.json(출처)을 만든다. 키가 없거나 실패하면 None."""
    key = secret("PEXELS_API_KEY")
    if not key:
        return None
    table = QUERIES[name]
    kind = next((k for k in table if k in (sport or "")), "야구")
    queries = table[kind]
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    query = queries[h % len(queries)]
    try:
        r = requests.get(SEARCH, headers={"Authorization": key},
                         params={"query": query, "orientation": "square", "per_page": 40}, timeout=20)
        r.raise_for_status()
        must = MUST[kind] if isinstance(MUST[kind], tuple) else (MUST[kind],)
        photos = [p for p in r.json().get("photos", []) if p["id"] not in used_ids()
                  and any(w in (p.get("alt") or "").lower() for w in must)       # 종목과 상관없는 사진 빼기
                  and not any(g in (p.get("alt") or "").lower() for g in GRAYISH)  # 흑백 빼기
                  and not any(w in (p.get("alt") or "").lower().replace(",", " ").split() for w in PEOPLE)]  # 사람 빼기
        start = h % max(1, min(len(photos), 10))  # 상위 10장 안에서 글마다 다르게
        for p in photos[start:] + photos[:start]:
            img = requests.get(p["src"]["large2x"], timeout=30)
            img.raise_for_status()
            if colorful(img.content):
                break
        else:
            print(f"'{query}'에서 쓸 만한 컬러 사진을 찾지 못해 사진 없이 만듭니다")
            return None
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"사진을 받지 못해 그린 썸네일로 대신합니다: {type(e).__name__}")
        return None
    (folder / f"{name}.jpg").write_bytes(img.content)
    info = {"id": p["id"], "photographer": p.get("photographer", ""), "page": p.get("url", ""), "query": query}
    (folder / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def fetch_all(folder: Path, sport: str, seed: str) -> None:
    for name in QUERIES:
        if not (folder / f"{name}.jpg").exists():
            fetch(folder, sport, seed, name)


def credit(folder: Path) -> str:
    """본문 끝에 붙일 출처 (API 이용 조건: 작가 이름 + Pexels 링크)."""
    lines = []
    for name, label in (("photo", "대표 사진"),):
        p = folder / f"{name}.json"
        if p.exists():
            info = json.loads(p.read_text(encoding="utf-8"))
            lines.append(f"{label}: {info['photographer']} / Pexels ({info['page']})")
    return "\n".join(lines)
