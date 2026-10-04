"""경제 상위 블로그 벤치마크 (2026-10-04, 대표 지시): 활성 방문자가 많은 경제 블로그는 무엇을 어떻게 쓰나.

1) 검색어마다 네이버 공식 블로그 검색 API 정확도순 상위 N개 → 자주·높게 나오는 블로그를 찾는다.
   (API 순서는 실제 검색 화면과 다를 수 있다. 여러 검색어에 '자주' 나오는지를 보는 용도)
2) 상위 블로그의 공개 RSS(rss.blog.naver.com/<아이디>.xml) → 발행 빈도·시각·요일, 제목 모양, 주제 비율, 연재 표시.
남의 제목·문장은 옮기지 않고 숫자·낱말 빈도만 남긴다. 방문자·이웃 수는 공식 통로가 없어 재지 않는다.
결과: reports/블로그-벤치마크/경제-상위블로그-<날짜>.md
"""
from __future__ import annotations

import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import requests

from .blog_bench import KST, WEEK, blog_id, parse_rss
from .common import ROOT, load_yaml, missing_secrets, request_json
from .naver_hub import ApiHub, clean

TOPIC = {  # 제목·요약에 이 말이 있으면 그 주제 (여러 개 가능)
    "시황": r"증시|마감|시황|코스피|코스닥|나스닥|다우|S&P|뉴욕|지수",
    "금": r"금값|금시세|금 시세|골드|금투자|금ETF|금 ETF",
    "코인": r"비트코인|코인|이더리움|가상자산|암호화폐|BTC|ETH|리플|XRP",
    "미국주식": r"미국주식|미국 주식|엔비디아|테슬라|애플|마이크로소프트|ETF|배당|SCHD|QQQ|TQQQ",
    "국내주식": r"삼성전자|하이닉스|국내주식|코스피|종목",
    "돈굴리기": r"ISA|파킹|예금|적금|CMA|금리|통장|연금|IRP",
    "부동산": r"아파트|부동산|청약|전세|매매",
    "거시·환율": r"환율|연준|FOMC|금리 인하|금리인하|CPI|물가|고용",
}
SERIES = re.compile(r"^\s*[\[【(].{1,12}[\]】)]|\d+\s*(편|탄|회|일차|주차)|#\d+|vol\.?\s*\d+", re.I)
WORD = re.compile(r"[가-힣A-Za-z]{2,}")
STOP = {"그리고", "이번", "오늘", "정리", "관련", "대한", "있는", "하는", "까지", "에서", "으로", "the", "and", "방법", "이유"}


def search(hub: ApiHub, q: str, n: int) -> list[dict]:
    data = request_json("GET", hub.base + hub.paths["blog_search"], headers=hub._headers(),
                        params={"query": q, "display": n, "sort": "sim"})
    time.sleep(0.12)
    return [{"blogger": clean(it.get("bloggername")), "link": (it.get("bloggerlink") or "").rstrip("/")}
            for it in data.get("items", [])]


def rank_blogs(hub: ApiHub, queries: dict, depth: int) -> dict:
    score, hits, groups, names = Counter(), Counter(), defaultdict(set), {}
    for g, qs in queries.items():
        for q in qs:
            try:
                rows = search(hub, q, depth)
            except Exception as e:  # noqa: BLE001
                print(f"검색 실패 {q}: {str(e)[:80]}")
                continue
            seen = set()
            for i, r in enumerate(rows):
                link = r["link"]
                if "blog.naver.com" not in link or link in seen:
                    continue
                seen.add(link)
                score[link] += depth - i
                hits[link] += 1
                groups[link].add(g)
                names[link] = r["blogger"]
    return {"score": score, "hits": hits, "groups": groups, "names": names}


def rss(bid: str) -> list[dict]:
    try:
        r = requests.get(f"https://rss.blog.naver.com/{bid}.xml", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; eoksori-bench/1.0)"})
        return parse_rss(r.text) if r.status_code == 200 else []
    except (requests.RequestException, Exception):  # noqa: BLE001
        return []


def measure(items: list[dict]) -> dict:
    if not items:
        return {}
    now = datetime.now(KST)
    recent = [x for x in items if now - x["at"] <= timedelta(days=30)]
    span = max(1.0, (items[0]["at"] - items[-1]["at"]).days or 1) if len(items) > 1 else 1.0
    titles = [x["title"] for x in items]
    topics = Counter()
    for x in items:
        text = x["title"] + " " + x["desc"][:200]
        for k, pat in TOPIC.items():
            if re.search(pat, text):
                topics[k] += 1
    words = Counter(w for t in titles for w in WORD.findall(t) if w not in STOP)
    hours = Counter(x["at"].hour for x in items)
    return {
        "n": len(items), "per_week": round(len(items) / span * 7, 1), "last30": len(recent),
        "hour": hours.most_common(1)[0][0], "weekend": round(100 * sum(x["at"].weekday() >= 5 for x in items) / len(items)),
        "q": round(100 * sum("?" in t for t in titles) / len(titles)),
        "num": round(100 * sum(bool(re.search(r"\d", t)) for t in titles) / len(titles)),
        "series": round(100 * sum(bool(SERIES.search(t)) for t in titles) / len(titles)),
        "tlen": round(statistics.mean(len(t) for t in titles)),
        "cats": len({x["category"] for x in items}),
        "topics": topics, "words": [w for w, _ in words.most_common(8)],
        "tags": round(statistics.mean(len(x["tags"]) for x in items), 1),
    }


def main() -> None:
    cfg = load_yaml("econ_bench.yaml")
    kst = datetime.now(KST)
    if missing_secrets("naver_hub"):
        print("네이버 키가 없어 실행하지 않았습니다")
        return
    hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
    nq = sum(len(v) for v in cfg["queries"].values())
    r = rank_blogs(hub, cfg["queries"], cfg.get("depth", 30))
    # 여러 검색어에 나온 블로그가 먼저 (한 검색어에서만 높은 블로그는 우연일 수 있음, 1차 실행 2026-10-04)
    top = sorted(r["score"], key=lambda l: (-r["hits"][l], -r["score"][l]))[:cfg.get("top_blogs", 15)]
    L = [f"# 경제 상위 블로그 벤치마크 ({kst:%Y-%m-%d})", "",
         f"네이버 공식 블로그 검색 API로 경제 검색어 {nq}개의 정확도순 상위 {cfg.get('depth', 30)}개를 보고, 여러 검색어에 자주·높게 나오는 블로그를 골랐어요.",
         "그 블로그들의 공개 RSS(최근 글 약 50개)로 발행 습관·제목 모양·주제를 숫자로 쟀어요. 남의 제목·문장은 옮기지 않았어요.",
         "⚠️ 방문자·이웃 수는 공식 통로가 없어 못 쟀어요. API 순서는 실제 검색 화면과 다를 수 있어요.", "",
         "## 1. 상위 노출 블로그 (여러 검색어에 나온 순)", "", f"검색어 2개 이상에 나온 블로그: {sum(1 for v in r['hits'].values() if v >= 2)}곳 / 전체 {len(r['hits'])}곳", "", "| 순위 | 블로그 | 나온 검색어 수 | 주로 나온 분야 |", "| --- | --- | --- | --- |"]
    for i, l in enumerate(top, 1):
        L.append(f"| {i} | [{r['names'][l]}]({l}) | {r['hits'][l]}/{nq} | {', '.join(sorted(r['groups'][l]))} |")
    prof = {}
    for l in top:
        prof[l] = measure(rss(blog_id(l)))
        time.sleep(0.3)
    ok = {l: p for l, p in prof.items() if p}
    L += ["", "## 2. 블로그별 발행 습관·제목 모양", "",
          "| 블로그 | 주당 글 | 최근30일 | 주 발행시각 | 주말% | 제목?% | 제목숫자% | 연재표시% | 제목길이 | 태그수 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for l, p in ok.items():
        L.append(f"| {r['names'][l]} | {p['per_week']} | {p['last30']} | {p['hour']}시 | {p['weekend']} | {p['q']} | {p['num']} | {p['series']} | {p['tlen']} | {p['tags']} |")
    L += ["", "## 3. 블로그별 다루는 주제 (최근 글 중 비율)", "", "| 블로그 | " + " | ".join(TOPIC) + " | 자주 쓰는 낱말 |", "| --- " * (len(TOPIC) + 2) + "|"]
    for l, p in ok.items():
        L.append(f"| {r['names'][l]} | " + " | ".join(f"{round(100 * p['topics'][k] / p['n'])}" for k in TOPIC) + f" | {', '.join(p['words'][:6])} |")
    if ok:
        med = lambda k: round(statistics.median(p[k] for p in ok.values()), 1)  # noqa: E731
        tot = Counter()
        for p in ok.values():
            for k in TOPIC:
                tot[k] += p["topics"][k] / p["n"]
        L += ["", "## 4. 공통점 (중간값)", "",
              f"- 주당 글 수: **{med('per_week')}편** (최근 30일 {med('last30')}편)",
              f"- 주 발행 시각(가장 많은 시각): {Counter(p['hour'] for p in ok.values()).most_common(3)}",
              f"- 주말 발행 비율: {med('weekend')}%",
              f"- 제목에 물음표: {med('q')}% · 숫자: {med('num')}% · 연재 표시: {med('series')}% · 제목 길이 {med('tlen')}자",
              f"- 카테고리 수: {med('cats')}개 · 태그 수 {med('tags')}개",
              "- 주제 비율 평균: " + ", ".join(f"{k} {round(100 * v / len(ok))}%" for k, v in tot.most_common()),
              "", f"RSS를 못 받은 블로그: {len(top) - len(ok)}곳"]
    out = ROOT / "reports" / "블로그-벤치마크" / f"경제-상위블로그-{kst:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
