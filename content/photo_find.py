"""인물 사진 후보 찾기 — 네이버 공식 이미지 검색 API(API HUB /search/v1/image)로 원본 이미지 주소를 받아 발행 도우미에 띄운다.

대표 결정 2026-10-06: 실존 인물은 그리지 않고 실제 사진을 대표가 직접 넣고 본문 끝에 출처를 적는다.
네이버 검색 화면 링크는 휴대폰에서 사진 저장이 안 돼서, 검색 API가 주는 '원본 이미지 주소'를 바로 열게 한다.
우리는 사진을 받아 저장하지 않는다(주소·작은 미리보기만 보여 줌). 저장은 대표가 원본을 열어 직접 한다.
"""
from __future__ import annotations

import html
import re
import urllib.parse

from market.common import load_yaml, request_json, secret

TAG = re.compile(r"<[^>]+>")
MIN_W = 500  # 너무 작은 사진은 블로그에 못 씀


def _hub() -> tuple[str, dict] | None:
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    base = load_yaml("global.yaml")["endpoints"]["naver_hub"]["base"].rstrip("/")
    return base + "/search/v1/image", {"X-NCP-APIGW-API-KEY-ID": secret("NCP_APIGW_API_KEY_ID"),
                                       "X-NCP-APIGW-API-KEY": secret("NCP_APIGW_API_KEY")}


def host(url: str) -> str:
    h = urllib.parse.urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def find(query: str, n: int = 6) -> list[dict]:
    """[{link(원본), thumb(미리보기), title, host, w, h}] — 큰 사진 먼저. 키가 없거나 실패하면 []."""
    hub = _hub()
    if not hub or not query:
        return []
    url, headers = hub
    try:
        data = request_json("GET", url, headers=headers,
                            params={"query": query, "display": 30, "sort": "sim", "filter": "large"})
    except Exception as e:  # 사진 후보는 없어도 도우미는 떠야 한다
        print(f"  사진 후보 실패 ({query}): {str(e)[:260]}")
        return []
    out, seen = [], set()
    for it in data.get("items", []):
        link = it.get("link") or ""
        if not link.startswith("http") or link in seen:
            continue
        w, h = int(it.get("sizewidth") or 0), int(it.get("sizeheight") or 0)
        if w and w < MIN_W:
            continue
        seen.add(link)
        out.append({"link": link, "thumb": it.get("thumbnail") or link, "w": w, "h": h, "host": host(link),
                    "title": html.unescape(TAG.sub("", it.get("title", ""))).strip()[:60]})
        if len(out) >= n:
            break
    print(f"  사진 후보 {len(out)}장: {query}")
    return out
