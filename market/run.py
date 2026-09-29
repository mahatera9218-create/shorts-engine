"""시장조사 실행 (설계서 0.3 최소 버전, KICKOFF 1주차).

씨앗 → 연관 키워드(검색광고) → 블로그 문서 수·상위 10개, 검색어 트렌드(API HUB)
→ 틈새 점수 → 상위 키워드만 유튜브 → 주제별 투자 메모 초안 3개.

사용법:
  python -m market.run            # 실제 실행 (GitHub Actions, Secrets 필요)
  python -m market.run --sample   # 예시 데이터로 흐름 확인 (키 불필요)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from . import report
from .common import ROOT, ApiError, load_yaml, missing_secrets
from .scoring import area_summary, related_to_seeds, score, suggest_verdict


def collect_keywords(tool, areas: list[dict], cfg: dict) -> list[dict]:
    """영역별 씨앗 → 연관 키워드. 중복 제거, 최소 검색량 필터, 씨앗과 무관한 키워드 제거, 씨앗마다 상위 N개."""
    seen: set[str] = {k.replace(" ", "") for k in cfg.get("exclude_keywords", [])}
    rows = []
    for area in areas:
        related = [r for r in tool.related(area["seeds"]) if r["volume"] >= cfg["min_monthly_volume"]]
        if cfg.get("relevance_filter", True):
            before = len(related)
            related = [r for r in related if related_to_seeds(r["keyword"], area["seeds"], [area["name"]] + (area.get("include_terms") or []))]
            cfg.setdefault("_dropped", []).append(f"{area['name']} {before - len(related)}개")
        related.sort(key=lambda r: r["volume"], reverse=True)
        kept = 0
        for r in related:
            key = r["keyword"].replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            rows.append({**r, "area_id": area["id"], "area_name": area["name"],
                         "affiliate_prior": area.get("affiliate", 3)})
            kept += 1
            if kept >= cfg["related_per_seed"] * len(area["seeds"]):
                break
    return rows


def run(sample: bool) -> int:
    cfg = load_yaml("global.yaml")
    areas = load_yaml("seeds.yaml")["areas"]
    run_date = date.today().isoformat()
    notes: list[str] = []

    if sample:
        from .sample import FakeHub, FakeKeywordTool, FakeYouTube
        tool, hub, yt = FakeKeywordTool(), FakeHub(), FakeYouTube()
        out_dir = ROOT / "reports" / "sample"
    else:
        missing = missing_secrets("naver_ad") + missing_secrets("naver_hub")
        if missing:
            msg = ("필요한 GitHub Secrets가 비어 있습니다: " + ", ".join(missing) +
                   "\n\n`docs/운영자-안내-Secrets-입력.md`의 순서대로 입력한 뒤 다시 실행하세요.")
            write_step_summary("# 시장조사 실행 중단\n\n" + msg)
            print(msg, file=sys.stderr)
            return 1
        from .naver_ad import KeywordTool
        from .naver_hub import ApiHub
        from .youtube import YouTube
        tool = KeywordTool(cfg["endpoints"]["naver_ad_base"])
        hub = ApiHub(cfg["endpoints"]["naver_hub"])
        yt = None
        if missing_secrets("youtube"):
            notes.append("YOUTUBE_API_KEY가 없어 유튜브 조회를 건너뜀 (점수·메모는 네이버 데이터만으로 계산)")
        else:
            y = cfg["youtube"]
            yt = YouTube(y["quota_budget"], y["region"], y["language"])
        out_dir = unique_dir(ROOT / "reports" / "market" / run_date)
        if not cfg["endpoints"]["naver_hub"].get("verified"):
            notes.append("API HUB 주소는 공식 문서로 아직 확인 전(verified: false). 이번 실행이 성공하면 확인된 것으로 보고 true로 바꾼다.")

    c = cfg["collect"]
    # ① 키워드 발굴
    collect_cfg = {**c, "exclude_keywords": cfg.get("exclude_keywords") or []}
    rows = collect_keywords(tool, areas, collect_cfg)
    if collect_cfg.get("_dropped"):
        notes.append("씨앗과 관련 없어 뺀 연관 키워드: " + ", ".join(collect_cfg["_dropped"]))
    print(f"연관 키워드 {len(rows)}개")
    if not rows:
        write_step_summary("# 시장조사 실행 중단\n\n연관 키워드를 하나도 받지 못했습니다. 씨앗 키워드나 최소 검색량 설정을 확인하세요.")
        return 1

    # ② 공급·이길 가능성: 블로그 문서 수와 상위 10개
    for r in rows:
        try:
            b = hub.blog(r["keyword"], c["blog_recent_n"])
        except ApiError as e:
            write_step_summary(f"# 시장조사 실행 중단\n\n블로그 검색 API 호출 실패: {e}\n\n"
                               "404면 API HUB 주소가, 401·403이면 키 또는 API HUB 이용 신청(블로그 검색 선택)이 원인일 가능성이 큽니다.")
            print(e, file=sys.stderr)
            return 1
        r["blog_total"], r["blog_items"] = b["total"], b["items"]

    # ② 수요 추세: 데이터랩 (실패해도 계속, 추세 0으로)
    try:
        trends = hub.trends([r["keyword"] for r in rows], c["trend_months"])
    except ApiError as e:
        trends = {}
        notes.append(f"데이터랩 검색어 트렌드 실패 → 추세 0으로 계산: {e}")
    for r in rows:
        t = trends.get(r["keyword"], {})
        r["trend"], r["seasonality"] = t.get("trend", 0.0), t.get("seasonality", 0.0)

    for area in areas:
        if area.get("shopping_category") and not sample:
            try:
                area["shopping"] = hub.shopping_category(area["name"], area["shopping_category"], c["trend_months"])
            except ApiError as e:
                notes.append(f"쇼핑 인사이트({area['name']}) 실패: {e}")

    scored = score(rows, cfg["weights"], cfg["regulated_terms"],
                   crowded_cap=cfg["verdict"]["crowded_monthly_posts"], display=c["blog_recent_n"])

    # ②-2 광고 키워드 도구가 못 보는 인물·스포츠 키워드: 데이터랩 상대값 × 기준 키워드 검색량으로 추정
    probes = estimate_probes(tool, hub, areas, cfg.get("demand_probe", {}), notes)

    # ③ 유튜브: 규제 제외 점수 상위만 (쿼터 보호)
    if yt is not None:
        y = cfg["youtube"]
        targets = [r for r in scored if not r["regulated"]][:y["top_keywords"]]
        for r in targets:
            try:
                r["youtube"] = yt.keyword(r["keyword"], y["videos_per_keyword"], y["outlier_ratio"])
            except Exception as e:  # 쿼터 초과 포함: 여기까지 받은 것으로 진행
                notes.append(f"유튜브 조회 중단 ({r['keyword']}): {e}")
                break
        notes.append(f"유튜브 쿼터 사용 {yt.used}단위 (예산 {y['quota_budget']}, 하루 한도 {y['daily_quota']})")

    # ④ 투자 메모 초안
    rep = cfg["report"]
    areas_ranked = area_summary(scored, rep["area_score_top"], rep["representative_keywords"])
    for a in areas_ranked:
        a["verdict"], a["verdict_reason"] = suggest_verdict(a, cfg["verdict"])
        a["affiliate_prior"] = next((x.get("affiliate", 3) for x in areas if x["id"] == a["area_id"]), 3)
        a["shopping"] = next((x.get("shopping") for x in areas if x["id"] == a["area_id"]), None)
    write_outputs(out_dir, run_date, scored, areas_ranked, notes, sample, rep["memos"], probes)
    return 0


def estimate_probes(tool, hub, areas: list[dict], cfg: dict, notes: list[str]) -> list[dict]:
    """seeds.yaml의 probe_keywords 검색량 추정. 기준 키워드의 실제 검색량(검색광고)에 데이터랩 비율을 곱한다."""
    anchor = cfg.get("anchor")
    wanted = [(a["name"], k) for a in areas for k in a.get("probe_keywords", [])]
    if not anchor or not wanted:
        return []
    try:
        rows = tool.related([anchor])
        base = next((r["volume"] for r in rows if r["keyword"].replace(" ", "") == anchor.replace(" ", "")), None)
        if not base:
            notes.append(f"검색량 추정 건너뜀: 기준 키워드 '{anchor}'의 검색량을 받지 못함")
            return []
        rel = hub.relative_last_month(anchor, [k for _, k in wanted])
    except ApiError as e:
        notes.append(f"검색량 추정 실패: {e}")
        return []
    notes.append(f"인물·스포츠 검색량은 추정치: 데이터랩 지난달 비율 × 기준 키워드 '{anchor}' 월 {int(base):,}회")
    out = [{"area": area, "keyword": k, "ratio": rel.get(k, 0.0), "est_volume": rel.get(k, 0.0) * base}
           for area, k in wanted]
    out.sort(key=lambda x: x["est_volume"], reverse=True)
    return out


def write_outputs(out_dir, run_date, scored, areas_ranked, notes, sample, memo_count, probes=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = report.summary_md(run_date, areas_ranked, scored, notes, sample, probes or [])
    (out_dir / "00-요약-점수표.md").write_text(summary, encoding="utf-8")
    memo_files = []
    for i, area in enumerate(areas_ranked[:memo_count], 1):
        name = f"memo-{i}-{area['area_id']}.md"
        (out_dir / name).write_text(report.memo_md(i, area, run_date, sample), encoding="utf-8")
        memo_files.append((name, area["area_name"]))
    (out_dir / "data.json").write_text(
        json.dumps({"date": run_date, "sample": sample, "keywords": scored, "probes": probes or [], "notes": notes},
                   ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    rel = out_dir.relative_to(ROOT)
    links = "\n".join(f"- [{t}]({n})" for n, t in memo_files)
    (out_dir / "README.md").write_text(
        f"# 시장조사 결과 · {run_date}\n\n{report.banner(sample)}- [요약·키워드 점수표](00-요약-점수표.md)\n{links}\n"
        "- [원자료 data.json](data.json)\n", encoding="utf-8")
    if not sample:
        (ROOT / "reports" / "LATEST.md").write_text(
            f"# 최신 시장조사\n\n{run_date} 실행 결과: [{rel}]({out_dir.relative_to(ROOT / 'reports')}/README.md)\n",
            encoding="utf-8")
    write_step_summary(summary + "\n## 투자 메모\n\n" + "\n".join(f"- {t}: `{rel}/{n}`" for n, t in memo_files))
    print(f"결과 저장: {rel}")


def unique_dir(path):
    """같은 날 다시 실행해도 이전 결과(Claude 검토가 채워진 메모 포함)를 덮어쓰지 않는다: 2026-09-29-2 식으로."""
    if not path.exists():
        return path
    n = 2
    while path.with_name(f"{path.name}-{n}").exists():
        n += 1
    return path.with_name(f"{path.name}-{n}")


def write_step_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="시장조사 실행")
    parser.add_argument("--sample", action="store_true", help="API 키 없이 예시 데이터로 실행")
    args = parser.parse_args()
    sys.exit(run(args.sample))


if __name__ == "__main__":
    main()
