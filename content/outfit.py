"""착장 도우미 (대표 결정 2026-10-10, reports/2026-10-10-착장-도우미-설계.md).

rank  : 오늘 뜨는 연예인 10명 — 후보(Grok X 화제 + 오늘 패션 키워드의 인물) → 네이버 월 검색량 + 최근 3일 검색 상승률로 순위.
        최근 3일에 이미 상위였던 인물은 감점. → blogs/fashion/outfit/<날짜>/celebs.yaml
write : 대표가 고른 연예인 + 인스타 게시물 주소(대표가 직접 복사) + 상품 링크(렌즈 결과)
        → 상품 페이지 읽기(link_facts) → 조사 메모 → 제목(패션 프롬프트) → ★추천 제목으로 글.
        인스타 게시물은 읽지 않고(자동 수집 안 함) 주소만 글 폴더에 남겨 도우미·임시저장 때 사진 자리 안내에 쓴다.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import econ_flow as F

OUT = F.FLOW.parent / "outfit"
N_SHOW = 10
STALE_DAYS, STALE_PEN = 3, 15
NAME = re.compile(r"^[가-힣A-Za-z]{2,6}$")  # 연예인 이름 (그룹명·영문 이름 포함, 너무 긴 건 빼기)
NOT_NAME = re.compile(r"(코어|룩|패션|코디|스타일|트렌드|컬러|아이템|백|가방|니트|코트|원피스|신발|시즌)$")  # 사람이 아닌 패션 낱말 (10-10 '현백코어')


def _candidates() -> dict[str, str]:
    """{이름: 왜 화제인지}. Grok(X 화제) + 오늘 패션 키워드(어사이드·뉴스)의 인물."""
    out: dict[str, str] = {}
    g = F.grok(f"오늘은 {F.today()}(한국 시간)입니다. 지금 X(트위터)와 연예 뉴스에서 화제인 한국 연예인 15명을 골라 주세요. "
               "공항 패션·시상식·화보·드라마 제작발표회·SNS 사진처럼 '옷차림'이 주목받을 만한 사람 위주로. "
               'JSON 배열만 답하세요: [{"name": "이름(본명이나 활동명 하나)", "why": "왜 화제인지 한 줄"}]', days=2)
    for it in F.parse_json(g) or []:
        if isinstance(it, dict) and NAME.match((it.get("name") or "").strip()) and not NOT_NAME.search(it["name"].strip()):
            out.setdefault(it["name"].strip(), (it.get("why") or "").strip())
    kw = F.load(F.FLOW / F.today() / "keywords.yaml", {}) or {}
    for it in kw.get("items", []):
        name = (it.get("person") or it["kw"].split()[0]).strip()
        name = re.split(r"[(\s·,]", name)[0]
        if NAME.match(name) and not NOT_NAME.search(name):
            out.setdefault(name, it["kw"])
    return out


def _recent_top(days: int) -> dict[str, int]:
    """최근 days일(오늘 제외) 상위 5명에 들었던 인물 → 날 수 (같은 사람만 매일 올라오지 않게)."""
    today = F.today()
    since = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    out: dict[str, int] = {}
    for f in sorted(OUT.glob("*/celebs.yaml")) if OUT.exists() else []:
        if since <= f.parent.name < today:
            for c in (F.load(f, {}) or {}).get("items", [])[:5]:
                out[c["name"]] = out.get(c["name"], 0) + 1
    return out


def rank() -> Path:
    from .econ_score import _hub, _volumes
    cands = _candidates()
    names = list(cands)[:30]
    vols = _volumes(names) if names else {}
    rises: dict[str, dict] = {}
    hub = _hub()
    if hub and names:
        try:
            rises = hub.rise(names)
        except Exception as e:  # noqa: BLE001  (상승률이 없어도 검색량으로 순위)
            print(f"검색어 트렌드 실패: {str(e)[:120]}")
    rep = _recent_top(STALE_DAYS)
    items = []
    for n in names:
        v = vols.get(n) or 0
        r = (rises.get(n) or {}).get("rise", 1.0)
        vol_pt = round(min(50, max(0.0, (math.log10(v) - 3) / 3 * 50))) if v > 0 else 0  # 1천 → 0점, 100만 → 50점
        rise_pt = round(min(50, max(0.0, (r - 1) * 50)))  # 평소의 2배면 50점
        stale = min(rep.get(n, 0) * STALE_PEN, 30)
        items.append({"name": n, "why": cands[n], "score": max(0, vol_pt + rise_pt - stale),
                      "parts": {"검색량": vol_pt, "상승": rise_pt, **({"반복": -stale} if stale else {})},
                      "volume": int(v) if v else None, "rise": r})
    items.sort(key=lambda x: -x["score"])
    out = OUT / F.today() / "celebs.yaml"
    F.save(out, {"date": F.today(), "updated": datetime.now(F.KST).strftime("%H:%M"), "items": items[:N_SHOW]})
    print(f"오늘 뜨는 연예인 {len(items[:N_SHOW])}명 → {out}")
    return out


def _kw(person: str, facts: str) -> str:
    """글 키워드 = 인물 + 첫 상품의 브랜드·아이템 (예: '카리나 프라다 숄더백'). 상품 정보가 없으면 '인물 착장'."""
    m = re.search(r"\[제품\]\s*([^|\n]+)\|\s*([^|\n]+)", facts)
    if not m:
        return f"{person} 착장"
    brand = re.split(r"[(/（]", m.group(1))[0].strip()
    # 아이템은 한글 낱말로 (영문 제품명이면 '제품명 :' 줄에서 찾기, 없으면 '착장')
    ko = re.findall(r"[가-힣]{2,}", re.sub(r"\(.*?\)", "", m.group(2)))
    if not ko:
        line = re.search(r"제품명\s*:\s*([^\n]+)", facts)
        ko = re.findall(r"[가-힣]{2,}", line.group(1)) if line else []
    item = ko[-1] if ko else "착장"
    return re.sub(r"\s+", " ", f"{person} {brand} {item}").strip()[:30]


def write(text: str) -> Path:
    """'[착장글]' 이슈 본문: 첫 줄 = 연예인 이름, 다음 줄들 = 인스타 게시물 주소·상품 링크."""
    from .celeb import link_facts, produce, research, titles
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    person = next((l for l in lines if not l.startswith("http")), "")[:20]
    urls = [l for l in lines if l.startswith("http")]
    insta = [u for u in urls if "instagram.com" in u]
    shops = [u for u in urls if "instagram.com" not in u]
    if not person:
        raise SystemExit("첫 줄에 연예인 이름이 필요해요.")
    facts = link_facts(shops) if shops else ""
    kw = _kw(person, facts)
    memo = research(kw) or F.claude_research(kw)
    if facts:
        memo = "[대표가 준 상품 링크에서 확인한 제품 정보 — 가장 믿을 만한 자료, 본문 제품 정보는 이걸 기준으로]\n" + facts + "\n\n" + memo
    d = titles(kw, memo)
    F.save(d / "outfit.yaml", {"person": person, "insta": insta, "shops": shops, "at": datetime.now(F.KST).strftime("%H:%M")})
    T = F.load(d / "titles.yaml", {})
    n = next((i for i, t in enumerate(T.get("items", []), 1) if t.get("rank") == 1), 1)
    produce(d.name, n)
    return d
