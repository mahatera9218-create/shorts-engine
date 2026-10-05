"""키워드 모으기·점수 매기기 (대표 지시 2026-10-05: "Grok만 믿지 말고, 소스가 겹치면 우선순위").

1) 모으기(허용된 통로만): Grok(X·웹) · 참고 블로거 어제·오늘 글(공개 RSS, zkfldb888 최우선) · 국내 경제 RSS ·
   야후 파이낸스 등 해외 RSS · 업비트 시세 급변 · 대표가 넣은 키워드(어드바이저·뉴스 랭킹·트렌드·캡처)
2) 묶기(Claude): 같은 이야기를 한 키워드로 묶고, 어느 줄(번호)에서 나왔는지 적게 한다 → 출처는 코드가 번호로 다시 센다
3) 점수(코드, 100점): 출처 겹침 40 + 네이버 뉴스량 20(최근 24시간 기사 수) + 검색 수요 25(검색광고 월간 검색량)
   + 오늘 블로그 빈자리 15(최근 24시간 블로그 글이 적을수록). 네이버 뉴스 '랭킹' 화면은 공식 통로가 없어 뉴스 검색 API로 대신한다.
설정: config/econ_keywords.yaml, config/econ_refs.yaml
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests

from market.common import ROOT, load_yaml, request_json, secret
from . import econ_flow as F

CFG = ROOT / "config" / "econ_keywords.yaml"
UA = {"User-Agent": "Mozilla/5.0 (eok-econ keyword reader; RSS)"}


# ---------------------------------------------------------------- 1) 모으기

def headlines(url: str, hours: int = 24) -> list[str]:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        since = datetime.now(F.KST) - timedelta(hours=hours)
        out = []
        for it in ET.fromstring(r.content).iter("item"):
            try:
                if parsedate_to_datetime(it.findtext("pubDate") or "") < since:
                    continue
            except (TypeError, ValueError):
                pass
            t = (it.findtext("title") or "").strip()
            if t:
                out.append(t)
        return out[:25]
    except Exception as e:  # noqa: BLE001
        print(f"RSS 실패 {url[:60]}: {type(e).__name__}")
        return []


def gather(grok_items: list[dict], mine: list[dict]) -> list[tuple[str, str, str]]:
    """(번호, 출처 이름, 내용) 줄 목록. 출처 이름은 점수표(source_points)의 이름과 같다."""
    cfg = F.load(CFG, {})
    rows: list[tuple[str, str, str]] = []
    for i, it in enumerate(mine, 1):
        rows.append((f"D{i}", "캡처" if str(it.get("why", "")).startswith("📷") else "대표", it["kw"]))
    for i, it in enumerate(grok_items, 1):
        rows.append((f"G{i}", "Grok", f"{it['kw']} — {it.get('why', '')}"))
    refs = F.load(ROOT / "econ" / "ref" / "rss" / f"{F.today()}.yaml", {})
    main = F.load(ROOT / "config" / "econ_refs.yaml", {}).get("main", "")
    n = 0
    for b in refs.get("bloggers", []):
        for t in b.get("recent", []):
            n += 1
            rows.append((f"B{n}", b["id"] if b["id"] == main else "블로거", f"[{b['id']}] {t}"))
    for kind in ("국내뉴스", "해외뉴스"):
        n = 0
        for url in cfg.get("feeds", {}).get(kind, []):
            for t in headlines(url):
                n += 1
                rows.append((f"{'N' if kind == '국내뉴스' else 'Y'}{n}", kind, t))
    for i, it in enumerate(F.price_moves(), 1):
        rows.append((f"P{i}", "시세", f"{it['kw']} — {it['why']}"))
    return rows


CLUSTER = {"type": "object", "additionalProperties": False, "required": ["keywords"],
           "properties": {"keywords": {"type": "array", "items": {
               "type": "object", "additionalProperties": False,
               "required": ["kw", "area", "why", "person", "rows"],
               "properties": {
                   "kw": {"type": "string", "description": "네이버에서 사람들이 실제로 칠 검색어 (2~4단어, 한국어)"},
                   "area": {"type": "string", "enum": F.AREAS},
                   "why": {"type": "string", "description": "왜 오늘 쓸 만한지 한 줄"},
                   "person": {"type": "string", "description": "관련 인물이 있으면 회사+이름(예: 삼성 이재용), 없으면 빈칸"},
                   "rows": {"type": "array", "items": {"type": "string"}, "description": "이 키워드가 나온 줄 번호 전부 (예: G2, B5, N13)"}}}}}}


def cluster(rows: list[tuple[str, str, str]]) -> list[dict]:
    text = "\n".join(f"{rid} ({src}) {t}" for rid, src, t in rows)
    res = F.claude_json(
        ["너는 경제 블로그 편집장이다. 한국 개인 투자자·직장인이 오늘 네이버에서 찾아볼 경제·돈 주제를 고른다. "
         "작전주·테마주 추천·리딩방·정치 싸움은 뺀다. 줄에 없는 주제를 지어내지 않는다."],
        f"오늘은 {F.today()}(한국 시간). 아래는 여러 출처에서 모은 줄입니다(번호와 출처 표시). 같은 이야기는 한 키워드로 묶고, "
        "키워드마다 그 이야기가 나온 줄 번호를 빠짐없이 적어 주세요. 해외 기사는 한국 독자가 찾을 한국어 검색어로 바꿔 주세요. "
        "D로 시작하는 줄(대표가 넣은 키워드)은 하나도 빠뜨리지 말고 그대로 키워드로 두세요. 키워드는 최대 15개.\n\n" + text,
        CLUSTER, stage="키워드 묶기")
    return res["keywords"]


# ---------------------------------------------------------------- 3) 점수

def _hub():
    from market.naver_hub import ApiHub
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    return ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])


def _recent_count(hub, path: str, kw: str) -> tuple[int, int]:
    """(최근 24시간 글 수(최대 100), 전체 문서 수)."""
    data = request_json("GET", hub.base + hub.paths[path], headers=hub._headers(),
                        params={"query": kw, "display": 100, "sort": "date"})
    since = datetime.now(F.KST) - timedelta(hours=24)
    n = 0
    for it in data.get("items", []):
        raw = it.get("pubDate") or it.get("postdate") or ""
        try:
            at = parsedate_to_datetime(raw) if "," in raw else datetime.strptime(raw, "%Y%m%d").replace(tzinfo=F.KST)
        except (TypeError, ValueError):
            continue
        n += at >= (since if "," in raw else since.replace(hour=0, minute=0))
    return n, int(data.get("total") or 0)


def _volumes(kws: list[str]) -> dict[str, float]:
    if not all(secret(k) for k in ("NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY", "NAVER_AD_CUSTOMER_ID")):
        return {}
    from market.naver_ad import KeywordTool
    tool = KeywordTool(load_yaml("global.yaml")["endpoints"]["naver_ad_base"])
    out = {}
    try:
        rows = tool.related([k.replace(" ", "") for k in kws])
        by = {r["keyword"]: r["volume"] for r in rows}
        for k in kws:
            out[k] = by.get(k.replace(" ", ""), 0.0)
    except Exception as e:  # noqa: BLE001
        print(f"검색광고 실패: {str(e)[:120]}")
    return out


def score(items: list[dict], src_rows: dict[str, str]) -> list[dict]:
    """items: {kw, rows[...]} → score·parts·sources를 채워 점수순으로."""
    cfg = F.load(CFG, {})
    pts, caps = cfg.get("source_points", {}), cfg.get("caps", {})
    hub = _hub()
    vols = _volumes([it["kw"] for it in items])
    for it in items:
        cnt: dict[str, int] = {}
        for rid in it.get("rows", []):
            s = src_rows.get(rid)
            if s:
                cnt[s] = cnt.get(s, 0) + 1
        src_pts = 0.0
        for s, c in cnt.items():
            p = pts.get(s, 0) * (c if s in ("블로거", "국내뉴스", "해외뉴스") else 1)
            src_pts += min(p, caps.get(s, p))
        src_pts = min(40.0, src_pts)
        news = blog = None
        if hub:
            try:
                news, _ = _recent_count(hub, "news_search", it["kw"])
                blog, _ = _recent_count(hub, "blog_search", it["kw"])
            except Exception as e:  # noqa: BLE001
                print(f"네이버 검색 실패 {it['kw']}: {str(e)[:80]}")
        vol = vols.get(it["kw"])
        parts = {"출처": round(src_pts),
                 "뉴스": round(20 * min(news, 100) / 100) if news is not None else 0,
                 "검색": round(min(25.0, max(0.0, (math.log10(vol) - 2) * 8.3))) if vol else 0,
                 "빈자리": round(15 * (1 - min(blog, 100) / 100)) if blog is not None else 0}
        it.update(score=sum(parts.values()), parts=parts, sources=cnt,
                  stats={"뉴스24h": news, "블로그24h": blog, "월검색": int(vol) if vol else None})
    return sorted(items, key=lambda x: -x["score"])


def run(grok_items: list[dict], mine: list[dict]) -> list[dict]:
    rows = gather(grok_items, mine)
    print(f"모은 줄 {len(rows)}개: " + ", ".join(f"{s} {sum(1 for r in rows if r[1] == s)}"
                                            for s in dict.fromkeys(r[1] for r in rows)))
    if not rows:
        return []
    items = cluster(rows)
    src_rows = {rid: src for rid, src, _ in rows}
    for it in items:
        it["rows"] = [r for r in it["rows"] if r in src_rows]
        it["src"] = ", ".join(sorted({src_rows[r] for r in it["rows"]})) or "?"
    # 대표가 넣은 키워드가 묶기에서 빠졌으면 그대로 살린다
    have = {r for it in items for r in it["rows"]}
    for rid, src, t in rows:
        if rid.startswith("D") and rid not in have:
            items.append({"kw": t, "area": "", "why": "대표가 넣음", "person": "", "rows": [rid], "src": src})
    return score(items, src_rows)
