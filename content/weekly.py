"""주간 보고서 (docs/운영-계획.md 4·5장): 자동 부분(만든 글·발행·품질·비용·재고)과 캡처 성과(config/metrics.yaml)를 한 장에.

- 만든 글·발행·버린 글 수, 발행률, 테마 구성, 편집장 평균, Claude 비용: posts/에서 자동
- 7일 조회수·체류·댓글·클립: config/metrics.yaml (캡처에서 옮겨 적음). 7일이 지난 글만 판정에 넣는다
- 판정 규칙(5장)에 따라 테마별 올리기·내리기 후보를 계산한다 (적용은 Claude가 기록과 함께)
결과: reports/주간/<주 시작일>.md
사용법: python -m content.weekly [YYYY-MM-DD]   (그 날짜가 속한 주, 기본 지난주)
"""
from __future__ import annotations

import csv
import re
import statistics
import sys
from datetime import date, timedelta

import yaml

from market.common import ROOT, load_yaml
from .mark import status

POSTS = ROOT / "posts"
MIN_GROUP = 5        # 묶음 최소 편수
UP, DOWN = 1.3, 0.7  # 전체 평균 대비 +30% / -30%


def posts_between(start: date, end: date) -> list[dict]:
    out = []
    for f in sorted(POSTS.iterdir()) if POSTS.exists() else []:
        if not (f / "post.md").exists() or not re.match(r"\d{4}-\d{2}-\d{2}", f.name):
            continue
        day = date.fromisoformat(f.name[:10])
        if not start <= day <= end:
            continue
        md = (f / "post.md").read_text(encoding="utf-8")
        d = yaml.safe_load((f / "data.yaml").read_text(encoding="utf-8")) if (f / "data.yaml").exists() else {}
        scores = [int(x) for x in re.findall(r"[가-힣 ]+ (\d)(?= ·|\n)", md.split("## 편집장 검토", 1)[1].split("\n\n")[1])] \
            if "## 편집장 검토" in md else []
        cost = re.search(r"API 비용 약 \$([\d.]+)", md)
        ttype = re.search(r"^\d\. ★ .+ — (\S+)$", md, re.M)
        out.append({"folder": f.name, "day": day, "theme": d.get("theme", "receipt"), "ok": "✅" in md.split("## ", 1)[0],
                    "status": status(f).get("status", ""), "score": statistics.mean(scores) if scores else None,
                    "cost": float(cost.group(1)) if cost else 0.0, "title_type": ttype.group(1) if ttype else "",
                    "marketer": d.get("marketer"), "rounds": int(r.group(1)) if (r := re.search(r"고쳐 쓰기 (\d+)회", md)) else 0,
                    "edits": (f / "edits.md").read_text(encoding="utf-8").count("\n  → ") if (f / "edits.md").exists() else 0})
    return out


def judge(metrics: dict, today: date, names: dict) -> list[str]:
    """7일 지난 글의 테마별 평균 조회수 → 올리기·내리기 후보 (5장 규칙 3)."""
    rows = []
    for folder, m in metrics.get("posts", {}).items():
        pub = m.get("published")
        if not pub or (today - date.fromisoformat(str(pub))).days < 7 or not m.get("views_7d"):
            continue
        d = yaml.safe_load((POSTS / folder / "data.yaml").read_text(encoding="utf-8")) if (POSTS / folder / "data.yaml").exists() else {}
        rows.append((d.get("theme", "receipt"), m["views_7d"], m.get("avg_time_sec")))
    if len(rows) < MIN_GROUP:
        return [f"판정할 글이 아직 {len(rows)}편 (7일 지난 글 {MIN_GROUP}편부터 판정)"]
    avg = statistics.mean(v for _, v, _ in rows)
    out = [f"7일 지난 글 {len(rows)}편, 글당 평균 조회수 {avg:,.0f}"]
    for th in sorted({t for t, _, _ in rows}):
        vs = [v for t, v, _ in rows if t == th]
        if len(vs) < MIN_GROUP:
            out.append(f"- {names.get(th, th)}: {len(vs)}편 (판정 보류)")
            continue
        r = statistics.mean(vs) / avg
        verdict = "올리기 후보 (+1)" if r >= UP else "내리기 후보 (−0.5)" if r <= DOWN else "유지"
        out.append(f"- {names.get(th, th)}: {len(vs)}편, 평균의 {r:.0%} → {verdict}")
    return out


def marketer_lines(ps: list[dict], metrics: dict) -> list[str]:
    """마케터 비교 (대표 결정 2026-10-01): 만든 글·발행·클립 조회·블로그 7일 조회·대표가 고친 곳·다시 쓴 횟수·비용.
    조회수는 대표 캡처(config/metrics.yaml)에서. 4주마다 꼴찌 전략을 바꾼다."""
    from .marketers import cfg, ids
    c = cfg()
    mp = metrics.get("posts", {})
    L = ["| 마케터 | 글(✅) | 발행 | 클립 조회 평균 | 블로그 7일 조회 평균 | 대표가 고친 곳 | 다시 쓴 횟수 | 비용 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m in ids(c):
        mine = [p for p in ps if p.get("marketer") == m and p["status"] != "rejected"]
        clips = [x for p in mine for x in [(mp.get(p["folder"]) or {}).get("clip_views")
                                           or ((mp.get(p["folder"]) or {}).get("checks") or [{}])[-1].get("clip_views")] if x]
        blogs = [(mp.get(p["folder"]) or {}).get("views_7d") for p in mine if (mp.get(p["folder"]) or {}).get("views_7d")]
        avg = lambda xs: f"{statistics.mean(xs):,.0f} ({len(xs)}편)" if xs else "-"
        L.append(f"| {m} · {c['marketers'][m]['name']} | {sum(p['ok'] for p in mine)} | {sum(p['status'] == 'used' for p in mine)} | "
                 f"{avg(clips)} | {avg(blogs)} | {sum(p['edits'] for p in mine)} | {sum(p['rounds'] for p in mine)} | "
                 f"${sum(p['cost'] for p in mine):.2f} |")
    return L


def cost_line(start: date, end: date, ps: list[dict]) -> str:
    """Claude 비용: reports/costs.csv(실행마다 기록, 지운 후보·화제 선수 찾기 포함)가 있으면 그걸로, 없으면 남은 글에서."""
    f = ROOT / "reports" / "costs.csv"
    rows = [r for r in csv.DictReader(f.open(encoding="utf-8"))
            if str(start) <= r["at"][:10] <= str(end)] if f.exists() else []
    if not rows:
        return f"- Claude 비용: 약 ${sum(p['cost'] for p in ps):.2f} (남은 글 기준, 지운 후보 빠짐)"
    stages: dict[str, float] = {}
    for r in rows:
        for part in filter(None, r["stages"].split(";")):
            k, v = part.split("=")
            stages[k] = stages.get(k, 0.0) + float(v)
    total = sum(float(r["usd"]) for r in rows)
    return (f"- Claude 비용: ${total:.2f} (하루 평균 ${total / 7:.2f}, 한 달 환산 ${total / 7 * 30:.0f} · 목표 월 $40) · 단계별: "
            + ", ".join(f"{k} ${v:.2f}" for k, v in sorted(stages.items(), key=lambda x: -x[1])))


def shorts_lines(end: date) -> list[str]:
    from . import shorts_stats
    stats = shorts_stats.load(shorts_stats.STATS, None)
    if not stats or not stats.get("channel"):
        return ["- 아직 수집 전 (config/youtube.yaml에 채널 주소가 들어가면 매일 자동)"]
    day = max(d for d in stats["channel"] if d <= str(end)) if any(d <= str(end) for d in stats["channel"]) else max(stats["channel"])
    return [x.replace("## ", "### ") for x in shorts_stats.summary(stats, day)]


def report(week_start: date) -> str:
    end = week_start + timedelta(days=6)
    ps = posts_between(week_start, end)
    pool = load_yaml("players.yaml")
    names = {k: v["name"] for k, v in pool["themes"].items()}
    metrics = load_yaml("metrics.yaml") if (ROOT / "config" / "metrics.yaml").exists() else {}
    made = [p for p in ps if p["status"] != "rejected"]
    used = [p for p in ps if p["status"] == "used"]
    scores = [p["score"] for p in made if p["score"]]
    L = [f"# 주간 보고서 · {week_start} ~ {end}", "",
         "## 1. 이번 주 숫자 (자동)", "",
         f"- 만든 글(✅): {sum(p['ok'] for p in made)}편 · 버린 글: {sum(p['status'] == 'rejected' for p in ps)}편",
         f"- 발행 완료 표시: {len(used)}편 / 7일 → 발행률 {len(used) / 7:.0%} (목표 90%)",
         f"- 편집장 평균: {statistics.mean(scores):.1f}" if scores else "- 편집장 평균: -",
         cost_line(week_start, end, ps),
         "- 테마 구성: " + (", ".join(f"{names.get(t, t)} {sum(p['theme'] == t for p in made)}" for t in sorted({p['theme'] for p in made})) or "-"),
         "", "## 2. 성과 (캡처 → config/metrics.yaml)", ""]
    wk = (metrics.get("weeks") or {}).get(str(week_start))
    L += [f"- 일 방문자 {wk.get('visitors_day', '-')} · 주간 조회 {wk.get('views_week', '-')} · 홈판 {wk.get('homefeed_pct', '-')}% · "
          f"검색 {wk.get('search_pct', '-')}% · 애드포스트 {wk.get('adpost_krw', '-')}원"] if wk else ["- 아직 캡처 없음 (월요일에 대표가 캡처를 보내면 채움)"]
    L += ["", "## 2-1. 마케터 비교 (클립은 3명 다 올림, 블로그는 차례대로)", ""] + marketer_lines(ps, metrics)
    L += ["", "## 3. 판정 (7일 지난 글, 운영 계획 5장)", ""] + judge(metrics, end, names)
    L += ["", "## 3-1. 유튜브 쇼츠 (자동, 운영 계획 6장)", ""] + shorts_lines(end)
    L += ["", "## 4. 이번 주 바꾼 것 (1~2개, DECISIONS에 기록)", "", "- (Claude가 판정 후 적음)",
          "", "## 5. 다음 주 가설", "", "- (Claude가 적음)",
          "", "## 6. 대표님께 부탁", "", "- 블로그·클립 통계와 댓글 캡처, 유튜브 스튜디오 쇼츠 캡처 (docs/운영자-안내-주간-점검.md)", ""]
    return "\n".join(L)


def main() -> None:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=7)
    start = day - timedelta(days=day.weekday())
    out = ROOT / "reports" / "주간" / f"{start}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = report(start)
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
