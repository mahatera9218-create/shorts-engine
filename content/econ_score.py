"""키워드 모으기·점수 매기기 (대표 지시 2026-10-05: "Grok만 믿지 말고, 소스가 겹치면 우선순위").

1) 모으기(허용된 통로만): Grok(X·웹) · 참고 블로거 어제·오늘 글(공개 RSS, zkfldb888 최우선) · 국내 경제 RSS ·
   야후 파이낸스 등 해외 RSS · 업비트 시세 급변 · 대표가 넣은 키워드(어드바이저·뉴스 랭킹·트렌드·캡처)
2) 묶기(Claude): 같은 이야기를 한 키워드로 묶고, 어느 줄(번호)에서 나왔는지 적게 한다 → 출처는 코드가 번호로 다시 센다
   + 인기 종목(국내·미국 대표 종목 중 24시간 네이버 기사가 많은 것, config watch)
3) 점수(코드, 100점): 홈판 재정의 2026-10-10 → 화제성(네이버인기·검색어트렌드 급상승·뉴스량·최신·출처겹침) 67 : 수요(검색광고 월 검색량) 33 = 2:1. weights는 블로그 config.
   네이버 뉴스 '랭킹' 화면은 공식 통로가 없어 뉴스 검색 API로 대신한다.
설정: config/econ_keywords.yaml, config/econ_refs.yaml
"""
from __future__ import annotations

import html
import math
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import yaml
import requests

from market.common import ROOT, load_yaml, request_json, secret
from . import econ_flow as F

def CFG():  # noqa: N802 — 블로그마다 키워드 설정이 다르다 (config/blogs.yaml의 keywords)
    return ROOT / F.BLOG.get("keywords", "config/econ_keywords.yaml")
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
    cfg = F.load(CFG(), {})
    rows: list[tuple[str, str, str]] = []
    for i, it in enumerate(mine, 1):
        src = "어사이드" if it.get("naver_rank") else ("캡처" if str(it.get("why", "")).startswith("📷") else "대표")
        rows.append((f"D{i}", src, it["kw"]))
    for i, it in enumerate(grok_items, 1):
        rows.append((f"G{i}", "Grok", f"{it['kw']} — {it.get('why', '')}"))
    refs = F.load(ROOT / "econ" / "ref" / "rss" / f"{F.today()}.yaml", {}) if F.BLOG["id"] == "econ" else {}
    skip = set(cfg.get("skip_bloggers", []))  # 키워드 조사에서 뺄 블로거 (대표 지시 2026-10-07 "쿠니네는 조사할 필요 없다")
    n = 0
    for b in refs.get("bloggers", []) if cfg.get("blogger_keywords", True) else []:  # 경제는 끔 (2026-10-07)
        if b["id"] in skip:
            continue
        for t in b.get("recent", []):
            n += 1
            rows.append((f"B{n}", "블로거", f"[{b.get('name', b['id'])}] {t}"))
    # 참고 블로거 RSS (econ 말고 블로그별 설정 ref_bloggers, 2026-10-06): 최근 36시간 새 글 제목
    if F.BLOG["id"] != "econ" and cfg.get("ref_bloggers") and cfg.get("blogger_keywords", True):
        from .econ_refs import feed
        now = datetime.now(F.KST)
        since, fresh = now - timedelta(hours=36), now - timedelta(hours=12)
        for bid, name in cfg["ref_bloggers"].items():
            if bid in skip:
                continue
            try:
                for x in feed(bid):
                    if x["at"] >= since and x["title"]:
                        n += 1  # 12시간 안 새 글은 '블로거새글'(점수 더), 요약 앞부분도 같이 — 브랜드·가격을 뽑게 (2026-10-06)
                        rows.append((f"B{n}", "블로거새글" if x["at"] >= fresh else "블로거",
                                     f"[{name}] {x['title']} — {x.get('summary', '')[:160]}"))
            except Exception as e:  # noqa: BLE001
                print(f"블로거 RSS 실패 {bid}: {type(e).__name__}")
    for kind in ("국내뉴스", "해외뉴스"):
        n = 0
        for url in cfg.get("feeds", {}).get(kind, []):
            for t in headlines(url):
                n += 1
                rows.append((f"{'N' if kind == '국내뉴스' else 'Y'}{n}", kind, t))
    for i, it in enumerate(F.price_moves() if F.BLOG["id"] == "econ" else [], 1):
        rows.append((f"P{i}", "시세", f"{it['kw']} — {it['why']}"))
    # 뉴스 검색어 (블로그별 news_queries, 2026-10-06): 네이버 뉴스 검색 API로 최근 24시간 기사 제목 — 패션처럼 RSS가 약한 분야용
    hub0 = _hub() if cfg.get("news_queries") else None
    n = 0
    for qy in cfg.get("news_queries", []) if hub0 else []:
        try:
            for t in _recent_titles(hub0, qy)[:cfg.get("news_per_query", 8)]:
                n += 1
                rows.append((f"S{n}", "뉴스검색", t))
        except Exception as e:  # noqa: BLE001
            print(f"뉴스 검색 실패 {qy}: {str(e)[:80]}")
    # 인기 종목: 국내·미국 대표 종목의 최근 24시간 네이버 기사 수 (뉴스 제목에서 테마로 묶여 사라지지 않게, 2026-10-05 대표 지적)
    hub = _hub()
    if hub:
        hot = []
        for name in cfg.get("watch", []):
            try:
                n, _ = _recent_count(hub, "news_search", name)
            except Exception:  # noqa: BLE001
                continue
            if n >= cfg.get("watch_min_news", 30):
                hot.append((n, name))
        for i, (n, name) in enumerate(sorted(hot, reverse=True)[:10], 1):
            rows.append((f"W{i}", "인기종목", f"{name} — 최근 24시간 네이버 기사 {n}건"))
    return rows


CLUSTER = {"type": "object", "additionalProperties": False, "required": ["keywords"],
           "properties": {"keywords": {"type": "array", "items": {
               "type": "object", "additionalProperties": False,
               "required": ["kw", "core", "area", "why", "person", "product", "rows"],
               "properties": {
                   "kw": {"type": "string", "description": "네이버에서 사람들이 실제로 칠 검색어 (2~4단어, 한국어)"},
                   "core": {"type": "string", "description": "검색량·뉴스량을 잴 핵심 검색어 1~2단어 (예: '원달러 환율', '비트코인', '청년미래적금')"},
                   "area": {"type": "string", "enum": F.load(CFG(), {}).get("areas") or F.AREAS},
                   "why": {"type": "string", "description": "왜 오늘 쓸 만한지 한 줄"},
                   "person": {"type": "string", "description": "관련 인물이 있으면 회사+이름(예: 삼성 이재용), 없으면 빈칸"},
                   "product": {"type": "string", "description": "줄에 브랜드·제품명·가격이 나왔으면 그대로(예: '샤넬 라지 버킷백 1,238만원'), 없으면 빈칸. 지어내지 않음"},
                   "rows": {"type": "array", "items": {"type": "string"}, "description": "이 키워드가 나온 줄 번호 전부 (예: G2, B5, N13)"}}}}}}


def cluster(rows: list[tuple[str, str, str]]) -> list[dict]:
    text = "\n".join(f"{rid} ({src}) {t}" for rid, src, t in rows)
    res = F.claude_json(
        [F.load(CFG(), {}).get("editor") or "너는 경제 블로그 편집장이다. 한국 개인 투자자·직장인이 오늘 네이버에서 찾아볼 경제·돈 주제를 고른다. "
         "작전주·테마주 추천·리딩방·정치 싸움은 뺀다. 줄에 없는 주제를 지어내지 않는다."],
        f"오늘은 {F.today()}(한국 시간). 아래는 여러 출처에서 모은 줄입니다(번호와 출처 표시). 같은 이야기는 한 키워드로 묶고, "
        "키워드마다 그 이야기가 나온 줄 번호를 빠짐없이 적어 주세요. 해외 기사는 한국 독자가 찾을 한국어 검색어로 바꿔 주세요. "
        "D로 시작하는 줄(대표가 넣은 키워드)은 하나도 빠뜨리지 말고 그대로 키워드로 두세요. "
        "W로 시작하는 줄(인기 종목)은 종목마다 따로 키워드로 두고, 그 종목이 나온 다른 줄도 같이 묶으세요"
        "(예: '삼성전자 외국인 매도' 기사는 삼성전자 키워드에). core에는 종목명이나 핵심 검색어만. 키워드는 최대 20개.\n\n" + text,
        CLUSTER, stage="키워드 묶기")
    return res["keywords"]


# ---------------------------------------------------------------- 3) 점수

def _hub():
    from market.naver_hub import ApiHub
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    return ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])


FRESH: dict[str, int] = {}  # 최근 6시간 기사 수 (_recent_count가 news_search 때 채움, 2026-10-06 최신성 가점)


def _recent_count(hub, path: str, kw: str) -> tuple[int, int]:
    """(최근 24시간 글 수(최대 100), 전체 문서 수). 뉴스는 최근 6시간 수도 FRESH[kw]에 남긴다."""
    data = request_json("GET", hub.base + hub.paths[path], headers=hub._headers(),
                        params={"query": kw, "display": 100, "sort": "date"})
    now = datetime.now(F.KST)
    since, fresh = now - timedelta(hours=24), now - timedelta(hours=6)
    n = n6 = 0
    for it in data.get("items", []):
        raw = it.get("pubDate") or it.get("postdate") or ""
        try:
            at = parsedate_to_datetime(raw) if "," in raw else datetime.strptime(raw, "%Y%m%d").replace(tzinfo=F.KST)
        except (TypeError, ValueError):
            continue
        n += at >= (since if "," in raw else since.replace(hour=0, minute=0))
        n6 += "," in raw and at >= fresh
    if path == "news_search":
        FRESH[kw] = n6
    return n, int(data.get("total") or 0)


def _recent_titles(hub, kw: str) -> list[str]:
    """네이버 뉴스 검색(최신순)에서 최근 24시간 기사 제목 (태그 뺌, 같은 제목 하나만)."""
    data = request_json("GET", hub.base + hub.paths["news_search"], headers=hub._headers(),
                        params={"query": kw, "display": 30, "sort": "date"})
    since = datetime.now(F.KST) - timedelta(hours=24)
    out = []
    for it in data.get("items", []):
        try:
            if parsedate_to_datetime(it.get("pubDate") or "") < since:
                continue
        except (TypeError, ValueError):
            continue
        t = html.unescape(re.sub(r"<[^>]+>", "", it.get("title", ""))).strip()
        if t and t not in out:
            out.append(t)
    return out


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


def _youtube_recent(cores: list[str], days: int = 7) -> dict[str, int]:
    """키워드마다 최근 days일 유튜브 공개 영상 수(대략, search.list totalResults) → '지금 콘텐츠가 쏟아지나' 화제성 보조.
    (대표 결정 2026-10-10 '유튜브 연동'). 키 없거나 쿼터 넘으면 조용히 건너뜀. search.list 1회 100단위라 상위 후보에만 묻는다."""
    k = secret("YOUTUBE_API_KEY")
    if not k or not cores:
        return {}
    since = (datetime.now(F.KST) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: dict[str, int] = {}
    for c in cores:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=20, params={
                "key": k, "part": "snippet", "q": c, "type": "video", "publishedAfter": since,
                "maxResults": 1, "regionCode": "KR", "relevanceLanguage": "ko"})
            if r.status_code == 403:  # 쿼터 소진 등 → 더 묻지 않고 멈춤
                print("유튜브 쿼터/권한으로 건너뜀")
                break
            r.raise_for_status()
            out[c] = int((r.json().get("pageInfo") or {}).get("totalResults", 0))
        except Exception as e:  # noqa: BLE001
            print(f"유튜브 조회 실패 {c}: {str(e)[:60]}")
    return out


def naver_part(rank: int | None) -> float:
    """어사이드 순위 → 네이버 인기 비율: 1~3위 100%, 4~6위 75%, 7~10위 50% (대표 결정 2026-10-07)."""
    if not rank:
        return 0.0
    return 1.0 if rank <= 3 else 0.75 if rank <= 6 else 0.5 if rank <= 10 else 0.0


def _recent_cores(days: int, topn: int) -> dict[str, int]:
    """최근 days일(오늘 제외) 상위 topn개에 나온 core → 나온 날 수 (매일 반복되는 주제 감점용, 대표 지시 2026-10-10)."""
    from datetime import datetime, timedelta
    from . import econ_flow as F
    today = F.today()
    since = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    out: dict[str, int] = {}
    for f in sorted(F.FLOW.glob("*/keywords.yaml")):
        day = f.parent.name
        if not (since <= day < today):
            continue
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        for it in sorted(data.get("items", []), key=lambda x: -x.get("score", 0))[:topn]:
            c = (it.get("core") or it.get("kw") or "").strip()
            if c:
                out[c] = out.get(c, 0) + 1
    return out


def score(items: list[dict], src_rows: dict[str, str] | None) -> list[dict]:
    """items: {kw, core, rows[...], naver_rank?} → score·parts·sources를 채워 점수순으로.
    100점 = 블로그 설정 weights (2026-10-07 대표 결정: 네이버 인기(어사이드) 35 > 최신 25 > 출처 겹침 20 > 뉴스량 10 = 검색량 10).
    "네이버에서 가장 최근·가장 핫한 키워드인데, X·블로거·뉴스에서도 나오는 것"이 위로 오게.
    src_rows가 None이면 줄 번호 대신 이미 센 it['sources']로 다시 매긴다 (어사이드·대표 키워드를 넣을 때 그날 목록 전체를 다시 채점).
    어사이드가 없는 날은 네이버 인기를 뺀 나머지를 100점으로 환산한다(점수 미달로 숨겨지지 않게)."""
    cfg = F.load(CFG(), {})
    pts, caps = cfg.get("source_points", {}), cfg.get("caps", {})
    stale_pen, stale_cap = cfg.get("stale_penalty", 0), cfg.get("stale_cap", 25)
    _recent = _recent_cores(cfg.get("stale_days", 3), cfg.get("stale_topn", 12)) if stale_pen else {}
    hub = _hub()
    q = {it["kw"]: (it.get("core") or it["kw"]) for it in items}  # 긴 키워드는 검색량이 0에 가까워 핵심어로 잰다
    cores = list(dict.fromkeys(q.values()))
    vols = _volumes(cores)
    rises: dict[str, dict] = {}  # 홈판 재정의 2026-10-10: 검색어트렌드 상승률(화제성)을 메인 점수에도 (무료 API)
    if hub and cfg.get("weights", {}).get("급상승"):
        try:
            rises = hub.rise(cores)
        except Exception as e:  # noqa: BLE001
            print(f"급상승 점수 실패: {str(e)[:100]}")
    raw = {}
    for it in items:
        cnt: dict[str, int] = {}
        if src_rows is None:
            cnt = dict(it.get("sources") or {})
        for rid in it.get("rows", []) if src_rows is not None else []:
            s = src_rows.get(rid)
            if s:
                cnt[s] = cnt.get(s, 0) + 1
        src_pts = 0.0
        for s, c in cnt.items():
            p = pts.get(s, 0) * (c if s in ("블로거", "블로거새글", "국내뉴스", "해외뉴스", "뉴스검색") else 1)
            src_pts += min(p, caps.get(s, p))
        raw[it["kw"]] = src_pts
        it["sources"] = cnt
    top = max(raw.values() or [1]) or 1
    w = {"출처": 40, "뉴스": 25, "검색": 35, "최신": 0, "네이버": 0, "급상승": 0, **cfg.get("weights", {})}  # 블로그마다 나눔
    aside = any(it.get("naver_rank") for it in items)
    scale = 100 / (100 - w["네이버"]) if (w["네이버"] and not aside and w["네이버"] < 100) else 1
    for it in items:
        news = blog = None
        if hub:
            try:
                news, _ = _recent_count(hub, "news_search", q[it["kw"]])
                blog, _ = _recent_count(hub, "blog_search", it["kw"])
            except Exception as e:  # noqa: BLE001
                print(f"네이버 검색 실패 {it['kw']}: {str(e)[:80]}")
        vol = vols.get(q[it["kw"]])
        # 만점 기준은 블로그마다 (패션은 검색량·기사가 경제보다 훨씬 적어 경제 기준이면 다 낮게 나옴, 2026-10-06)
        nf, vf = cfg.get("news_full", 100), cfg.get("vol_full", 1_000_000)
        n6 = FRESH.get(q[it["kw"]])
        ff = cfg.get("fresh_full", 10)  # 최신: 최근 6시간 기사 이 수면 만점 (대표 지시 2026-10-06 "따끈할수록 가점")
        rise = (rises.get(q[it["kw"]]) or {}).get("rise", 1.0)  # 1.0 평소, 2.0 평소의 2배
        parts = {"네이버": round(w["네이버"] * naver_part(it.get("naver_rank"))),
                 "급상승": round(w["급상승"] * min(1.0, max(0.0, rise - 1.0))) if w["급상승"] else 0,  # 2배↑면 만점 (화제성)
                 "최신": round(w["최신"] * min(n6, ff) / ff) if (n6 is not None and w["최신"]) else 0,
                 "출처": round(w["출처"] * raw[it["kw"]] / top),
                 "뉴스": round(w["뉴스"] * min(news, nf) / nf) if news is not None else 0,
                 "검색": round(min(w["검색"], max(0.0, (math.log10(vol) - 2) / (math.log10(vf) - 2) * w["검색"]))) if vol else 0}
        pb = cfg.get("product_bonus", 0)  # 패션: 브랜드·가격이 이미 나온 주제 가점 (대표 결정 2026-10-08 '주제 고르기 강화')
        if pb and (it.get("product") or "").strip():
            parts["제품"] = pb
        rep = _recent.get((it.get("core") or it["kw"]).strip(), 0)  # 최근 며칠 반복된 주제 감점 (대표 지시 2026-10-10 "맨날 똑같다")
        if rep and stale_pen:
            parts["반복"] = -min(rep * stale_pen, stale_cap)
        it.update(score=max(0, min(100, round(sum(parts.values()) * scale))), parts=parts,
                  stats={"뉴스24h": news, "뉴스6h": n6, "블로그24h": blog, "월검색": int(vol) if vol else None, "상승": rise})
    items.sort(key=lambda x: -x["score"])
    # 유튜브 '지금 콘텐츠가 쏟아지나' 화제성 보조 (대표 결정 2026-10-10): 상위 후보에만 묻어 쿼터 아낌
    yb = cfg.get("youtube_bonus", 0)
    if yb:
        yt_top = cfg.get("youtube_top", 10)
        yf = cfg.get("youtube_full", 500)  # 최근 7일 이만큼 영상이면 만점 보너스
        top_cores = list(dict.fromkeys(q[it["kw"]] for it in items[:yt_top]))
        yrec = _youtube_recent(top_cores)
        for it in items[:yt_top]:
            v = yrec.get(q[it["kw"]])
            if v is None:
                continue
            bonus = round(yb * min(1.0, math.log10(v + 1) / math.log10(yf + 1)))
            it["parts"]["유튜브"] = bonus
            it["stats"]["유튜브7일"] = v
            it["score"] = max(0, min(100, it["score"] + bonus))
        items.sort(key=lambda x: -x["score"])
    return items


def run(grok_items: list[dict], mine: list[dict]) -> list[dict]:
    rows = gather(grok_items, mine)
    print(f"모은 줄 {len(rows)}개: " + ", ".join(f"{s} {sum(1 for r in rows if r[1] == s)}"
                                            for s in dict.fromkeys(r[1] for r in rows)))
    if not rows:
        return []
    items = cluster(rows)
    src_rows = {rid: src for rid, src, _ in rows}
    who = {rid: t[1:t.index("]")] for rid, _, t in rows if rid.startswith("B") and "]" in t}  # 블로거 이름
    for it in items:
        it["rows"] = [r for r in it["rows"] if r in src_rows]
        it["src"] = ", ".join(sorted({src_rows[r] for r in it["rows"]})) or "?"
        it["bloggers"] = sorted({who[r] for r in it["rows"] if r in who})
    # 대표가 넣은 키워드가 묶기에서 빠졌으면 그대로 살린다
    have = {r for it in items for r in it["rows"]}
    for rid, src, t in rows:
        if rid.startswith("D") and rid not in have:
            items.append({"kw": t, "area": "", "why": "대표가 넣음", "person": "", "rows": [rid], "src": src})
    # 어사이드 순위는 다시 모아도 이어지게 (D 줄 번호 = mine 순서)
    rank = {f"D{i}": it["naver_rank"] for i, it in enumerate(mine, 1) if it.get("naver_rank")}
    for it in items:
        r = [rank[x] for x in it["rows"] if x in rank]
        if r:
            it["naver_rank"] = min(r)
    return score(items, src_rows)
