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


def area_summary(scored: list[dict], per_area: int = 5) -> list[dict]:
    """영역(주제 후보)별로 묶는다. 규제 키워드는 순위 계산에서 빼고 따로 센다."""
    areas: dict[str, dict] = {}
    for r in scored:
        a = areas.setdefault(r["area_id"], {"area_id": r["area_id"], "area_name": r["area_name"],
                                             "keywords": [], "regulated": []})
        (a["regulated"] if r["regulated"] else a["keywords"]).append(r)
    result = []
    for a in areas.values():
        top = a["keywords"][:per_area]
        a["top"] = top
        a["area_score"] = round(sum(k["score"] for k in top) / len(top), 1) if top else 0.0
        a["total_volume"] = sum(k["volume"] for k in a["keywords"])
        result.append(a)
    result.sort(key=lambda a: a["area_score"], reverse=True)
    return result
