"""순위 자동 지표 수집(우리가 이미 쓰는 네이버 검색광고 API·API HUB 데이터랩 + 애플 앱 조회 API).

- 대상: web/content/rankings/*.json 중 앱에 'metrics' 설정이 있는 것(평가 대기 제외).
- 항목(자동, 모두 재현 가능한 공개 지표 · 점수마다 evidence에 출처·값·확인일을 남긴다):
    awareness  인지도     = 네이버 월간 검색수(PC+모바일, 검색광고 API) → 로그 환산 (100회=0점, 100만회=5점)
    interest   최근 관심도 = 데이터랩 검색어 트렌드, 최근 4주 평균 상대값(같은 요청 안 최댓값=100) → 0~5
    rating     이용자 평점 = 애플 iTunes Search API(공식 문서 있는 공개 API) 평균 평점. 평가 1,000건 미만이면 비움
  수수료·표시광고 이력 같은 항목은 사람이 근거 링크와 함께 입력(type: manual)한다. AI 추정 점수는 쓰지 않는다.
- 어떤 지표든 수집에 실패하면 기존 값을 그대로 둔다(키가 없거나 API 오류여도 안전).

사용: python -m content.rank_metrics [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from market.common import ROOT, load_yaml, missing_secrets, request_json

RANK_DIR = ROOT / "web" / "content" / "rankings"
KST = timezone(timedelta(hours=9))
MIN_RATING_COUNT = 1000
ITUNES = "https://itunes.apple.com/search"


# ---- 순수 계산(테스트 대상) ----------------------------------------------------
def volume_to_score(volume: float) -> float:
    """월간 검색수 → 0~5. 100회=0, 1만회=2.5, 100만회=5 (로그)."""
    if volume <= 100:
        return 0.0
    return round(min(5.0, (math.log10(volume) - 2) * 1.25), 1)


def interest_to_score(weekly_ratios: list[float]) -> float | None:
    """데이터랩 주간 상대값 최근 4주 평균(0~100) → 0~5. 데이터가 4주 미만이면 None."""
    if len(weekly_ratios) < 4:
        return None
    avg = sum(weekly_ratios[-4:]) / 4
    return round(min(5.0, avg / 100 * 5), 1)


def rating_to_score(rating: float | None, count: int | None) -> float | None:
    if rating is None or not count or count < MIN_RATING_COUNT:
        return None
    return round(max(0.0, min(5.0, float(rating))), 1)


def _norm(s: str) -> str:
    return re.sub(r"[\s·\-_()]", "", s or "").lower()


def pick_apple_result(results: list[dict], term: str, seller_contains: str = "") -> dict | None:
    """iTunes 검색 결과 중 앱 이름에 검색어가 들어 있고(판매자 조건이 있으면 판매자도 맞는) 첫 결과."""
    for r in results:
        if _norm(term) not in _norm(r.get("trackName", "")):
            continue
        if seller_contains and _norm(seller_contains) not in _norm(r.get("sellerName", "")):
            continue
        return r
    return None


def fmt_int(n: float) -> str:
    return f"{int(round(n)):,}"


# ---- 외부 호출 ---------------------------------------------------------------
def fetch_volumes(keywords: list[str]) -> dict[str, float]:
    """네이버 검색광고 API 월간 검색수. 키워드(공백 제거)와 정확히 같은 행의 PC+모바일 합."""
    from market.naver_ad import KeywordTool
    cfg = load_yaml("global.yaml")
    tool = KeywordTool(cfg["endpoints"]["naver_ad_base"])
    out: dict[str, float] = {}
    for kw in keywords:
        rows = tool.related([kw])
        key = kw.replace(" ", "")
        for r in rows:
            if r["keyword"].replace(" ", "") == key:
                out[kw] = r["volume"]
                break
        time.sleep(0.3)
    return out


def fetch_weekly_ratios(keywords: list[str], weeks: int = 8) -> dict[str, list[float]]:
    """데이터랩 검색어 트렌드(API HUB) 주간 상대값. 한 요청에 최대 5개를 함께 보내 같은 기준(최댓값=100)으로 비교한다."""
    from market.naver_hub import ApiHub, MAX_GROUPS
    cfg = load_yaml("global.yaml")
    hub = ApiHub(cfg["endpoints"]["naver_hub"])
    end = date.today() - timedelta(days=1)
    start = end - timedelta(weeks=weeks)
    out: dict[str, list[float]] = {}
    for i in range(0, len(keywords), MAX_GROUPS):
        batch = keywords[i:i + MAX_GROUPS]
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "week",
                "keywordGroups": [{"groupName": k, "keywords": [k]} for k in batch]}
        data = request_json("POST", hub.base + hub.paths["search_trend"],
                            headers={**hub._headers(), "Content-Type": "application/json"}, json=body)
        for res in data.get("results", []):
            out[res.get("title", "")] = [float(p.get("ratio", 0)) for p in res.get("data", [])]
        time.sleep(0.2)
    return out


def fetch_apple(term: str) -> list[dict]:
    data = request_json("GET", ITUNES, params={"term": term, "country": "kr", "entity": "software", "limit": 8})
    return data.get("results", [])


# ---- 파일 갱신 -----------------------------------------------------------------
def _set(app: dict, key: str, score, evidence: dict) -> None:
    app.setdefault("scores", {})
    app.setdefault("evidence", {})
    if score is None:
        return  # 못 구한 값은 기존 값 유지
    app["scores"][key] = score
    app["evidence"][key] = evidence


def update_file(path: Path, dry: bool = False) -> int:
    d = json.loads(path.read_text(encoding="utf-8"))
    apps = [a for a in d.get("apps", []) if a.get("metrics") and not a.get("pending")]
    if not apps:
        return 0
    today = datetime.now(KST).strftime("%Y-%m-%d")
    kws = [a["metrics"]["keyword"] for a in apps]
    changed = 0
    try:
        vols = fetch_volumes(kws)
    except Exception as e:  # noqa: BLE001
        print(f"[{path.name}] 검색광고 API 실패: {type(e).__name__}: {e}"); vols = {}
    try:
        ratios = fetch_weekly_ratios(kws)
    except Exception as e:  # noqa: BLE001
        print(f"[{path.name}] 데이터랩 실패: {type(e).__name__}: {e}"); ratios = {}
    for a in apps:
        m = a["metrics"]
        kw = m["keyword"]
        if kw in vols:
            _set(a, "awareness", volume_to_score(vols[kw]), {
                "type": "auto", "source": "네이버 검색광고 API",
                "label": f"'{kw}' 월 검색수 {fmt_int(vols[kw])}회", "checked": today})
            changed += 1
        if kw in ratios:
            sc = interest_to_score(ratios[kw])
            if sc is not None:
                avg = sum(ratios[kw][-4:]) / 4
                _set(a, "interest", sc, {
                    "type": "auto", "source": "네이버 데이터랩 검색어 트렌드",
                    "label": f"'{kw}' 최근 4주 관심도 {avg:.0f}/100(같은 비교 그룹 내 상대값)", "checked": today})
                changed += 1
        if m.get("apple_term"):
            try:
                hit = pick_apple_result(fetch_apple(m["apple_term"]), m["apple_term"], m.get("apple_seller", ""))
            except Exception as e:  # noqa: BLE001
                print(f"[{a['slug']}] 애플 조회 실패: {type(e).__name__}: {e}"); hit = None
            if hit:
                sc = rating_to_score(hit.get("averageUserRating"), hit.get("userRatingCount"))
                if sc is not None:
                    _set(a, "rating", sc, {
                        "type": "auto", "source": "Apple App Store(iTunes Search API)", "url": hit.get("trackViewUrl", ""),
                        "label": f"iOS 평점 {sc:.1f} ({fmt_int(hit['userRatingCount'])}건){m.get('rating_note', '')}",
                        "checked": today})
                    changed += 1
            time.sleep(0.3)
    if changed:
        d["metricsUpdated"] = today
        d["updated"] = today
        if not dry:
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{path.name}] 자동 지표 {changed}개 갱신")
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="순위 자동 지표 수집")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    miss = missing_secrets("naver_ad") + missing_secrets("naver_hub")
    if miss:
        print("네이버 키 없음 — 검색광고·데이터랩 지표는 건너뜀:", ", ".join(miss))
    for f in sorted(RANK_DIR.glob("*.json")):
        try:
            update_file(f, dry=args.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"[{f.name}] 실패: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
