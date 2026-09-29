"""결과를 휴대폰에서 읽기 좋은 마크다운으로 만든다 (KICKOFF 규칙 6).

표는 열을 5개 안팎으로 줄이고, 긴 내용은 목록으로 쓴다.
양식은 .claude/skills/market-research-memo/SKILL.md를 따른다.
판단 칸(결론, 매출·원가, 경쟁자 요약, 정보 이득)은 비워 두고 Claude 검토 대기로 표시한다 (14.1).
"""
from __future__ import annotations

from collections import Counter

PENDING = "_Claude 검토 대기_"
LABEL = {"demand": "수요", "value": "가치", "supply": "공급", "win": "이길 가능성", "affiliate": "제휴 가치"}


def _n(x) -> str:
    return f"{int(x):,}" if x is not None else "-"


def _pct(x) -> str:
    return f"{x * 100:+.0f}%"


def banner(sample: bool) -> str:
    if not sample:
        return ""
    return ("> ⚠️ **예시 데이터입니다. 실제 시장 데이터가 아닙니다.** API 키 입력 전, 결과가 "
            "어떤 모양인지 보여주기 위한 가짜 숫자입니다. 판단에 쓰지 마세요.\n\n")


def score_table(scored: list[dict], limit: int = 30) -> str:
    lines = ["| 순위 | 키워드 | 점수 | 월 검색량 | 블로그 문서 |", "| --- | --- | --- | --- | --- |"]
    for i, r in enumerate(scored[:limit], 1):
        flag = " ⚠️" if r["regulated"] else ""
        lines.append(f"| {i} | {r['keyword']}{flag} | {r['score']} | {_n(r['volume'])} | {_n(r.get('blog_total'))} |")
    return "\n".join(lines)


def summary_md(run_date: str, areas: list[dict], scored: list[dict], notes: list[str], sample: bool) -> str:
    out = [f"# 시장조사 요약 · {run_date}", "", banner(sample)]
    out += ["## 주제 후보 순위", "", "| 순위 | 주제 | 주제 점수 | 제안 | 규제 키워드 |", "| --- | --- | --- | --- | --- |"]
    for i, a in enumerate(areas, 1):
        out.append(f"| {i} | {a['area_name']} | {a['area_score']} | {a.get('verdict', '-')} | {len(a['regulated'])}개 |")
    out += ["", "주제 점수 = 그 주제의 규제 제외 상위 키워드 점수 평균. 제안은 코드 판정이며 최종 결론은 Claude 검토 후 메모에 적습니다. 점수는 이번 실행 안에서의 상대값(최고 100)입니다.", ""]
    out += ["## 키워드 상위 30", "", score_table(scored), "", "⚠️ = 규제·민감 업종 (법률 검토 전 진입 안 함)", ""]
    if notes:
        out += ["## 실행 메모", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(out)


def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _mid(xs: list[float]):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def _axis_rows(area: dict) -> list[tuple[str, str, str]]:
    """스킬 양식의 '축 | 점수 | 근거' 행. 점수는 상위 키워드 평균(0~1), 근거는 원 숫자."""
    top = area["top"]
    ax = {k: _avg([r["axes"][k] for r in top]) for k in LABEL}
    yt = [r["youtube"] for r in top if r.get("youtube")]
    seasonal = sum(1 for r in top if r.get("seasonality", 0) >= 2)
    high = sum(1 for r in top if r["competition"] == "높음")
    monthly = _mid([r.get("monthly_new_posts") for r in top])
    subs = _mid([v["subscribers"] for y in yt for v in y["videos"] if v["subscribers"]])
    yt_total = _mid([y["total"] for y in yt])
    shop = area.get("shopping")
    return [
        ("수요", f"{ax['demand']:.2f}",
         f"월 검색량 합 {_n(sum(r['volume'] for r in top))}, 추세 평균 {_pct(_avg([r.get('trend', 0) for r in top]))}, "
         f"계절성 강한 키워드 {seasonal}개"),
        ("가치", f"{ax['value']:.2f}",
         f"경쟁도 높음 {high}/{len(top)}개, 노출 광고 평균 {_avg([r['ad_depth'] for r in top]):.1f}개, "
         f"월 클릭 합 {_n(sum(r['clicks'] for r in top))}"),
        ("공급", f"{ax['supply']:.2f} (낮을수록 유리)",
         f"블로그 문서 중앙값 {_n(_mid([r.get('blog_total') for r in top]))}, "
         f"유튜브 경쟁 영상 {_n(yt_total) if yt_total is not None else '미조회'}"),
        ("이길 가능성", f"{ax['win']:.2f}",
         f"최근 30일 새 블로그 글 중앙값 {_n(monthly) + '개' if monthly is not None else '미확인'} (적을수록 유리), "
         f"유튜브 상위 채널 구독자 중앙값 {_n(subs) if subs else '미조회'}"),
        ("제휴 가치", f"{ax['affiliate']:.2f}",
         f"가정값 {area.get('affiliate_prior', '-')}/5 (config/seeds.yaml, 미검증)"
         + (f", 쇼핑 인사이트 추세 {_pct(shop['trend'])}" if shop else ", 쇼핑 인사이트 미조회")),
    ]


def memo_md(rank: int, area: dict, run_date: str, sample: bool) -> str:
    """market-research-memo 스킬의 투자 메모 양식. 숫자는 코드가, 판단 칸은 Claude가 채운다."""
    top, rep = area["top"], area.get("representative", area["top"])
    out = [f"# {area['area_name']} 투자 메모 — {run_date}", "", banner(sample)]
    out += [f"**결론:** {PENDING}", "",
            f"- 데이터 기준 제안(코드): **{area.get('verdict', '-')}** — {area.get('verdict_reason', '')}",
            f"- 주제 점수 {area['area_score']} · 후보 순위 {rank}", ""]

    if top:
        out += ["| 축 | 점수 | 근거 |", "| --- | --- | --- |"]
        out += [f"| {a} | {b} | {c} |" for a, b, c in _axis_rows(area)]
        out += ["", "점수는 이번 실행 키워드 안에서의 상대값(0~1). 상위 키워드 평균.", ""]

    out += [f"**예상 편당 매출:** {PENDING}", "", f"**예상 편당 원가:** {PENDING}", ""]

    # 상위 경쟁자 요약: 3줄은 Claude가 쓰고, 코드는 근거 사실만 모은다.
    # 최근 글을 여러 키워드에 걸쳐 꾸준히 쓰는 블로그 = 이 주제에서 활발한 경쟁자
    bloggers = Counter(it["blogger"] for r in top for it in r.get("blog_items", [])[:30] if it["blogger"])
    repeat = [f"{b}({c}회)" for b, c in bloggers.most_common(5) if c >= 3]
    monthly = [m for m in (r.get("monthly_new_posts") for r in top) if m is not None]
    busy = sum(1 for m in monthly if m >= 100)
    outliers = [v for r in top if r.get("youtube") for v in r["youtube"]["videos"] if v["outlier"]]
    out += [f"**상위 경쟁자 요약:** {PENDING}", "",
            f"- 여러 키워드에 최근 글을 꾸준히 쓰는 블로그(추격 대상 후보, 15.1): {', '.join(repeat) or '없음'}",
            f"- 월 새 글 100개 이상인 키워드: {busy}/{len(monthly)}개",
            "- 실제 검색 화면의 상위 10개는 API로 알 수 없음 (정확도순 결과가 검색 화면과 다름, 2026-09-29 확인)",
            f"- 유튜브 이상치 영상(쇼츠 신호): {len(outliers)}개", ""]

    out += [f"**빈틈과 우리의 정보 이득:** {PENDING}", "",
            "새 숫자 / 도구 / 최신성 / 미답변 질문 중 무엇으로 이길지 (12.2)", ""]

    out += ["**대표 키워드 10개**", "", "| 키워드 | 월 검색량 | 틈새 점수 |", "| --- | --- | --- |"]
    out += [f"| {r['keyword']} | {_n(r['volume'])} | {r['score']} |" for r in rep]
    out += [""]

    out += ["**규제·리스크**", ""]
    out.append("- 규제·민감 키워드: " + (", ".join(f"{r['keyword']}({r['regulated']})" for r in area["regulated"][:8]) or "없음"))
    seasonal = [r["keyword"] for r in rep if r.get("seasonality", 0) >= 2]
    out.append("- 계절성 강함(최고가 평균의 2배 이상): " + (", ".join(seasonal) or "없음"))
    out += [f"- 그 밖의 리스크: {PENDING}", ""]

    out += ["**검증할 가정**", "",
            "- 제휴 가치는 가정값이다 → 제휴 클릭·매출로 보정",
            "- 검색광고 가치가 높은 키워드일수록 애드포스트 단가도 높다 (0.6) → 30~60일",
            "- 틈새 점수가 높은 키워드가 실제로 상위 노출된다 (0.6) → 발행 후 30일 순위 추적",
            f"- 추가: {PENDING}", ""]

    # 부록: 판단 근거 원자료 (상위 3개 키워드만, 1페이지를 넘기지 않게)
    out += ["---", "", "<details><summary>부록: 상위 키워드 최근 글</summary>", ""]
    for r in top[:3]:
        out.append(f"**{r['keyword']}** · 블로그 문서 {_n(r.get('blog_total'))} · 최근 30일 새 글 {_n(r.get('monthly_new_posts'))}")
        out += [f"- {it['postdate']} · {it['blogger']} · {it['title']}" for it in r.get("blog_items", [])[:3]]
        for v in [v for v in (r.get("youtube") or {}).get("videos", []) if v["outlier"]][:2]:
            out.append(f"- 📈 {v['title']} ({v['channel']}, 조회 {_n(v['views'])} / 구독 {_n(v['subscribers'])})")
        out.append("")
    out += ["</details>", ""]
    return "\n".join(out)
