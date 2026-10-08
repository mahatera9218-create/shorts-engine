"""패션 가격 찾기 — 네이버 쇼핑 검색 API(API HUB, 공식 통로)로 제품 판매가와 비슷한 상품 가격대 (대표 결정 2026-10-08 "패션 기능 강화").

조사 메모(Grok)가 "[제품] 브랜드 | 제품명 | 가격" 줄로 착용 제품을 적으면, 제품마다
① '브랜드 제품명'으로 네이버 쇼핑 판매가(최저~중간~최고, 판매처) ② '제품명(브랜드 빼고)'으로 비슷한 상품 가격대를 찾아
조사 메모 끝에 붙인다. 쇼핑 판매가는 공식가가 아니므로 글에는 "네이버 쇼핑 기준 ○○원대(기준일)"로만 쓴다.
"""
from __future__ import annotations

import html
import re
import statistics

from market.common import load_yaml, request_json, secret

from . import econ_flow as F

TAG = re.compile(r"<[^>]+>")
LINE = re.compile(r"\[제품\]\s*([^\n]+)")  # 줄 앞 번호·기호와 상관없이
ALIAS = {"샤넬": ["chanel"], "루이비통": ["louis vuitton", "lv"], "디올": ["dior"], "구찌": ["gucci"], "프라다": ["prada"],
         "미우미우": ["miu miu"], "에르메스": ["hermes"], "보테가베네타": ["bottega"], "셀린느": ["celine"], "버버리": ["burberry"],
         "생로랑": ["saint laurent", "ysl"], "발렌시아가": ["balenciaga"], "로에베": ["loewe"], "펜디": ["fendi"], "폴로": ["polo", "ralph"]}
JUNK = re.compile(r"중고|리퍼|대여|렌탈|케이스|커버|스트랩만|더스트백|정품 ?인증|가품")


def _hub() -> tuple[str, dict] | None:
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    ep = load_yaml("global.yaml")["endpoints"]["naver_hub"]
    return ep["base"].rstrip("/") + ep.get("shop_search", "/search/v1/shop"), {
        "X-NCP-APIGW-API-KEY-ID": secret("NCP_APIGW_API_KEY_ID"), "X-NCP-APIGW-API-KEY": secret("NCP_APIGW_API_KEY")}


def search(query: str, display: int = 40) -> list[dict]:
    """[{title, price, mall, brand, cat}] — 중고·액세서리 부속은 뺀다. 키가 없거나 실패하면 []."""
    hub = _hub()
    if not hub or not query.strip():
        return []
    url, headers = hub
    try:
        data = request_json("GET", url, headers=headers, params={"query": query, "display": display, "sort": "sim"})
    except Exception as e:  # 가격은 없어도 글은 쓴다
        print(f"  쇼핑 검색 실패 ({query}): {str(e)[:200]}")
        return []
    out = []
    for it in data.get("items", []):
        t = html.unescape(TAG.sub("", it.get("title", ""))).strip()
        try:
            p = int(it.get("lprice") or 0)
        except ValueError:
            p = 0
        if p <= 0 or JUNK.search(t):
            continue
        out.append({"title": t, "price": p, "mall": it.get("mallName", ""), "brand": it.get("brand", ""),
                    "cat": " > ".join(x for x in (it.get(f"category{i}") for i in range(1, 4)) if x)})
    return out


def won(n: int) -> str:
    return f"{n // 10000:,}만원" if n >= 100000 and n % 10000 == 0 else f"{n:,}원"


def summary(items: list[dict], must: list[str], exclude: list[str] | None = None) -> str:
    """must 단어가 제목에 다 들어가고 exclude 단어는 없는 것만 모아 가격대 한 줄. 없으면 빈칸."""
    hit = [x for x in items if all(w.lower() in (x["title"] + " " + x["brand"]).lower() for w in must)
           and not any(w.lower() in (x["title"] + x["brand"]).lower() for w in exclude or [])]
    if not hit:
        return ""
    ps = sorted(x["price"] for x in hit)
    malls = list(dict.fromkeys(x["mall"] for x in hit if x["mall"]))[:3]
    return (f"{len(hit)}개 판매처 · 최저 {won(ps[0])} · 중간 {won(int(statistics.median(ps)))} · 최고 {won(ps[-1])}"
            + (f" · 판매처 예: {', '.join(malls)}" if malls else ""))


def products(memo: str) -> list[tuple[str, str]]:
    """조사 메모의 '[제품] 브랜드 | 제품명 | 가격' 줄 → [(브랜드, 제품명)] (브랜드·제품명이 '확인 안 됨'이면 뺌)."""
    out = []
    for m in LINE.finditer(memo):  # noqa
        parts = [p.strip() for p in m.group(1).split("|")]
        if len(parts) >= 2 and parts[0] and parts[1] and "확인" not in parts[0] + parts[1]:
            out.append((parts[0], parts[1]))
    return list(dict.fromkeys(out))[:4]


def note(memo: str) -> str:
    """조사 메모 끝에 붙일 '네이버 쇼핑 판매가' 칸. 찾은 게 없으면 빈칸."""
    lines = []
    for brand, name in products(memo):
        exact = summary(search(f"{brand} {name}"), [brand.split()[0]])
        generic_q = name.replace(brand, "").strip() or name
        similar = summary(search(generic_q), generic_q.split()[-1:], [brand.split()[0], *ALIAS.get(brand.split()[0], [])])  # 그 브랜드 상품은 빼고
        if exact:
            lines.append(f"- {brand} {name}: 네이버 쇼핑 판매가 {exact}")
        if similar:
            lines.append(f"- 비슷한 '{generic_q}' 상품 가격대: {similar}")
    if not lines:
        return ""
    return (f"\n\n[네이버 쇼핑 판매가 ({F.today()} 기준, 공식가 아님 — 글에는 '네이버 쇼핑 기준 ○○원대'로)]\n" + "\n".join(lines))


def main() -> None:
    """점검: 실제 쇼핑 검색이 되는지 (주소·권한). 결과를 reports/에 남긴다. AI 비용 없음."""
    from market.common import ROOT
    qs = [("샤넬", "라지 버킷백"), ("미우미우", "스웨이드 재킷"), ("버버리", "트렌치코트")]
    hub = _hub()
    md = [f"# 네이버 쇼핑 검색 점검 ({F.today()})", "", f"- 주소: {hub[0] if hub else '키 없음'}", ""]
    for b, n in qs:
        items = search(f"{b} {n}")
        md += [f"## {b} {n}", f"- 받은 상품 {len(items)}개",
               f"- 정확: {summary(items, [b]) or '없음'}",
               f"- 비슷한 '{n}': {summary(search(n), n.split()[-1:], [b, *ALIAS.get(b, [])]) or '없음'}",
               *[f"  - {x['title'][:50]} · {x['price']:,}원 · {x['mall']}" for x in items[:3]], ""]
    out = ROOT / "reports" / f"{F.today()}-쇼핑검색-점검.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
