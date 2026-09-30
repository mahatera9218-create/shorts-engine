"""블로그 벤치마크 (2026-09-30): 겹치는 주제에서 잘 되는 블로그를 우리 블로그와 같은 잣대로 잰다.

- 통로: 블로그 공개 RSS(https://rss.blog.naver.com/<아이디>.xml)와 네이버 공식 블로그 검색 API. 본문은 받지 않는다.
- 남의 제목·문장은 저장하지 않는다. 발행 빈도·시각·카테고리·제목 패턴·자주 쓰는 낱말·태그, 말투 수치만 남긴다.
- 겹침: "선수 이름 + 연봉" 검색어마다 API 정확도순 100개 안에서 대상 글과 우리 글의 자리.
  API 정확도순은 실제 검색 화면 순서와 다르다(2026-09-29 확인) → 두 블로그를 같은 잣대로 비교하는 용도로만 쓴다.
- 결과: reports/블로그-벤치마크/<날짜>.md
사용법: python -m market.blog_bench              (실제, NCP 키 필요 — 없으면 RSS만)
       python -m market.blog_bench --rss-dir d   (저장한 RSS <아이디>.xml로 시험, 검색 없이)
"""
from __future__ import annotations

import argparse
import re
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from content.voice import style_metrics
from .common import ROOT, ApiError, load_yaml, missing_secrets

KST = ZoneInfo("Asia/Seoul")
WEEK = "월화수목금토일"
TAGS = re.compile(r"<[^>]+>")
WORD = re.compile(r"[가-힣A-Za-z]{2,}")
STOP = {"그리고", "이번", "오늘", "정리", "관련", "대한", "있는", "하는", "까지", "에서", "으로", "the"}


def blog_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[1]


def parse_rss(xml: str) -> list[dict]:
    out = []
    for it in ET.fromstring(xml).iter("item"):
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(KST)
        except (TypeError, ValueError):
            continue
        tags = [t.strip() for t in (it.findtext("tag") or "").split(",") if t.strip()]
        out.append({"title": (it.findtext("title") or "").strip(), "at": at,
                    "category": (it.findtext("category") or "").strip() or "(없음)", "tags": tags,
                    "desc": TAGS.sub(" ", it.findtext("description") or ""), "link": (it.findtext("link") or "").split("?")[0]})
    return out


def title_flags(t: str) -> dict:
    return {"숫자": bool(re.search(r"\d", t)), "돈": bool(re.search(r"억|만원|달러|연봉|몸값|상금|계약|FA", t)),
            "순위": bool(re.search(r"TOP|순위|\d+위", t)), "비교": bool(re.search(r"vs|VS|비교|차이", t)),
            "물음": "?" in t, "괄호": bool(re.search(r"[\[\(【]", t)), "선수명": False}


def profile(items: list[dict], names: list[str]) -> dict:
    """RSS 글 목록 → 숫자 요약. 제목 원문은 들고 나가지 않는다."""
    if not items:
        return {"n": 0}
    days = sorted({i["at"].date() for i in items})
    span = max((days[-1] - days[0]).days + 1, 1)
    flags = Counter()
    words, tags, players = Counter(), Counter(), Counter()
    for i in items:
        f = title_flags(i["title"])
        hit = [n for n in names if n in i["title"]]
        f["선수명"] = bool(hit)
        players.update(hit)
        flags.update(k for k, v in f.items() if v)
        words.update(w for w in set(WORD.findall(i["title"])) if w not in STOP and w not in hit)
        tags.update(set(i["tags"]))
    n = len(items)
    per_day = Counter(i["at"].date() for i in items)
    return {
        "n": n, "first": days[0], "last": days[-1], "span": span, "per_day": n / span,
        "max_day": max(per_day.values()), "active_days": len(days),
        "hours": Counter(i["at"].hour for i in items), "weekdays": Counter(WEEK[i["at"].weekday()] for i in items),
        "categories": Counter(i["category"] for i in items),
        "title_len": statistics.median(len(i["title"]) for i in items),
        "flags": {k: flags[k] / n for k in ["숫자", "돈", "선수명", "순위", "비교", "물음", "괄호"]},
        "players": players, "words": words, "tags": tags,
        "tags_per_post": statistics.mean(len(i["tags"]) for i in items),
        "voice": style_metrics([i["desc"] for i in items if i["desc"].strip()]),
    }


def fetch_rss(bid: str, rss_dir: str | None) -> list[dict]:
    if rss_dir:
        p = Path(rss_dir) / f"{bid}.xml"
        return parse_rss(p.read_text(encoding="utf-8")) if p.exists() else []
    r = requests.get(f"https://rss.blog.naver.com/{bid}.xml", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return parse_rss(r.text)


def overlap(hub, queries: list[str], ids: dict[str, str]) -> list[dict]:
    """검색어마다 API 정확도순 100개 안에서 각 블로그의 가장 높은 자리(없으면 None)."""
    from .common import request_json
    url = hub.base + hub.paths["blog_search"]
    rows = []
    for q in queries:
        try:
            data = request_json("GET", url, headers=hub._headers(), params={"query": q, "display": 100, "sort": "sim"})
        except ApiError as e:
            rows.append({"q": q, "error": str(e)[:80]})
            continue
        pos = {}
        for rank, it in enumerate(data.get("items", []), 1):
            link = (it.get("bloggerlink", "") + " " + it.get("link", "")).lower()
            for key, bid in ids.items():
                if key not in pos and re.search(rf"/{re.escape(bid.lower())}(?![\w-])", link):
                    pos[key] = rank
        rows.append({"q": q, "total": int(data.get("total", 0)), **{k: pos.get(k) for k in ids}})
    return rows


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _top(c: Counter, k: int = 8) -> str:
    return ", ".join(f"{w}({n})" for w, n in c.most_common(k)) or "-"


def compare_table(pa: dict, pb: dict, a: str, b: str) -> list[str]:
    def row(label, fa, fb):
        return f"| {label} | {fa(pa) if pa['n'] else '-'} | {fb(pb) if pb['n'] else '-'} |"
    L = [f"| 항목 | {a} | {b} |", "| --- | --- | --- |",
         row("RSS에 보이는 글", lambda p: f"{p['n']}편 ({p['first']:%m-%d}~{p['last']:%m-%d})", lambda p: f"{p['n']}편 ({p['first']:%m-%d}~{p['last']:%m-%d})"),
         row("하루 평균 발행", lambda p: f"{p['per_day']:.1f}편 (최대 {p['max_day']}편)", lambda p: f"{p['per_day']:.1f}편 (최대 {p['max_day']}편)"),
         row("주로 올리는 시각", lambda p: _top(Counter({f'{h}시': c for h, c in p['hours'].items()}), 3),
             lambda p: _top(Counter({f'{h}시': c for h, c in p['hours'].items()}), 3)),
         row("요일", lambda p: _top(p["weekdays"], 7), lambda p: _top(p["weekdays"], 7)),
         row("제목 길이(가운데 값)", lambda p: f"{p['title_len']:.0f}자", lambda p: f"{p['title_len']:.0f}자")]
    for k in pa.get("flags") or pb.get("flags"):
        L.append(row(f"제목에 {k}", lambda p, k=k: _pct(p["flags"][k]), lambda p, k=k: _pct(p["flags"][k])))
    L += [row("글당 태그 수", lambda p: f"{p['tags_per_post']:.1f}개", lambda p: f"{p['tags_per_post']:.1f}개"),
          row("말투: ~요 / ~다", lambda p: f"{_pct(p['voice'].get('요', 0))} / {_pct(p['voice'].get('다', 0))}",
              lambda p: f"{_pct(p['voice'].get('요', 0))} / {_pct(p['voice'].get('다', 0))}")]
    return L


def report(today: date, ours: tuple[str, dict], targets: list[tuple[dict, dict]], rows: list[dict] | None,
           notes: list[str], top: int) -> str:
    oname, op = ours
    L = [f"# 블로그 벤치마크 ({today})", "",
         "> 공개 RSS와 네이버 공식 검색 API로 잰 숫자예요. 남의 제목·문장은 옮기지 않았어요.",
         "> RSS는 최근 글 일부만 보여줘요(보통 최근 50편 안쪽).", ""]
    for t, p in targets:
        L += [f"## {t['name']} vs {oname}", "", f"왜 보나: {t.get('why', '')}", ""]
        if not p["n"]:
            L += ["RSS를 읽지 못했어요.", ""]
            continue
        L += compare_table(p, op, t["name"], oname) + [""]
        L += ["**카테고리별 글 수**", "", f"- {t['name']}: {_top(p['categories'], 10)}",
              f"- {oname}: {_top(op['categories'], 10) if op['n'] else '-'}", "",
              "**제목에 자주 나온 선수**", "", f"- {t['name']}: {_top(p['players'], 12)}",
              f"- {oname}: {_top(op['players'], 12) if op['n'] else '-'}", "",
              f"**제목에 자주 쓴 낱말 ({t['name']})**: {_top(p['words'], 20)}", "",
              f"**자주 단 태그 ({t['name']})**: {_top(p['tags'], 20)}", ""]
        gap = [n for n, _ in p["players"].most_common() if n not in (op.get("players") or {})]
        if gap:
            L += [f"**{t['name']} 쪽은 썼고 우리는 아직 안 쓴 선수**: {', '.join(gap[:12])}", ""]
    if rows is not None:
        keys = [t["name"] for t, _ in targets] + [oname]
        L += ["## 같은 검색어에서 자리 (API 정확도순 100개 안)", "",
              "> 실제 검색 화면 순서와 달라요. 두 블로그를 같은 잣대로 견주는 용도예요. 빈칸 = 100위 밖.", "",
              "| 검색어 | 문서 수 | " + " | ".join(keys) + " |", "| --- | --- | " + " | ".join("---" for _ in keys) + " |"]
        ok = [r for r in rows if "error" not in r]
        for r in sorted(ok, key=lambda r: min([r[k] for k in keys if r.get(k)] or [999])):
            if any(r.get(k) for k in keys):
                L.append(f"| {r['q']} | {r['total']:,} | " + " | ".join(str(r.get(k) or "") for k in keys) + " |")
        L += [""]
        for k in keys:
            got = [r[k] for r in ok if r.get(k)]
            L.append(f"- {k}: {len(ok)}개 검색어 중 {len(got)}개에 등장, 그중 {top}위 안 {sum(1 for x in got if x <= top)}개")
        if len(ok) < len(rows):
            L.append(f"- 검색 실패 {len(rows) - len(ok)}개")
        L += [""]
    if notes:
        L += ["## 참고", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rss-dir")
    a = ap.parse_args()
    cfg = load_yaml("blog_bench.yaml")
    names = [p["name"] for p in load_yaml("players.yaml")["players"]]
    me = load_yaml("blogs.yaml")["blogs"][0]
    notes = []

    def prof(bid):
        try:
            return profile(fetch_rss(bid, a.rss_dir), names)
        except (requests.RequestException, ET.ParseError) as e:
            notes.append(f"{bid} RSS 읽기 실패: {type(e).__name__}")
            return {"n": 0}

    ours = (me["name"], prof(blog_id(me["url"])))
    targets = [(t, prof(t["id"])) for t in cfg["targets"]]
    rows = None
    if a.rss_dir:
        notes.append("시험 실행: 검색 API 겹침 검사 생략")
    elif missing_secrets("naver_hub"):
        notes.append("NCP 키가 없어 검색 API 겹침 검사 생략")
    else:
        from .naver_hub import ApiHub
        hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
        ids = {t["name"]: t["id"] for t in cfg["targets"]} | {me["name"]: blog_id(me["url"])}
        rows = overlap(hub, [f"{n} {cfg['query_suffix']}" for n in dict.fromkeys(names)], ids)
    today = date.today()
    out = ROOT / "reports" / "블로그-벤치마크" / f"{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = report(today, ours, targets, rows, notes, cfg.get("top", 10))
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
