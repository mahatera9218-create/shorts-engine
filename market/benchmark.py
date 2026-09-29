"""벤치마크 대상 찾기 (설계서 15.1). 공식 블로그 검색 API만 쓴다.

주제별 "돈·숫자형" 검색어의 최신 글을 모아, 여러 검색어에 반복해서 나오는 블로그를
추격 대상 후보로 올린다. 제목 패턴(숫자·순위·비교 비율)도 코드로 센다.
조회수·공감 수는 공개 API로 알 수 없으므로, 후보 중 몇 곳은 운영자가 휴대폰으로 확인한다.

사용법:
  python -m market.benchmark            # 실제 (Secrets 필요)
  python -m market.benchmark --sample   # 예시 데이터
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date

from .common import ROOT, ApiError, load_yaml, missing_secrets
from .run import unique_dir, write_step_summary
from .scoring import monthly_new_posts
from content.voice import style_metrics

DIGIT = re.compile(r"\d")
RANK = re.compile(r"순위|TOP|top|Top|위\b|1위")
VERSUS = re.compile(r"vs|VS|비교|대비|차이")


def title_patterns(titles: list[str]) -> dict:
    n = len(titles) or 1
    return {
        "count": len(titles),
        "digit": sum(1 for t in titles if DIGIT.search(t)) / n,
        "rank": sum(1 for t in titles if RANK.search(t)) / n,
        "versus": sum(1 for t in titles if VERSUS.search(t)) / n,
        "avg_len": sum(len(t) for t in titles) / n,
    }


def find_candidates(results: dict[str, list[dict]], min_queries: int, top_n: int, today: date) -> list[dict]:
    """results: 검색어 → 최신 글 목록. 여러 검색어에 나온 블로그를 등장 검색어 수·글 수 순으로."""
    by_blog: dict[str, dict] = defaultdict(lambda: {"queries": set(), "posts": []})
    for query, items in results.items():
        for it in items:
            key = it.get("blog_link") or it.get("blogger")
            if not key:
                continue
            b = by_blog[key]
            b["name"] = it.get("blogger", "")
            b["link"] = it.get("blog_link", "")
            b["queries"].add(query)
            b["posts"].append(it)
    out = []
    for b in by_blog.values():
        if len(b["queries"]) < min_queries:
            continue
        posts = sorted(b["posts"], key=lambda p: p.get("postdate", ""), reverse=True)
        uniq = list({p.get("link") or p.get("title"): p for p in posts}.values())
        out.append({
            "name": b["name"], "link": b["link"],
            "query_hits": len(b["queries"]), "post_hits": len(uniq),
            "recent30": monthly_new_posts([p.get("postdate", "") for p in uniq], 10 ** 6, today) or 0,
            "titles": [p.get("title", "") for p in uniq[:3]],
            "patterns": title_patterns([p.get("title", "") for p in uniq]),
        })
    out.sort(key=lambda b: (b["query_hits"], b["post_hits"]), reverse=True)
    return out[:top_n]


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render(run_date: str, themes: list[dict], sample: bool) -> str:
    out = [f"# 벤치마크 후보 · {run_date}", ""]
    if sample:
        out += ["> ⚠️ **예시 데이터입니다.** 실제 블로그가 아닙니다.", ""]
    out += ["\"돈·숫자형\" 검색어의 최신 글에 **여러 번 나오는 블로그**입니다. 조회수·공감 수는 공개 API로 알 수 없어, "
            "몇 곳은 대표님이 휴대폰으로 열어 반응(공감·댓글·이웃 수)을 확인합니다 (설계서 15.1).", ""]
    for t in themes:
        p = t["patterns"]
        out += [f"## {t['name']}", "",
                f"수집 글 {p['count']}개의 제목: 숫자 포함 {_pct(p['digit'])} · 순위형 {_pct(p['rank'])} · "
                f"비교형 {_pct(p['versus'])} · 평균 {p['avg_len']:.0f}자", ""]
        v = t.get("voice")
        if v and v["sentences"]:
            out += [f"본문 요약문 {v['sentences']}문장의 말투: ~요 {_pct(v['요'])} · ~다 {_pct(v['다'])} · ~죠 {_pct(v['죠'])} · "
                    f"질문 {_pct(v['질문'])} · 느낌표 {_pct(v['느낌표'])} · 문장 평균 {v['평균길이']:.0f}자 (문장은 저장하지 않고 수치만)", ""]
        if not t["candidates"]:
            out += ["- 반복 등장 블로그 없음", ""]
            continue
        out += ["| 블로그 | 검색어 | 글 | 최근 30일 |", "| --- | --- | --- | --- |"]
        for b in t["candidates"]:
            name = f"[{b['name']}]({b['link']})" if b["link"] else b["name"]
            out.append(f"| {name} | {b['query_hits']}개 | {b['post_hits']}편 | {b['recent30']:.0f}편 |")
        out += ["", "<details><summary>후보별 최근 제목</summary>", ""]
        for b in t["candidates"]:
            out.append(f"**{b['name']}**")
            out += [f"- {x}" for x in b["titles"]]
            out.append("")
        out += ["</details>", ""]
    out += ["## 다음", "", "- Claude가 후보 중 선두 2·추격 대상 3·급성장 2곳을 골라 제안 → 대표 승인 (15.1)",
            "- 뒷광고·짜깁기·조회 조작이 의심되는 곳은 잘나가도 제외", ""]
    return "\n".join(out)


def run(sample: bool) -> int:
    cfg = load_yaml("benchmark.yaml")
    run_date = date.today().isoformat()
    if sample:
        from .sample import FakeHub
        hub = FakeHub()
        out_dir = ROOT / "reports" / "benchmark" / "sample"
    else:
        missing = missing_secrets("naver_hub")
        if missing:
            write_step_summary("# 벤치마크 중단\n\n비어 있는 Secrets: " + ", ".join(missing))
            return 1
        from .naver_hub import ApiHub
        hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
        out_dir = unique_dir(ROOT / "reports" / "benchmark" / run_date)
    themes = []
    for t in cfg["themes"]:
        results = {}
        for q in t["queries"]:
            try:
                results[q] = hub.blog(q, 100)["items"]
            except ApiError as e:
                write_step_summary(f"# 벤치마크 중단\n\n블로그 검색 실패 ({q}): {e}")
                return 1
        titles = [it.get("title", "") for items in results.values() for it in items]
        snippets = [it.get("description", "") for items in results.values() for it in items if it.get("description")]
        themes.append({"name": t["name"], "patterns": title_patterns(titles), "voice": style_metrics(snippets),
                       "candidates": find_candidates(results, cfg["min_queries"], cfg["top_n"], date.today())})
    text = render(run_date, themes, sample)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text(text, encoding="utf-8")
    write_step_summary(text)
    print(f"결과 저장: {out_dir.relative_to(ROOT)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="벤치마크 대상 찾기")
    parser.add_argument("--sample", action="store_true")
    sys.exit(run(parser.parse_args().sample))


if __name__ == "__main__":
    main()
