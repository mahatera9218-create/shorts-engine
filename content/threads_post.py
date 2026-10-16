"""Threads 자동 게시: 새로 발행된 글을 하나씩 Threads에 올린다(소량·공식 API).

- 대상: web/content/posts/*.md 중 아직 안 올린 글. 올린 slug는 reports/threads-posted.json에 기록.
- 매 실행 1편만(하루 2~3회 cron = 소량). 봇 티 안 나게 글의 요약(사람이 쓴 톤)을 그대로 쓴다.
- 공식 API(graph.threads.net): 컨테이너 생성 → 게시. 토큰은 THREADS_ACCESS_TOKEN(Secrets).
- 토큰 없거나 실패하면 아무 것도 안 하고 조용히 끝낸다.

사용: python -m content.threads_post [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests

from market.common import ROOT, secret

POSTS = ROOT / "web" / "content" / "posts"
LOG = ROOT / "reports" / "threads-posted.json"
SITE = "https://astacgroup.com"
API = "https://graph.threads.net/v1.0"
HASHTAGS = {
    "tax": "#세금 #절세", "jaetech": "#재테크", "realty": "#부동산", "pension": "#연금",
}


def _front(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    d = {}
    if m:
        for line in m.group(1).splitlines():
            i = line.find(":")
            if i != -1:
                d[line[:i].strip()] = line[i + 1:].strip()
    return d


def _posted() -> set[str]:
    try:
        return set(json.loads(LOG.read_text(encoding="utf-8")).get("posted", []))
    except Exception:
        return set()


def _save(posted: set[str]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps({"posted": sorted(posted)}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")


def _next(posted: set[str]) -> tuple[str, dict] | None:
    # 날짜 최신순으로, 아직 안 올린 글 하나.
    items = []
    for f in POSTS.glob("*.md"):
        d = _front(f)
        slug = d.get("slug") or f.stem
        if slug not in posted:
            items.append((d.get("date", ""), slug, d))
    if not items:
        return None
    items.sort(reverse=True)
    _, slug, d = items[0]
    return slug, d


def compose(slug: str, d: dict) -> str:
    ex = d.get("excerpt", "").strip()
    # 중간에 잘린 요약이면 마지막 완결 문장까지만(봇 티·어색함 방지).
    if ex and ex[-1] not in "다.!?…":
        cut = max(ex.rfind("다."), ex.rfind(". "), ex.rfind("! "), ex.rfind("? "))
        if cut > 30:
            ex = ex[: cut + (2 if ex[cut] == "다" else 1)]
    tags = HASHTAGS.get(d.get("category", ""), "#재테크")
    url = f"{SITE}/{slug}"
    text = f"{ex}\n\n전체 정리 👉 {url}\n\n{tags}"
    return text[:490]


def publish_threads(text: str, token: str) -> str:
    me = requests.get(f"{API}/me", params={"fields": "id", "access_token": token}, timeout=20)
    me.raise_for_status()
    uid = me.json()["id"]
    c = requests.post(f"{API}/{uid}/threads",
                      data={"media_type": "TEXT", "text": text, "access_token": token}, timeout=30)
    c.raise_for_status()
    cid = c.json()["id"]
    p = requests.post(f"{API}/{uid}/threads_publish",
                      data={"creation_id": cid, "access_token": token}, timeout=30)
    p.raise_for_status()
    return p.json().get("id", "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Threads 자동 게시(소량)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not POSTS.exists():
        print("글 폴더 없음")
        return 0
    posted = _posted()
    nxt = _next(posted)
    if not nxt:
        print("올릴 새 글 없음(모두 게시됨).")
        return 0
    slug, d = nxt
    text = compose(slug, d)
    if args.dry_run:
        print("=== 게시 미리보기 ===\n" + text)
        return 0
    token = secret("THREADS_ACCESS_TOKEN")
    if not token:
        print("THREADS_ACCESS_TOKEN 없음 — 게시 생략.")
        return 0
    try:
        tid = publish_threads(text, token)
    except Exception as e:  # noqa: BLE001
        print(f"Threads 게시 실패: {type(e).__name__}: {e}")
        return 0
    posted.add(slug)
    _save(posted)
    print(f"[Threads 게시] {slug} → {tid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
