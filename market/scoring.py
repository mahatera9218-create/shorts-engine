"""틈새 점수 (설계서 0.3). LLM을 쓰지 않는 순수 계산.

틈새 점수 = 수요^a × 가치^b × 이길가능성^c × 제휴가치^d ÷ 공급^e
각 축은 이번 실행의 키워드들 안에서 0~1로 정규화한다(상대 점수).
0이 되면 곱이 사라지므로 축마다 바닥값 FLOOR를 둔다.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from statistics import median

FLOOR = 0.05
MAX_AD_DEPTH = 15  # 네이버 파워링크 최대 노출 수 기준


def _log(x: float) -> float:
    return math.log10(1 + max(x, 0))


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _floor(x: float) -> float:
    return max(FLOOR, min(1.0, x))


def median_age_days(postdates: list[str], today: date | None = None) -> float | None:
    """상위 글 발행일(YYYYMMDD)의 중앙값 나이(일). 오래될수록 기회."""
    today = today or date.today()
    ages = []
    for p in postdates:
        try:
            ages.append((today - datetime.strptime(p, "%Y%m%d").date()).days)
        except (TypeError, ValueError):
            continue
    return median(ages) if ages else None


def regulated_category(keyword: str, terms: dict[str, list[str]]) -> str | None:
    for category, words in terms.items():
        if any(w in keyword for w in words):
            return category
    return None


def score(rows: list[dict], weights: dict, regulated_terms: dict, today: date | None = None) -> list[dict]:
    """rows: 키워드별 수집 결과(수요·가치·공급·상위글·제휴 사전값). 점수를 붙여 내림차순으로 돌려준다."""
    if not rows:
        return []
    demand_raw = _minmax([_log(r["volume"]) for r in rows])
    clicks_raw = _minmax([_log(r["clicks"]) for r in rows])
    supply_raw = _minmax([_log(r.get("blog_total", 0)) for r in rows])

    out = []
    for i, r in enumerate(rows):
        trend = max(-0.3, min(0.3, r.get("trend", 0.0)))
        demand = _floor(demand_raw[i] * (1 + trend))
        value = _floor((r["competition_level"] / 3 + min(r["ad_depth"] / MAX_AD_DEPTH, 1) + clicks_raw[i]) / 3)
        age = median_age_days([it["postdate"] for it in r.get("blog_items", [])], today)
        win = _floor(age / 365) if age is not None else 0.5
        affiliate = _floor(r.get("affiliate_prior", 3) / 5)
        supply = _floor(supply_raw[i])

        raw = (demand ** weights["demand"] * value ** weights["value"] * win ** weights["win"]
               * affiliate ** weights["affiliate"]) / supply ** weights["supply"]
        out.append({
            **r,
            "axes": {"demand": demand, "value": value, "win": win, "affiliate": affiliate, "supply": supply},
            "top_median_age_days": age,
            "raw_score": raw,
            "regulated": regulated_category(r["keyword"], regulated_terms),
        })
    top = max(x["raw_score"] for x in out) or 1
    for x in out:
        x["score"] = round(100 * x["raw_score"] / top, 1)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def area_summary(scored: list[dict], score_top: int = 5, show: int = 10) -> list[dict]:
    """영역(주제 후보)별로 묶는다. 규제 키워드는 순위 계산에서 빼고 따로 센다.

    주제 점수 = 규제 제외 상위 score_top개 키워드 점수 평균. 메모에는 대표 키워드 show개를 싣는다.
    """
    areas: dict[str, dict] = {}
    for r in scored:
        a = areas.setdefault(r["area_id"], {"area_id": r["area_id"], "area_name": r["area_name"],
                                             "keywords": [], "regulated": []})
        (a["regulated"] if r["regulated"] else a["keywords"]).append(r)
    result = []
    for a in areas.values():
        top = a["keywords"][:score_top]
        a["top"] = top
        a["representative"] = a["keywords"][:show]
        a["area_score"] = round(sum(k["score"] for k in top) / len(top), 1) if top else 0.0
        a["total_volume"] = sum(k["volume"] for k in a["keywords"])
        result.append(a)
    result.sort(key=lambda a: a["area_score"], reverse=True)
    return result


def suggest_verdict(area: dict, rules: dict) -> tuple[str, str]:
    """스킬의 판정 기준 중 코드로 판단할 수 있는 부분만 적용한 제안.

    '진입'은 정보 이득 수단이 구체적으로 있어야 하므로 코드는 '진입 후보'까지만 말한다.
    """
    top = area["top"]
    if not top:
        return "제외", "규제 아닌 키워드가 없음"
    if len(area["regulated"]) > len(area["keywords"]):
        return "제외", "규제 업종 키워드 비중이 큼 (법률 검토 전 진입 안 함)"
    trend = sum(k.get("trend", 0) for k in top) / len(top)
    if trend <= rules["declining_trend"]:
        return "제외", f"수요 하락 추세 (상위 키워드 평균 {trend * 100:+.0f}%)"
    ages = [k["top_median_age_days"] for k in top if k.get("top_median_age_days") is not None]
    if ages and median(ages) < rules["fresh_top_days"]:
        return "제외", f"상위 10개가 최근 글로 꽉 참 (발행일 중앙값 {median(ages):.0f}일)"
    win = sum(k["axes"]["win"] for k in top) / len(top)
    if win < rules["low_win"]:
        return "보류", f"이길 가능성 낮음 ({win:.2f})"
    return "진입 후보", "점수 상위·규제 아님. 정보 이득 수단 확인 필요"
