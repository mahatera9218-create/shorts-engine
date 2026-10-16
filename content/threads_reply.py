"""Threads 댓글 후보 찾기: 우리 글 주제와 관련된 공개 글을 공식 키워드 검색으로 찾고, 댓글 초안을 만든다.

- 공식 API만 사용: GET graph.threads.net/v1.0/keyword_search (threads_keyword_search 권한 필요).
- 자동 댓글은 달지 않는다. 낯선 사람 글에 자동으로 링크 댓글을 다는 건 스팸·계정 제재 위험이 커서(DECISIONS
  2026-10-16: 외부 자동 홍보는 Threads '게시'만 자동) 후보와 초안만 reports/threads-reply-queue.md 에 모으고,
  대표가 링크를 열어 직접 붙여넣는다(하루 소량).
- 초안은 '질문에 먼저 도움이 되는 답'이 본문, 링크는 질문이 정보 요청일 때만 마지막에 한 줄(상업 홍보 티 금지).
  가짜 경험·세무사 사칭·투자 권유 금지. 본 글과 무관하면 건너뛴다.
- 토큰(THREADS_ACCESS_TOKEN)·ANTHROPIC_API_KEY 없으면 조용히 끝낸다. 이미 본 글은 reports/threads-reply-seen.json.

사용: python -m content.threads_reply [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from market.common import ROOT, secret

POSTS = ROOT / "web" / "content" / "posts"
SEEN = ROOT / "reports" / "threads-reply-seen.json"
QUEUE = ROOT / "reports" / "threads-reply-queue.md"
SITE = "https://astacgroup.com"
API = "https://graph.threads.net/v1.0"
KST = timezone(timedelta(hours=9))
MAX_PER_RUN = 8
KEYWORDS_PER_RUN = 4

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "relevant": {"type": "boolean"},
                       "slug": {"type": "string"}, "reply": {"type": "string"}},
        "required": ["id", "relevant", "slug", "reply"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False,
}


def load_posts() -> list[dict]:
    out = []
    for f in sorted(POSTS.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
        d = {}
        if m:
            for line in m.group(1).splitlines():
                i = line.find(":")
                if i != -1:
                    d[line[:i].strip()] = line[i + 1:].strip()
        d.setdefault("slug", f.stem)
        out.append(d)
    return out


def keywords_for(posts: list[dict], day: int) -> list[str]:
    """글 제목에서 검색어를 뽑는다(앞 단어 2~3개). 날짜로 돌려가며 소량만 검색."""
    kws = []
    for p in posts:
        t = re.sub(r"[｜|(（].*$", "", p.get("title", "")).strip()
        t = re.sub(r"\b20\d\d(년)?\s*(기준)?\b", "", t).strip()
        if t:
            kws.append(" ".join(t.split()[:3]))
    if not kws:
        return []
    start = (day * KEYWORDS_PER_RUN) % len(kws)
    rot = kws[start:] + kws[:start]
    return rot[:KEYWORDS_PER_RUN]


def search(q: str, token: str) -> list[dict]:
    r = requests.get(f"{API}/keyword_search", timeout=30, params={
        "q": q, "search_type": "TOP", "fields": "id,text,permalink,username,timestamp",
        "access_token": token})
    r.raise_for_status()
    return r.json().get("data", [])


def _seen() -> set[str]:
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")).get("seen", []))
    except Exception:
        return set()


def _save_seen(s: set[str]) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"seen": sorted(s)[-2000:]}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def draft(llm, cands: list[dict], posts: list[dict]) -> list[dict]:
    catalog = "\n".join(f"- {p['slug']}: {p.get('title', '')}" for p in posts)
    system = [
        "너는 세무·절세·연금 정보 사이트 'Yield Briefing'의 Threads 담당자다. 아래 공개 글 각각에 대해 우리 글"
        "이 실제로 도움이 되는지 판단하고 댓글 초안을 쓴다.\n"
        "- relevant=false: 우리 글 주제와 무관·광고성·논쟁/정치·투자 종목 추천·개인정보가 많은 글. reply는 빈 문자열.\n"
        "- relevant=true: reply는 한국어 2~3문장. 질문에 먼저 도움이 되는 사실을 쓰고(숫자는 모르면 단정하지 말고"
        " '국세청 126 확인 권고'), 정보 요청일 때만 마지막 줄에 우리 글 링크 1개를 붙인다. slug에 그 글의 slug.\n"
        "- 금지: 가짜 경험·후기('저도 환급받았어요'), 세무사/전문가 사칭, 투자 권유, 과장, 홍보 문구.\n"
        f"우리 글 목록:\n{catalog}"]
    body = "\n".join(f"[{c['id']}] {c['text'][:400]}" for c in cands)
    out = llm.ask_json(system, f"판단·초안 대상:\n{body}", SCHEMA, model="claude-sonnet-5-5",
                       effort="medium", max_tokens=4000, stage="스레드댓글")
    return out.get("items", [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Threads 댓글 후보·초안(자동 댓글 없음)")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 검색어만 출력")
    args = ap.parse_args(argv)

    posts = load_posts()
    kws = keywords_for(posts, datetime.now(KST).toordinal())
    if args.dry_run:
        print("검색어:", kws)
        return 0
    token = secret("THREADS_ACCESS_TOKEN")
    if not token:
        print("THREADS_ACCESS_TOKEN 없음 — 생략.")
        return 0
    seen = _seen()
    me_user = ""
    try:
        me_user = requests.get(f"{API}/me", params={"fields": "username", "access_token": token},
                               timeout=20).json().get("username", "")
    except Exception:
        pass
    cands: list[dict] = []
    for q in kws:
        try:
            for it in search(q, token):
                if it.get("id") in seen or not it.get("text") or it.get("username") == me_user:
                    continue
                it["q"] = q
                cands.append(it)
        except Exception as e:  # noqa: BLE001  (권한 미승인·한도 등: 조용히 다음 검색어)
            print(f"[검색 실패] {q}: {type(e).__name__}: {e}")
    cands = cands[:MAX_PER_RUN]
    if not cands:
        print("새 후보 없음.")
        return 0

    from content.llm import Claude
    llm = Claude()
    by_id = {c["id"]: c for c in cands}
    items = draft(llm, cands, posts)
    lines = []
    for it in items:
        c = by_id.get(it["id"])
        seen.add(it["id"])
        if not c or not it["relevant"] or not it["reply"].strip():
            continue
        lines.append(f"### {c.get('username', '')} · 검색어 '{c['q']}'\n"
                     f"- 원글: {c.get('permalink', '')}\n- 내용: {c['text'][:200].strip()}\n"
                     f"- 댓글 초안:\n\n> {it['reply'].strip()}\n")
    _save_seen(seen)
    if lines:
        head = f"\n## {datetime.now(KST):%Y-%m-%d %H:%M} 후보 {len(lines)}개 (대표가 링크 열어 직접 붙여넣기)\n\n"
        old = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else "# Threads 댓글 후보\n"
        QUEUE.write_text(old + head + "\n".join(lines), encoding="utf-8")
    print(f"후보 {len(cands)}개 중 댓글 초안 {len(lines)}개 저장.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
