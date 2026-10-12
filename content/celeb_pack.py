"""패션 조사 세트 — 조사만 API(Grok)로, 글은 구독 클로드 프로젝트로 (대표 결정 2026-10-12).

키워드 `인물 / 시점 / 제품명` → Grok이 웹·X에서 조사해 JSON으로 돌려줌 → **확인 안 된 칸은 코드가 지움**
→ 클로드 패션 프로젝트에 한 번에 붙여넣는 글('조사 메모 + 출발')로 조립.
저장: blogs/fashion/research/<날짜>/<주제>.txt (붙여넣을 글) · .json (조사 값). 도우미가 읽어 '복사' 버튼으로 보여 준다.
조사 항목은 prompts/project/클로드-패션-글.md(조사 순서·착용 확인·가격 규칙)와 원문 §8 자료 조사 규칙을 따른다.
"""
from __future__ import annotations

import json
import re
import sys

import requests

from . import econ_flow as F

NONE = {"", "확인 안 됨", "확인안됨", "미확인", "정보 없음", "정보없음", "없음", "모름", "불명", "해당 없음", "n/a", "na", "null", "none",
        "unknown", "-", "?", "추정"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; shorts-engine link check)"}

ASK = """오늘은 {today}(한국 시간)입니다. 패션 블로그 글을 쓰기 위한 조사입니다. 키워드: {kw}
(형식: 인물 / 시점 / 제품명. 제품명이 없으면 그 인물이 그 시점에 입은 것을 찾으세요.)

웹과 X에서 어제·오늘 나온 기사, 공식 SNS, 브랜드·쇼핑몰 공식 상품 페이지를 확인하고 교차검증하세요.
순서: ① 최신 뉴스·기사 ② 그 인물 착용을 다룬 글 ③ 브랜드·쇼핑몰 공식 상품 페이지. 네이버·구글 검색 결과 화면을 긁지 말고, 특정 기사·상품 페이지를 열어 읽으세요.
글 문장과 사진은 옮기지 말고 사실(누가·언제·무엇·브랜드·가격)만 적으세요.

**JSON 한 덩어리만** 출력하세요(설명·코드블록 표시 금지). 확인하지 못한 칸은 반드시 빈 문자열 ""(목록은 [])로 두세요. 추측·지어내기 절대 금지.
{{
 "person": "인물 이름",
 "age": "공식으로 확인된 만 나이 또는 출생연도 (확인 안 되면 \\"\\")",
 "what_happened": "무슨 일인지 한두 문장 (방송·행사·공항·SNS·작품 / 날짜 / 장소)",
 "worn_confirmed": true 또는 false (그 인물이 그 제품을 실제 착용·사용한 것이 기사·공식 SNS로 확인되면 true),
 "worn_basis": "착용 근거 (예: ○○일보 기사, 공식 인스타)",
 "products": [ {{
   "brand_ko": "", "brand_en": "", "name_en": "제품명 영문 원어(모델·라인명까지)", "name_ko": "",
   "model_no": "품번", "color_material": "색상·소재", "features": "다른 제품과 구별되는 디테일",
   "list_price_krw": "정가(원, 공식 사이트)", "sale_price_krw": "할인가(원)", "retail_price_krw": "판매처 가격(원)과 판매처",
   "overseas_price": "해외가(현지 통화)", "price_asof": "가격 확인 날짜", "on_sale": "출시·판매 여부",
   "price_url": "가격을 확인한 페이지 주소"
 }} ],
 "styling": "스타일링 포인트(색·소재·실루엣)",
 "related_people": ["같은 그룹·작품·행사에서 실제 관련 있는 사람만"],
 "reactions": [ {{"text": "사람들 반응 요약", "rumor": true 또는 false}} ],
 "photo_links": [ {{"kind": "공식제품 | 기사 | 공식SNS", "url": "직접 열어 확인한 주소만", "direct": true(누르면 사진이 바로 뜨는 이미지 주소) 또는 false(기사·상품 페이지), "source": "매체 또는 브랜드명"}} ],
 "sources": [ {{"title": "", "url": ""}} ]
}}
제품은 확인된 것만 넣으세요(없으면 []). 기억으로 쓴 주소·가짜 링크는 금지입니다."""


def _ok(v) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, str):
        return v.strip().lower() not in NONE
    if isinstance(v, (list, dict)):
        return bool(v)
    return True


def clean(o):
    """확인 안 된 칸(빈 값·'확인 안 됨' 등)을 재귀로 지운다. worn_confirmed(참/거짓)는 따로 다루니 보존."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k in ("worn_confirmed", "rumor", "direct"):
                out[k] = bool(v)
                continue
            v = clean(v)
            if _ok(v):
                out[k] = v
        return out
    if isinstance(o, list):
        return [x for x in (clean(i) for i in o) if _ok(x)]
    if isinstance(o, str):
        return o.strip()
    return o


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def alive(url: str, direct: bool) -> bool:
    """직접 열어 보고 살아 있는 링크만 (지어낸 주소 거르기). 이미지 주소면 이미지인지도 본다."""
    try:
        r = requests.get(url, headers=UA, timeout=10, stream=True, allow_redirects=True)
        ok = r.status_code < 400
        if ok and direct:
            ok = r.headers.get("content-type", "").lower().startswith("image/")
        r.close()
        return ok
    except Exception:
        return False


def check_links(d: dict) -> dict:
    keep = []
    for p in d.get("photo_links", []):
        u = str(p.get("url", ""))
        if u.startswith("http") and alive(u, bool(p.get("direct"))):
            keep.append(p)
    d["photo_links"] = keep
    if not keep:
        d.pop("photo_links", None)
    return d


PRICE_ROWS = (("list_price_krw", "정가"), ("sale_price_krw", "할인가"), ("retail_price_krw", "판매처가"), ("overseas_price", "해외가"))


def render(kw: str, d: dict, today: str) -> str:
    """클로드 패션 프로젝트에 붙여넣을 글. 값이 없는 줄은 만들지 않는다."""
    L = [kw.strip(), "",
         "[조사 메모 — 아래에 적힌 사실만 쓴다. 여기에 없는 제품명·브랜드·가격·착용 상황은 지어내지 않는다. 없는 항목은 글에서도 뺀다.]",
         f"조사일: {today} (한국 시간)"]
    if d.get("person"):
        L.append(f"인물: {d['person']}")
    if d.get("age"):
        L.append(f"확인된 나이·출생: {d['age']}")
    if d.get("what_happened"):
        L.append(f"무슨 일: {d['what_happened']}")
    if d.get("worn_confirmed"):
        L.append("착용 확인: 됨" + (f" (근거: {d['worn_basis']})" if d.get("worn_basis") else ""))
    else:
        L.append("착용 확인: 안 됨 — 입은 것처럼 쓰지 말고, 쓰려면 첫 문단에 '착용이 확인되지 않은 스타일링 제안'이라고 밝힌다")
    for i, p in enumerate(d.get("products", []), 1):
        L += ["", f"[제품 {i}]"]
        brand = " ".join(x for x in (p.get("brand_ko"), f"({p['brand_en']})" if p.get("brand_en") else "") if x)
        if brand:
            L.append(f"브랜드: {brand}")
        name = " / ".join(x for x in (p.get("name_en"), p.get("name_ko")) if x)
        if name:
            L.append(f"제품명: {name}")
        for key, label in (("model_no", "품번"), ("color_material", "색상·소재"), ("features", "디테일"), ("on_sale", "출시·판매")):
            if p.get(key):
                L.append(f"{label}: {p[key]}")
        for key, label in PRICE_ROWS:
            if p.get(key):
                L.append(f"{label}: {p[key]}")
        if any(p.get(k) for k, _ in PRICE_ROWS) and p.get("price_asof"):
            L.append(f"가격 기준: {p['price_asof']}")
        if p.get("price_url"):
            L.append(f"가격 출처: {p['price_url']}")
    if d.get("styling"):
        L += ["", f"스타일링 포인트: {d['styling']}"]
    if d.get("related_people"):
        L.append("관련 인물: " + ", ".join(d["related_people"]))
    if d.get("reactions"):
        L += ["", "반응:"] + [f"- {r['text']}" + (" (소문·미확인)" if r.get("rumor") else "") for r in d["reactions"] if r.get("text")]
    if d.get("photo_links"):
        L += ["", "사진 링크 (직접 열어 확인한 것만):"]
        for p in d["photo_links"]:
            L.append(f"- [{'이미지 주소' if p.get('direct') else '페이지'}] {p.get('kind', '')} · {p.get('source', '')} · {p['url']}")
    if d.get("sources"):
        L += ["", "출처:"] + [f"- {s.get('title', '')} {s.get('url', '')}".rstrip() for s in d["sources"] if s.get("url")]
    L += ["", "출발"]
    return "\n".join(L)


def make(kw: str) -> bool:
    """키워드 한 줄 → 조사 → 저장. 조사 실패(그록 응답 없음·읽지 못함)면 False."""
    today = F.today()
    raw = F.grok(ASK.format(today=today, kw=kw), days=2, web=True, turns=2)
    d = parse(raw)
    if not d:
        print(f"조사 실패: {kw} (Grok 응답이 없거나 읽을 수 없음)")
        return False
    d = check_links(clean(d))
    out = F.BLOG["base"] / "research" / today
    out.mkdir(parents=True, exist_ok=True)
    stem = F.topic_slug(kw)[len(today) + 1:]
    (out / f"{stem}.json").write_text(json.dumps({"keyword": kw, "date": today, **d}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}.txt").write_text(render(kw, d, today), encoding="utf-8")
    print(f"조사 세트 저장: {out / (stem + '.txt')}")
    return True


def run(text: str) -> None:
    """이슈 본문 → 줄마다 키워드(최대 3). 하나라도 되면 성공."""
    kws = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("http")][:3]
    if not kws:
        raise SystemExit("키워드가 비어 있어요. 한 줄에 '인물 / 시점 / 제품명'으로 적어 주세요.")
    ok = 0
    for kw in kws:
        F.guard()
        try:
            ok += make(kw)
        except Exception as ex:  # 하나가 실패해도 나머지는 계속
            print(f"조사 실패: {kw}: {ex}")
    if not ok:
        raise SystemExit("조사 세트를 하나도 못 만들었어요. (그록 키·한도를 확인해 주세요)")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "")
