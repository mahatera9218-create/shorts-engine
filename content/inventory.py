"""콘텐츠 재고: 지금 풀·테마·비교 물건으로 쓸 수 있는 글 조합이 얼마나 남았나 (대표 결정 2026-09-30: 콘텐츠가 마르지 않게).

- 조합 = (테마, 선수들[, 물건]). 같은 조합은 USED_DAYS(120일) 안에 다시 쓰지 않는다 (autopost.used_combos).
- 결과: reports/콘텐츠-재고-<날짜>.md. 주간 점검 때 보고, 모자라는 테마는 선수·물건·테마를 늘린다.
사용법: python -m content.inventory
"""
from __future__ import annotations

from datetime import date
from itertools import combinations

from market.common import ROOT, load_yaml
from .autopost import USED_DAYS, eligible, places_for, used_combos


def kind(pool: dict, p: dict) -> str:
    return pool["sports"].get(p["sport"], {}).get("sport", p["sport"])


def count(pool: dict) -> dict[str, int]:
    ps = pool["players"]
    el = eligible(pool)
    items = len(load_yaml("prices.yaml")["items"])
    pairs = list(combinations(ps, 2))
    places = {p["name"]: places_for(pool, p) for p in ps}
    return {"life": len(ps) * items,
            "place": sum(sum(x["domestic"] for x in v) for v in places.values()),
            "trip": sum(len(v) for v in places.values()),
            "tax": len(el["tax"]),
            "receipt": len(ps),
            "same": sum(kind(pool, a) == kind(pool, b) for a, b in pairs),
            "jersey": len(el["jersey"]),
            "cross": sum(kind(pool, a) != kind(pool, b) for a, b in pairs)}


def report(today: str) -> str:
    pool = load_yaml("players.yaml")
    total = count(pool)
    used, used_items = used_combos(today, days=10_000)
    used_by = {}
    for th, _ in used:
        used_by[th] = used_by.get(th, 0) + 1
    for keys in used_items.values():  # 장소 테마는 (선수, 장소)가 조합
        for k in keys:
            th = "place" if str(k).startswith("apt_") else "trip" if str(k).startswith("trip_") else None
            if th:
                used_by[th] = used_by.get(th, 0) + 1
    w = {k: v["weight"] for k, v in pool["themes"].items()}
    ws = sum(w.values())
    L = [f"# 콘텐츠 재고 · {today}", "",
         f"하루 1편 기준. 같은 조합은 {USED_DAYS}일 안에 다시 쓰지 않는다. '며칠 치'는 새 조합만 셌을 때 그 테마가 버티는 날수",
         "(테마 확률로 나눔). 새 시즌 연봉·성적이 나오면 같은 조합도 새 글이 된다.", "",
         "| 테마 | 확률 | 새 조합 전체 | 쓴 조합 | 남은 조합 | 며칠 치 |", "| --- | --- | --- | --- | --- | --- |"]
    left_days = []
    for th, n in total.items():
        p = w.get(th, 0) / ws
        left = max(0, n - used_by.get(th, 0))
        days = int(left / p) if p else 0
        left_days.append(days)
        L.append(f"| {pool['themes'][th]['name']} | {p:.0%} | {n:,} | {used_by.get(th, 0)} | {left:,} | {days:,}일 |")
    L += ["", f"가장 먼저 마르는 테마까지 약 **{min(left_days):,}일**. 선수 {len(pool['players'])}명, "
          f"비교 물건 {len(load_yaml('prices.yaml')['items'])}개 기준.", "",
          "## 마르지 않게 하는 장치", "",
          "- 선수: 댓글 요청·뉴스 많은 선수를 풀에 추가 (config/requests.yaml, players.yaml)",
          "- 물건: 생활 물가·유니폼 가격을 늘림 (config/prices.yaml, goods.yaml)",
          "- 테마: 광고 단가를 재서 새 테마를 붙임 (config/ideas.yaml → market/ad_value.py)",
          "- 시즌 달력: 연봉 발표(1~2월)·개막(3월)·올스타(7월)·시즌 종료(10월)·FA(11~12월)·이적시장(여름·겨울)마다 같은 선수도 새 숫자",
          "- 재사용: 120일이 지나면 같은 조합도 최신 성적으로 다시 쓸 수 있다"]
    return "\n".join(L) + "\n"


def main() -> None:
    today = date.today().isoformat()
    text = report(today)
    out = ROOT / "reports" / f"콘텐츠-재고-{today}.md"
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
