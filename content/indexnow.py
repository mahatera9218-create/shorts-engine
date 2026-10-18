"""IndexNow 핑: 새로 발행·수정된 글 주소를 검색엔진(네이버·빙 등)에 즉시 알린다. 비밀 값 없음(키는 공개 파일).

- 프로토콜: https://www.indexnow.org — 키 파일 web/public/<키>.txt 를 사이트 루트(https://astacgroup.com/<키>.txt)에서 확인한다.
- 네이버 서치어드바이저가 IndexNow를 지원한다(2023-07). 구글은 IndexNow를 지원하지 않는다 → 구글은 사이트맵·내부 링크로 알린다.
- 대상: 마지막 커밋에서 바뀐 web/content/posts/*.md (--new), 또는 전체 글(--all), 또는 직접 지정(--url).
- 실패해도 워크플로를 깨지 않는다(항상 종료코드 0). 하루 호출은 소량(글 발행 때만).

사용: python -m content.indexnow --new [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import requests

from market.common import ROOT

SITE = "https://astacgroup.com"
PUBLIC = ROOT / "web" / "public"
POSTS = ROOT / "web" / "content" / "posts"
ENDPOINTS = ["https://api.indexnow.org/indexnow", "https://searchadvisor.naver.com/indexnow"]


def find_key() -> str | None:
    """web/public 의 '<32자리 16진수>.txt' 파일 중 이름과 내용이 같은 것이 키."""
    for f in PUBLIC.glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", f.stem) and f.read_text(encoding="utf-8").strip() == f.stem:
            return f.stem
    return None


def slug_urls(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        m = re.match(r"web/content/posts/([^/]+)\.md$", p)
        if m:
            out.append(f"{SITE}/{m.group(1)}")
    return out


def changed_post_urls() -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", "HEAD~1", "HEAD", "--", "web/content/posts"],
                       cwd=ROOT, capture_output=True, text=True)
    return slug_urls(r.stdout.split())


def all_post_urls() -> list[str]:
    return [f"{SITE}/{f.stem}" for f in sorted(POSTS.glob("*.md"))]


def ping(urls: list[str], key: str) -> None:
    body = {"host": SITE.replace("https://", ""), "key": key, "keyLocation": f"{SITE}/{key}.txt", "urlList": urls[:100]}
    try:
        r = requests.post(ENDPOINTS[0], json=body, timeout=20, headers={"Content-Type": "application/json; charset=utf-8"})
        print(f"[IndexNow 공용] {r.status_code} ({len(urls)}개)")
    except Exception as e:  # noqa: BLE001
        print(f"[IndexNow 공용 실패] {type(e).__name__}: {e}")
    for u in urls[:20]:  # 네이버는 URL별 GET(공식 방식)
        try:
            r = requests.get(ENDPOINTS[1], params={"url": u, "key": key}, timeout=15)
            print(f"[네이버] {r.status_code} {u}")
        except Exception as e:  # noqa: BLE001
            print(f"[네이버 실패] {u}: {type(e).__name__}: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="IndexNow 핑")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--new", action="store_true", help="마지막 커밋에서 추가·수정된 글")
    g.add_argument("--all", action="store_true", help="전체 글")
    g.add_argument("--url", nargs="+", help="직접 지정")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    key = find_key()
    if not key:
        print("IndexNow 키 파일이 없습니다(web/public/<키>.txt).")
        return 0
    urls = changed_post_urls() if args.new else all_post_urls() if args.all else args.url
    if not urls:
        print("알릴 주소 없음.")
        return 0
    print("대상:", *urls, sep="\n  ")
    if not args.dry_run:
        ping(urls, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
