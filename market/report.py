"""결과를 휴대폰에서 읽기 좋은 마크다운으로 만든다 (KICKOFF 규칙 6).

표는 열을 5개 안팎으로 줄이고, 긴 내용은 목록으로 쓴다.
판단 칸(결론 최종, 매출·원가, 차별화)은 비워 두고 Claude 검토 대기로 표시한다 (14.1).
"""
from __future__ import annotations

from collections import Counter

PENDING = "_Claude 검토 대기 — market-research-memo 스킬로 채운다._"
LABEL = {"demand": "수요", "value": "가치", "win": "이길 가능성", "affiliate": "제휴 가치", "supply": "공급(낮을수록 좋음)"}


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
    out += ["## 주제 후보 순위", "", "| 순위 | 주제 | 주제 점수 | 규제 키워드 |", "| --- | --- | --- | --- |"]
    for i, a in enumerate(areas, 1):
        out.append(f"| {i} | {a['area_name']} | {a['area_score']} | {len(a['regulated'])}개 |")
    out += ["", "주제 점수 = 그 주제의 규제 제외 상위 키워드 점수 평균. 점수는 이번 실행 안에서의 상대값(최고 100)입니다.", ""]
    out += ["## 키워드 상위 30", "", score_table(scored), "", "⚠️ = 규제·민감 업종 (법률 검토 전 진입 안 함)", ""]
    if notes:
        out += ["## 실행 메모", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(out)


def _suggestion(area: dict) -> str:
    if not area["top"]:
        return "제외 (규제 아닌 키워드 없음)"
    if len(area["regulated"]) > len(area["keywords"]):
        return "보류 (규제 키워드 비중이 큼)"
    return "진입 검토"


def memo_md(rank: int, area: dict, run_date: str, sample: bool) -> str:
    top = area["top"]
    out = [f"# 투자 메모 {rank} · {area['area_name']}", "", f"작성: {run_date} · 코드 초안", "", banner(sample)]

    out += ["## 1. 결론", "", f"- 데이터 기준 제안: **{_suggestion(area)}** (주제 점수 {area['area_score']})",
            f"- 최종 결론과 이유: {PENDING}", ""]

    out += ["## 2. 점수", ""]
    if top:
        axes = {k: sum(r["axes"][k] for r in top) / len(top) for k in LABEL}
        out += ["상위 키워드 평균 (0~1)", ""] + [f"- {LABEL[k]}: {axes[k]:.2f}" for k in LABEL] + [""]
        out += ["| 키워드 | 점수 | 월 검색량 | 경쟁도 | 추세 |", "| --- | --- | --- | --- | --- |"]
        for r in top:
            out.append(f"| {r['keyword']} | {r['score']} | {_n(r['volume'])} | {r['competition'] or '-'} | {_pct(r.get('trend', 0))} |")
        out += ["", "추세 = 데이터랩 최근 3개월 ÷ 그 전 3개월. 제휴 가치는 `config/seeds.yaml`의 가정값.", ""]

    out += ["## 3. 예상 편당 매출·원가", "", PENDING, ""]

    out += ["## 4. 상위 경쟁자 요약과 빈틈", ""]
    bloggers = Counter()
    for r in top:
        bloggers.update(it["blogger"] for it in r.get("blog_items", []) if it["blogger"])
        age = r.get("top_median_age_days")
        age_txt = f"{age / 30:.0f}개월" if age is not None else "미확인"
        out += [f"### {r['keyword']}", "", f"- 블로그 문서 {_n(r.get('blog_total'))}개, 상위 10개 발행일 중앙값 {age_txt} 전"]
        for it in r.get("blog_items", [])[:3]:
            out.append(f"- {it['postdate']} · {it['blogger']} · {it['title']}")
        yt = r.get("youtube")
        if yt:
            outliers = [v for v in yt["videos"] if v["outlier"]]
            out.append(f"- 유튜브 상위 영상 {len(yt['videos'])}개, 이상치 {len(outliers)}개")
            for v in outliers[:2]:
                out.append(f"  - 📈 {v['title']} ({v['channel']}, 조회 {_n(v['views'])} / 구독 {_n(v['subscribers'])})")
        out.append("")
    repeat = [f"{b} ({c}회)" for b, c in bloggers.most_common(5) if c >= 2]
    out += ["- 여러 키워드 상위에 반복 등장한 블로그(추격 대상 후보, 15.1): " + (", ".join(repeat) or "없음"), "",
            f"- 빈틈: {PENDING}", ""]

    out += ["## 5. 우리의 차별화 포인트", "", "정보 이득 게이트(12.2): 새 숫자 / 도구 / 최신 정보 / 미답변 질문 중 무엇으로 이기는가", "", PENDING, ""]

    out += ["## 6. 규제·리스크", ""]
    if area["regulated"]:
        out.append("- ⚠️ 규제·민감 키워드: " + ", ".join(f"{r['keyword']}({r['regulated']})" for r in area["regulated"][:8]))
    else:
        out.append("- 규제·민감 키워드: 없음")
    seasonal = [r["keyword"] for r in top if r.get("seasonality", 0) >= 2]
    out.append("- 계절성 강함(최고가 평균의 2배 이상): " + (", ".join(seasonal) or "없음"))
    out += [f"- 기타 리스크: {PENDING}", ""]
    return "\n".join(out)
