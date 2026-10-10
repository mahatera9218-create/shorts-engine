"""네이버 급상승 탐지 — 어사이드 없이 공식 API로 (대표 요청 2026-10-10 "어사이드 안 쓰고 네이버 조사", "주기적으로 돌아서 보여 줘").

1) 씨앗 키워드(config rising_seeds) → 네이버 검색광고 API 연관 키워드 + 월 검색량 (사람들이 실제로 치는 말)
2) 검색어 트렌드(API HUB, 일 단위) → 최근 3일 검색이 그 전 11일 평균보다 얼마나 올랐나
3) 블로그 검색 API → 지난 24시간 새 블로그 글 수 (지금 쓰이는 중인가)
→ <flow>/<날짜>/rising.yaml, 도우미 '📈 네이버 급상승' 칸. AI 비용 없음.
한계: 검색어 트렌드는 어제까지 데이터라 실시간 홈판보다 하루 늦다.
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from . import econ_flow as F

N_CAND, N_FRESH, N_SHOW = 150, 40, 15
NAME_PT, BROAD_PT = 20, -15  # 회사·연예인 이름이 든 키워드는 올리고, 이름 없는 넓은 말은 내림 (대표 요청 2026-10-10)


def run() -> None:
    from .econ_score import CFG, _hub, _recent_count
    from market.common import load_yaml, secret
    from market.naver_ad import KeywordTool
    cfg = F.load(CFG(), {}) or {}
    seeds = cfg.get("rising_seeds") or []
    min_vol = cfg.get("rising_min_volume", 2000)
    if not seeds or not all(secret(k) for k in ("NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY", "NAVER_AD_CUSTOMER_ID")):
        print("급상승: 씨앗이 없거나 검색광고 키가 없어 건너뜀")
        return
    # 1) 연관 키워드 + 월 검색량
    tool = KeywordTool(load_yaml("global.yaml")["endpoints"]["naver_ad_base"])
    rows = tool.related(seeds)
    vol: dict[str, float] = {}
    for r in rows:
        k = (r.get("keyword") or "").strip()
        if 2 <= len(k) <= 20 and r.get("volume", 0) >= min_vol and not re.fullmatch(r"[\d\W]+", k):
            vol[k] = max(vol.get(k, 0), r["volume"])
    # 회사·연예인 명단 (config rising_entities): 그 자체도 후보로 넣고, 이름이 든 키워드에 가점
    names = [n.strip() for n in cfg.get("rising_entities") or [] if n.strip()]
    if F.BLOG["id"] == "fashion":  # 착장 도우미 '오늘 뜨는 연예인'도 후보로
        from .outfit import OUT
        cel = F.load(OUT / F.today() / "celebs.yaml", {}) or {}
        names += [c["name"] for c in cel.get("items", []) if c.get("name")]
    names = list(dict.fromkeys(names))
    if names:
        from .econ_score import _volumes
        for n, v in _volumes(names).items():
            vol[n.replace(" ", "")] = max(vol.get(n.replace(" ", ""), 0), v or 0)
    keyed = [n.replace(" ", "") for n in names]
    topics = [t.replace(" ", "") for t in cfg.get("rising_topics") or []]  # 부동산·환율·생활경제 말 (2026-10-10)
    def has_name(k: str) -> bool:
        return any(n and n in k for n in keyed + topics)
    if F.BLOG["id"] == "econ":  # 정부 지원금·정책 안내는 안 씀 (대표 결정 2026-10-10)
        from .econ_sections import POLICY
        vol = {k: v for k, v in vol.items() if not POLICY.search(k)}
    ent = [k for k in vol if has_name(k)]
    rest = [k for k in sorted(vol, key=lambda k: -vol[k]) if k not in ent]
    cands = (sorted(ent, key=lambda k: -vol[k]) + rest)[:N_CAND]
    hub = _hub()
    if not hub or not cands:
        print("급상승: 후보가 없거나 API HUB 키가 없음")
        return
    # 2) 최근 3일 상승률
    rises = hub.rise(cands)
    scored = []
    for k in cands:
        r = (rises.get(k) or {}).get("rise", 0.0)
        steady = any(t in k for t in topics) and vol[k] >= 10000  # 아파트·금리·환율처럼 늘 많이 찾는 생활 말은 줄지만 않으면 (2026-10-10)
        if r < (1.0 if steady else 1.2):  # 평소보다 20% 이상 오른 것만
            continue
        rise_pt = min(60, (r - 1) * 60)  # 평소의 2배면 60점
        vol_pt = min(40, max(0.0, (math.log10(vol[k]) - 3) / 3 * 40)) if vol[k] > 0 else 0  # 1천 → 0점, 100만 → 40점
        named = has_name(k)
        scored.append({"kw": k, "rise": r, "volume": int(vol[k]), "named": named,
                       "pt": rise_pt + vol_pt + (NAME_PT if named else BROAD_PT)})
    scored.sort(key=lambda x: -x["pt"])
    pool = scored[:N_FRESH]
    if F.BLOG["id"] == "econ":  # 새 글 수를 잴 후보에 섹션마다 3개는 넣기 (점수 낮은 생활 말이 잘리지 않게)
        from .econ_sections import section
        per: dict[str, int] = {}
        extra = []
        for it in scored:
            sec = section({"kw": it["kw"]})
            per[sec] = per.get(sec, 0) + 1
            if per[sec] <= 3 and it not in pool:
                extra.append(it)
        pool = pool + extra
    # 3) 지난 24시간 새 블로그 글 수 (지금 쓰이는 중인가)
    for it in pool:
        try:
            it["blog24h"], _ = _recent_count(hub, "blog_search", it["kw"])
        except Exception as e:  # noqa: BLE001
            print(f"블로그 검색 실패 {it['kw']}: {str(e)[:80]}")
            it["blog24h"] = None
        it["pt"] += min(20, (it["blog24h"] or 0) / 5)  # 24시간 새 글 100개면 20점
    items = sorted(pool, key=lambda x: -x["pt"])
    if F.BLOG["id"] == "econ":  # 섹션마다 4개까지 — 회사만 몰리지 않고 부동산·환율·생활경제도 보이게 (2026-10-10)
        from .econ_sections import section
        for it in items:
            it["section"] = section({"kw": it["kw"]})
        # 섹션마다 2개는 먼저 자리 보장, 남은 자리는 점수순 (섹션당 4개까지) — 회사만 15개를 차지하지 않게
        first, cnt = [], {}
        for it in items:
            if cnt.get(it["section"], 0) < 2:
                cnt[it["section"]] = cnt.get(it["section"], 0) + 1
                first.append(it)
        rest = [it for it in items if it not in first]
        for it in rest:
            if len(first) >= N_SHOW:
                break
            if cnt.get(it["section"], 0) < 4:
                cnt[it["section"]] = cnt.get(it["section"], 0) + 1
                first.append(it)
        items = sorted(first, key=lambda x: -x["pt"])
    items = items[:N_SHOW]
    for it in items:
        it["score"] = round(it.pop("pt"))
    out = F.FLOW / F.today() / "rising.yaml"
    F.save(out, {"date": F.today(), "updated": datetime.now(F.KST).strftime("%H:%M"), "items": items})
    if F.BLOG["id"] == "econ":
        print("섹션별:", {k: sum(1 for it in items if it.get("section") == k) for k in dict.fromkeys(it.get("section") for it in items)})
        print("생활 말 상승률(상위 10):", [(k, round((rises.get(k) or {}).get("rise", 0), 2)) for k in cands if any(t in k for t in topics)][:10])
    print(f"급상승 {len(items)}개 → {out}" + (f" (1위 {items[0]['kw']} ×{items[0]['rise']})" if items else ""))
