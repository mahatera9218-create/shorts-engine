"""주간 보고서 (docs/운영-계획.md 4·5장): 자동 부분(만든 글·발행·품질·비용·재고)과 캡처 성과(config/metrics.yaml)를 한 장에.

- 만든 글·발행·버린 글 수, 발행률, 테마 구성, 편집장 평균, Claude 비용: posts/에서 자동
- 7일 조회수·체류·댓글·클립: config/metrics.yaml (캡처에서 옮겨 적음). 7일이 지난 글만 판정에 넣는다
- 판정 규칙(5장)에 따라 테마별 올리기·내리기 후보를 계산한다 (적용은 Claude가 기록과 함께)
결과: reports/주간/<주 시작일>.md
사용법: python -m content.weekly [YYYY-MM-DD]   (그 날짜가 속한 주, 기본 지난주)
"""
from __future__ import annotations

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
                    "cost": float(cost.group(1)) if cost else 0.0, "title_type": ttype.group(1) if ttype else ""})
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
         f"- Claude 비용: 약 ${sum(p['cost'] for p in ps):.2f} (다시 쓴 글 포함)",
         "- 테마 구성: " + (", ".join(f"{names.get(t, t)} {sum(p['theme'] == t for p in made)}" for t in sorted({p['theme'] for p in made})) or "-"),
         "", "## 2. 성과 (캡처 → config/metrics.yaml)", ""]
    wk = (metrics.get("weeks") or {}).get(str(week_start))
    L += [f"- 일 방문자 {wk.get('visitors_day', '-')} · 주간 조회 {wk.get('views_week', '-')} · 홈판 {wk.get('homefeed_pct', '-')}% · "
          f"검색 {wk.get('search_pct', '-')}% · 애드포스트 {wk.get('adpost_krw', '-')}원"] if wk else ["- 아직 캡처 없음 (월요일에 대표가 캡처를 보내면 채움)"]
    L += ["", "## 3. 판정 (7일 지난 글, 운영 계획 5장)", ""] + judge(metrics, end, names)
    L += ["", "## 4. 이번 주 바꾼 것 (1~2개, DECISIONS에 기록)", "", "- (Claude가 판정 후 적음)",
          "", "## 5. 다음 주 가설", "", "- (Claude가 적음)",
          "", "## 6. 대표님께 부탁", "", "- 블로그·클립 통계와 댓글 캡처 (docs/운영자-안내-주간-점검.md)", ""]
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
