"""발행 자동 확인 (2026-09-30): 네이버 블로그 공식 RSS로 실제 공개된 글을 찾아 후보 글에 표시한다.

- 통로: https://rss.blog.naver.com/<아이디>.xml (네이버가 제공하는 공개 RSS, 글 제목·링크·발행 시각만 읽는다)
- 짝 찾기: RSS 글 제목이 후보의 제목 중 하나와 같으면 그 후보. 대표가 제목을 다듬었으면
  "발행일 이전에 만든 후보 중 선수 짧은 이름이 제목에 있는 가장 최근 것".
- 찾으면 posts/<글>/status.yaml에 used + 네이버 글 주소(url)를 남긴다. 이미 used면 주소만 채운다.
- 매일 아침 자동 글쓰기가 지난 후보를 지우기 전에 돈다 (발행했는데 버튼을 깜빡한 글이 지워지지 않게).
사용법: python -m content.published            (RSS를 읽어 표시)
       python -m content.published --file x.xml (저장한 RSS로 시험)
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

from market.common import ROOT, load_yaml
from . import desk, mark

POSTS = ROOT / "posts"
KST = ZoneInfo("Asia/Seoul")


def rss_url() -> str:
    blog = load_yaml("blogs.yaml")["blogs"][0]["url"].rstrip("/")
    return f"https://rss.blog.naver.com/{blog.rsplit('/', 1)[1]}.xml"


def items(xml: str) -> list[dict]:
    """RSS → [{title, url, at(한국 시각 'YYYY-MM-DD HH:MM')}]. 주소의 추적용 꼬리(?fromRss=…)는 뗀다."""
    out = []
    for it in ET.fromstring(xml).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").split("?")[0].strip()
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            at = ""
        if title and link:
            out.append({"title": title, "url": link, "at": at})
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _short_name(folder: Path) -> str:
    f = folder / "data.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return (d or {}).get("short_name") or (d or {}).get("player", "").split(" ")[0]


def match(item: dict, folders: list[Path]) -> Path | None:
    day = item["at"][:10] or "9999-99-99"
    cands = [f for f in folders if f.name[:10] <= day and mark.status(f).get("status") != "rejected"]
    t = _norm(item["title"])
    for f in cands:  # 1) 제목이 그대로
        p = desk.parse(f)
        if p and any(_norm(x["text"]) == t for x in p["titles"]):
            return f
    named = [f for f in cands if (n := _short_name(f)) and _norm(n) in t]  # 2) 선수 이름
    return max(named, key=lambda f: f.name) if named else None


def apply(found: list[dict]) -> list[str]:
    folders = sorted(x for x in POSTS.iterdir() if x.is_dir() and (x / "post.md").exists()) if POSTS.exists() else []
    known = {mark.status(f).get("url") for f in folders}
    done = []
    for it in found:
        if it["url"] in known:
            continue
        f = match(it, folders)
        if not f:
            continue
        st = mark.status(f)
        st.update({"status": "used", "at": st.get("at") or it["at"], "url": it["url"], "naver_title": it["title"]})
        (f / "status.yaml").write_text(yaml.safe_dump(st, allow_unicode=True), encoding="utf-8")
        known.add(it["url"])
        done.append(f"{f.name} ← {it['title']} ({it['url']})")
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()
    try:
        xml = Path(a.file).read_text(encoding="utf-8") if a.file else \
            requests.get(rss_url(), timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
        found = items(xml)
    except (requests.RequestException, ET.ParseError) as e:
        print(f"발행 확인: RSS를 읽지 못함 ({type(e).__name__}) — 버튼 표시만 씁니다")
        sys.exit(0)
    done = apply(found)
    now = datetime.now(KST).strftime("%m-%d %H:%M")
    print(f"발행 확인 ({now}): RSS 글 {len(found)}편, 새로 표시 {len(done)}편" + "".join(f"\n- {x}" for x in done))


if __name__ == "__main__":
    main()
