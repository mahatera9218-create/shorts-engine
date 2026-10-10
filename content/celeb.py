"""연예인 패션 블로그(캐시미어 다이어리) (대표 결정 2026-10-05, 연예·패션은 같은 날 하나로 합침).

프롬프트: prompts/ent-fashion-blog.md(강사 원문, 그대로) + prompts/addon-common-celeb.md(우리 자동화용) + 블로그별 페르소나
(prompts/addon-fashion.md, config/blogs.yaml의 addon).
역할: 조사 = Grok(웹 + X, 어제·오늘) · 글 = Claude · 사진 = 실제 사진(위키미디어 공용, 자유 이용 허락된 것) → 제품 AI 사진(GPT Image)
→ Pexels. SNS·방송 장면·언론사 사진은 자동으로 가져오지 않는다(저작권·초상권).

titles <키워드>          : 그룹 1(주인공 숨김)·2(이름 노출)·3(관련 인물) 각 5개 + 최종 추천 1개
produce <주제폴더> <번호> : 1,500자 이상 본문 · 숫자 없는 요약 · 해시태그 18~19개 · 구간마다 사진 1장 + 썸네일
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import requests

from market.common import ROOT
from . import econ_flow as F
from .title_refs import VERSION_SCHEMA, versions_ask
from .kunine import ai_photo, pexels, photo_prompt

UA = {"User-Agent": "shorts-engine/1.0 (blog image lookup; contact via GitHub)"}
FREE = ("cc0", "public domain", "cc by", "cc-by", "pd")  # 위키미디어 자유 이용 라이선스만
META = ("사용자가 제공", "첨부한", "첨부 자료", "캡처", "검색해보니", "확인해보니", "이번 글에서는", "이번 포스팅에서는",
        "제가 확인한 바로는", "자료를 기준으로", "제공된 정보", "검색 결과", "출처를 확인", "이미지 삽입", "사진 삽입", "사진 자리")
NO_AUTO_PHOTOS = True  # 대표 결정 2026-10-08: 사진은 대표가 프롬프트로 직접 (자동 무료·AI·위키미디어 사진 안 넣음)
HIGH_UPTO = 4  # 글 맨 앞부터 이 번호까지 고화질 (1 = 썸네일)
MAX_IMAGES = 8  # 썸네일 + 소제목 구간마다 1장(마무리 제외 7) — 대표 결정 2026-10-08 "사진 갯수 줄이자" (전에는 16)


def prompt() -> list[str]:
    b = F.BLOG
    files = [b["prompt"], "prompts/addon-common-celeb.md", b["addon"]]
    # 글 방식은 강사 원문 + 덧붙임만 (대표 지시 2026-10-06: 고수에게서는 제목·키워드만 배움)
    return [re.sub(r"<!--.*?-->", "", (ROOT / f).read_text(encoding="utf-8"), flags=re.S).strip() for f in files]


def research(kw: str) -> str:
    """Grok 조사 메모 + 네이버 쇼핑 판매가(공식 쇼핑 검색 API, 대표 결정 2026-10-08 '가격 찾기 강화')."""
    memo = _grok_research(kw)
    if memo:
        from .shop_price import note
        memo += note(memo)
    return memo


def link_facts(urls: list[str]) -> str:
    """대표가 찾은 상품 링크를 Claude 웹 가져오기(web_fetch)로 열고, 빠진 항목은 웹 검색(web_search, 공식 도구)으로 채움
    (대표 지시 2026-10-08 '링크로 글': 정가·할인가·판매처별·해외가 원화 환산·품번까지 다 채우기, 못 찾은 항목은 줄째 빼기)."""
    if not urls:
        return ""
    import anthropic
    c = anthropic.Anthropic()
    # 비용 줄이기 2차 (대표 지적 2026-10-10 "왜 이렇게 비싸"): 실측 1편 0.46~0.92달러였던 원인 = 웹 검색 여러 번 + 큰 페이지를 매 턴 다시 읽음.
    # → 정보 뽑기는 싼 Haiku로, 대표 링크만 열고(추가 페이지 없음), 페이지당 읽는 양 8,000토큰(3,000이면 소재·색이 잘림, 10-10 시험), 검색은 정가·판매처가 링크에 없을 때 1번만.
    def call(model: str, fetch: str, search: str):
        return c.messages.create(
            model=model, max_tokens=2000,
            tools=[{"type": fetch, "name": "web_fetch", "max_uses": len(urls), "max_content_tokens": 8000},
                   {"type": search, "name": "web_search", "max_uses": 1}],
            messages=msgs)
    msgs = [{"role": "user", "content": (
            f"오늘은 {F.today()}입니다. 아래 상품 링크를 하나씩 열어 제품 정보를 정리해 주세요. 링크 페이지가 가장 믿을 만한 자료입니다. "
            "정가·판매처 가격이 링크에 없을 때만 웹 검색을 1번 하고, 검색 결과 요약에 보이는 값만 쓰세요(페이지를 더 열지 않기). "
            "인사말·설명 없이 아래 모양만 답하세요. 직접 확인한 것만 쓰고 지어내지 마세요. 못 찾은 항목은 '확인 안 됨'이라고 쓰지 말고 그 줄을 아예 빼세요.\n"
            "제품마다 이 모양으로 (값이 있는 줄만):\n"
            "[제품] 브랜드(한글·영문) | 제품명(영문 원어) | 가격(원)\n"
            "브랜드 : \n제품명 : \n품번 : \n정가 : \n할인가 : (판매처, 확인한 날)\n판매처별 가격 : 판매처 가격, 판매처 가격\n"
            "해외 가격 : 원래 통화 금액 (약 ○○원, 오늘 환율 기준)\n소재 : \n색 : \n"
            "그 아래 디자인 특징(실루엣·디테일·핏) 2~3줄. 맨 끝에 '출처:' 아래 확인한 주소.\n\n" + "\n".join(urls))}]
    try:
        msg, inp, out = call("claude-haiku-4-5", "web_fetch_20250910", "web_search_20250305"), 1.0, 5.0  # Haiku 4.5: 1·5달러 / 100만 토큰
    except anthropic.BadRequestError as e:  # Haiku에서 웹 도구가 안 되면 Sonnet으로 (같은 제한)
        print(f"Haiku 링크 읽기 실패 → Sonnet: {str(e)[:160]}")
        msg, inp, out = call("claude-sonnet-5-5", "web_fetch_20260209", "web_search_20260209"), 2.0, 10.0  # Sonnet 5.5: 2·10달러
    u = msg.usage
    searches = getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
    F.SPENT["claude"] += (u.input_tokens * inp + u.output_tokens * out) / 1_000_000 + searches * 0.01
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def write_with_links(slug: str, n: int, urls: list[str]) -> Path:
    """대표가 고른 제목(n번) + 구글 렌즈로 찾은 상품 링크 → 링크 제품 정보를 조사 메모 맨 앞에 넣고 원문 프롬프트대로 글 (대표 결정 2026-10-09)."""
    tdir = next(F.FLOW.glob(f"*/{slug}"), None)
    if not tdir:
        raise SystemExit(f"주제 폴더 없음: {slug}")
    if urls:
        facts = link_facts(urls)
        r = tdir / "research.md"
        old = r.read_text(encoding="utf-8") if r.exists() else ""
        r.write_text("[대표가 준 상품 링크에서 확인한 제품 정보 — 가장 믿을 만한 자료, 본문 제품 정보는 이걸 기준으로]\n"
                     + facts + "\n\n" + old, encoding="utf-8")
    return produce(slug, n)


def from_links(text: str) -> Path:
    """'[패션링크]' 이슈: 첫 줄 = 인물 아이템, 다음 줄들 = 상품 링크 → 조사 + 링크 제품 정보 → 제목 → ★추천 제목으로 초안."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    urls = [l for l in lines if l.startswith("http")]
    kw = next((l for l in lines if not l.startswith("http")), "")[:40]
    if not kw or not urls:
        raise SystemExit("첫 줄에 '인물 아이템', 다음 줄에 상품 링크가 필요해요.")
    facts = link_facts(urls)
    memo = (research(kw) or F.claude_research(kw)) + "\n\n[대표가 준 상품 링크에서 확인한 제품 정보 — 가장 믿을 만한 자료]\n" + facts
    d = titles(kw, memo)
    T = F.load(d / "titles.yaml", {})
    n = next((i for i, t in enumerate(T.get("items", []), 1) if t.get("rank") == 1), 1)
    produce(d.name, n)
    return d


def _grok_research(kw: str) -> str:
    return F.grok(
        f"오늘은 {F.today()}(한국 시간)입니다. 블로그 글을 쓰기 위한 조사 메모를 만들어 주세요. 키워드(주어): {kw}\n"
        "웹과 X에서 어제·오늘 나온 기사·공식 SNS·브랜드 공식 사이트를 확인하고 교차검증하세요. 아래 순서로 짧게:\n"
        "1) 무슨 일인지 (방송·행사·공항·SNS·작품, 날짜)\n"
        "2) 착용·사용 제품: 제품마다 한 줄씩 정확히 이 모양으로 — [제품] 브랜드(한글·영문) | 제품명(영문 원어·모델명·라인명까지) | 가격(원, 공식 판매가와 기준 시점, 모르면 '확인 안 됨') | 품번·상품코드 | 가격 자세히(정가·할인가·판매처별 가격, 해외가는 원래 통화와 원화 환산)."
        " 브랜드나 제품명을 모르면 그 칸에 '확인 안 됨'. 세트 상품인지 각각 판매인지도 적기\n"
        "3) 스타일링 포인트(색·소재·실루엣)\n"
        "4) 관련 인물(같은 그룹·작품·가족·출연자) — 실제 관련 있는 사람만\n"
        "5) 사람들 반응(X), 소문은 '소문' 표시\n"
        "맨 끝에 '출처:' 아래 제목과 URL. 확인 안 된 제품·가격은 '확인 안 됨'이라고 쓰고 지어내지 마세요. 사생활 추측은 쓰지 마세요.",
        days=2, web=True, turns=2)


# ---------------------------------------------------------------- 제목 (그룹 3 × 5 + 최종 1)

GROUPS = ["그룹 1 주인공 숨김", "그룹 2 이름 노출", "그룹 3 관련 인물"]
TITLES = {"type": "object", "additionalProperties": False, "required": ["groups", "final", "person"],
          "properties": {
              "person": {"type": "string", "description": "주인공 이름"},
              "groups": {"type": "array", "description": "그룹 1·2·3 순서로 3개",
                         "items": {"type": "object", "additionalProperties": False, "required": ["group", "titles"],
                                   "properties": {"group": {"type": "string", "enum": GROUPS},
                                                  "titles": {"type": "array", "items": {"type": "string"}}}}},
              "final": {"type": "string", "description": "15개 중 최종 추천 제목 1개"}}}


def title_guide() -> str:
    """제목 고수(경제토르·유미) 공식 — 구조만 참고 (대표 지시 2026-10-05, content/title_refs.py)"""
    from .title_refs import guide_text
    return guide_text(F.BLOG["id"])


PRICE = re.compile(r"\d[\d,.]*\s*(만|억)?\s*원")


def has_product(memo: str) -> bool:
    """조사 메모에 확인된 가격(=브랜드·제품이 특정됨)이 있는지. '확인 안 됨' 줄은 빼고 본다 (대표 결정 2026-10-08:
    쿠니네처럼 '한 인물 + 한 아이템 + 가격·브랜드 반전'이 되는 주제만 자동으로 쓴다)."""
    body = memo.split("출처:")[0] + "\n" + "\n".join(l for l in memo.split("\n") if l.startswith("- ") and "네이버 쇼핑 판매가" in l)
    return any(PRICE.search(l) for l in body.splitlines()
               if "확인 안" not in l and "확인되지" not in l and "미확인" not in l and not l.startswith("- 비슷한"))


def titles(kw: str, memo: str | None = None) -> Path:
    d = F.FLOW / F.today() / F.topic_slug(kw)
    d.mkdir(parents=True, exist_ok=True)
    memo = memo or research(kw) or F.claude_research(kw)
    (d / "research.md").write_text(f"# 조사 메모: {kw}\n\n{memo}\n", encoding="utf-8")
    out = F.claude_json(prompt() + [g for g in [title_guide()] if g], (
        f"키워드(주어): {kw}\n\n[조사 메모]\n{memo[:10000]}\n\n이번 단계는 **제목만** 만듭니다. 원문의 제목 규칙대로 그룹 1·2·3 각 5개와 "
        "최종 추천 1개를 JSON으로 주세요.\n\n" + __import__("content.blog_stats", fromlist=["x"]).title_hint(F.BLOG["id"]) + __import__("content.good_rules", fromlist=["x"]).title_hint(F.BLOG["id"])), TITLES, stage="제목(연예·패션)")
    person = out.get("person", "")
    items, groups = [], []

    def add(t: str, g: str, rank: int | None) -> int:
        for i, x in enumerate(items):
            if x["title"] == t:
                return i
        n = len(t)
        flags = ([f"{n}자(35자 넘음)"] if n > 35 else []) + (["괄호"] if re.search(r"[\[\]()]", t) else [])
        if g.startswith("그룹 1") and person and person in t:
            flags.append("주인공 이름 들어감")
        items.append({"title": t, "type": g.split()[0] + " " + g.split()[1], "rank": rank, "best": rank == 1,
                      "chars": n, "flags": flags})
        return len(items) - 1

    add(out["final"], next((g["group"] for g in out["groups"] if out["final"] in g["titles"]), GROUPS[0]), 1)
    for g in out["groups"]:
        groups.append({"type": g["group"], "idx": [add(t, g["group"], None) for t in g["titles"][:5]], "best": None})
    from .good_rules import ensure  # 반응굿 유형이 하나도 없으면 3개 보충 (대표 지시 2026-10-08)
    extra = ensure(items, F.BLOG["id"], kw, memo, prompt(), 35)
    if extra:
        groups.insert(0, {"type": "반응굿 유형", "idx": [add(t, "반응굿 유형", None) for t in extra], "best": None})
    (d / "chosen.yaml").unlink(missing_ok=True)
    F.save(d / "titles.yaml", {"keyword": kw, "person": person, "mode": "연예패션",
                               "made": datetime.now(F.KST).strftime("%H:%M"), "items": items, "groups": groups})
    print(f"제목 {len(items)}개 → {d}")
    return d


# ---------------------------------------------------------------- 본문

IMG = {"type": "object", "additionalProperties": False, "required": ["kind", "query", "query_en", "prompt", "stock_query", "alt"],
       "properties": {"kind": {"type": "string", "enum": ["person", "product"]}, "query": {"type": "string"},
                      "query_en": {"type": "string"}, "prompt": {"type": "string"}, "stock_query": {"type": "string"},
                      "alt": {"type": "string"}}}
BODY = {"type": "object", "additionalProperties": False,
        "required": ["greeting", "sections", "summary", "tags", "sources", "thumb", "area"],
        "properties": {
            "area": {"type": "string"},
            "greeting": {"type": "string", "description": "첫 문단(도입). 블로그 설정의 인사말 규칙을 따름"},
            "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["heading", "images", "paragraphs"],
                                                    "properties": {"heading": {"type": "string"},
                                                                   "images": {"type": "array", "items": IMG},
                                                                   "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
            "summary": {"type": "string", "description": "숫자·순서 말 없는 짧은 전체 요약"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "8개 안팎(6~10개): 인물 → 인물+아이템 → 브랜드 → 브랜드+아이템 → 일반 키워드 순"},
            "sources": {"type": "array", "items": {"type": "string"}},
            "thumb": IMG}}


def text_of(a: dict) -> str:
    return re.sub(r"\*\*|__|(?<!\*)\*(?!\*)", "", "\n\n".join([a["greeting"]] + [p for s in a["sections"] for p in [s["heading"]] + s["paragraphs"]]))  # 글자 수는 강조 표시 빼고


NO_INTRO = {"fashion": ["캐시미어 다이어리", "캐다입니다", "캐다예요", "캐다에요"]}  # 본문에 쓰면 안 되는 자기소개


def check(a: dict) -> list[str]:
    t, bad = text_of(a), []
    if len(t) < 1500:  # 글자 수는 원문 프롬프트 기준 (대표 결정 2026-10-08)
        bad.append(f"본문 {len(t)}자 → 1,500자 이상(1,800~2,500자)")
    if re.search(r"\d|첫째|둘째|셋째|두 가지|세 가지", a["summary"]):
        bad.append("요약에 숫자·순서 말 → 빼기")
    raw = "\n".join(p for s in a["sections"] for p in s["paragraphs"])
    if len(re.findall(r"\*\*|__", raw)) // 2 > 2:  # 쿠니네는 강조 거의 없음 (조사 2026-10-08)
        bad.append("굵게·밑줄 강조 → 글 전체 2곳 이내로")
    hit = [m for m in META if m in t]
    if hit:
        bad.append("제작 과정 문장 → 빼기: " + ", ".join(hit[:5]))
    if F.PRESS.search(t):
        bad.append("언론사명·링크 → 빼기")
    if not 17 <= len(a["tags"]) <= 19:  # 쿠니네 실제 18~19개 (대표 결정 2026-10-08 블로그 글 조사 후, 원문 '20개 미만' 안)
        bad.append(f"해시태그 {len(a['tags'])}개 → 18~19개")
    if not 7 <= len(a["sections"]) <= 9:  # 원문 추천 흐름 8구간 (대표 지적 2026-10-07)
        bad.append(f"소제목 구간 {len(a['sections'])}개 → 8개(전체 착장 → 눈에 띈 제품 → 브랜드·제품명 → 디자인·소재 → 가격 → 실루엣·어울리는 이유 → 따라 입기 → 마무리)")
    if re.search(r"알려진 바가 없|확인되지 않아|확인되지 않았|정보가 없어", t):
        bad.append("'가격이 알려지지 않았다' 같은 조사 과정 문장 → 빼고, 같은 라인 공식가나 가격대 고르는 기준으로")
    few = [s["heading"] for s in a["sections"][:-1] if len(s["images"]) < 1]  # 구간마다 사진 1장 (마무리 제외, 대표 결정 2026-10-08 사진 줄이기)
    if few:
        bad.append("사진 없는 구간 → 1장씩: " + ", ".join(few[:5]))
    many = [s["heading"] for s in a["sections"] if len(s["images"]) > 1]
    if many:
        bad.append("사진 2장 이상 구간 → 1장으로 줄이기: " + ", ".join(many[:5]))
    # 패션은 인사말·자기소개 없이 시작 (대표 지시 2026-10-07 "캐시미어 다이어리 캐다입니다. 이런 건 안 나오게")
    intro = [w for w in NO_INTRO.get(F.BLOG["id"], []) if w in t]
    if intro:
        bad.append("블로그 이름·닉네임 자기소개 → 빼고 바로 이야기로 시작: " + ", ".join(intro))
    return bad


def produce(slug: str, n: int) -> Path:
    tdir = next(F.FLOW.glob(f"*/{slug}"), None)
    if not tdir:
        raise SystemExit(f"주제 폴더 없음: {slug}")
    T = F.load(tdir / "titles.yaml")
    pick, kw = T["items"][n - 1], T["keyword"]
    memo = (tdir / "research.md").read_text(encoding="utf-8")
    sys_prompt = prompt()
    ask = (f"키워드(주어): {kw}\n확정 제목: {pick['title']}\n주인공: {T.get('person', '')}\n\n[조사 메모]\n{memo[:10000]}\n\n"
           "이번 단계는 **본문만** 씁니다(제목은 정해졌습니다). 원문 본문 규칙과 덧붙임·블로그 설정대로 JSON으로 주세요." "\n본문은 확정 제목이 약속한 것(숫자·질문·반전·비교)에 반드시 답하도록, 조사 메모에서 제목과 직접 관련된 사실을 먼저 씁니다(대표 확인 2026-10-09).")
    a = F.claude_json(sys_prompt, ask, BODY, stage="글쓰기(연예·패션)")
    bad = check(a)
    if bad:
        a = F.claude_json(sys_prompt, ask + "\n\n[고칠 것]\n" + "\n".join(f"- {b}" for b in bad)
                          + "\n\n[지난 초안]\n" + json.dumps(a, ensure_ascii=False), BODY, stage="고쳐쓰기(형식)")
    left = check(a)
    post = F.POSTS / slug
    post.mkdir(parents=True, exist_ok=True)
    credits, used, prompts = [], set(), []

    def ask(spec: dict, size: str) -> str:  # ChatGPT·제미나이에 붙여넣을 글 (인물 사진은 실제 사진을 찾을 검색어 안내)
        return f"[실제 사진 찾기] {spec.get('query') or spec['alt']} — {spec['alt']}"  # 패션은 실사만 (대표 결정 2026-10-08)

    thumb = image(a["thumb"], post / "thumb", "1024x1024", credits, used)
    prompts.append({"n": 1, "label": "썸네일 · " + a["thumb"]["alt"], "make": True, "file": thumb or "", "size": "1024x1024",
                    "person": True, "desc": a["thumb"].get("prompt", ""), "find": a["thumb"].get("query", ""),
                    "prompt": ask(a["thumb"], "1024x1024")})
    lines = [f"[이미지 1_썸네일: {thumb or '-'}]"]
    lines.append(a["greeting"])
    k = 2
    for sec in a["sections"]:
        for im in sec["images"][:3]:
            if k - 1 > MAX_IMAGES:
                break
            # 맨 앞 4장(썸네일 + 본문 3장)은 대표가 ChatGPT·제미나이로 직접(고화질), 나머지는 실제 사진·무료 사진 (대표 결정 2026-10-06)
            f = image(im, post / f"img{k}", "1536x1024", credits, used, quality="high" if k <= HIGH_UPTO else "medium")
            label = re.sub(r"[:\[\]]", " ", im["alt"])[:30].strip()
            lines.append(f"[이미지 {k}_{label}: {f or '-'}]")
            prompts.append({"n": k, "label": im["alt"], "make": True, "file": f or "", "size": "1536x1024",
                            "person": True, "desc": im.get("prompt", ""), "find": im.get("query", ""),
                            "prompt": ask(im, "1536x1024")})
            k += 1
        lines.append(f"■ {sec['heading']}")
        lines += sec["paragraphs"]
    lines.append(a["summary"])
    # AI 사진 안내·사진 출처 줄 없음 (대표 결정 2026-10-08: 패션은 실사만, 쿠니네처럼 출처 안 적음)
    (post / "body.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    (post / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    others = [t for t in T["items"] if t is not pick][:4]
    tags = ",".join(x.replace("#", "").replace(" ", "") for x in a["tags"][:19])
    status = "✅ 발행 가능" + (" · ⚠️ 형식: " + " / ".join(left) if left else "")
    from .kunine import NO_CREDIT
    if NO_CREDIT:
        status += " · ⚠️ OpenAI 크레딧이 없어 AI 사진 대신 무료 사진으로 채움 — 대표가 크레딧 충전 필요"
    (post / "post.md").write_text("\n".join([
        f"# 발행 패키지 · {kw} ({F.BLOG['name']})", "", f"**상태:** {status}",
        f"**본문:** {len(text_of(a))}자 · 사진 {k - 2}장 + 썸네일", "",
        f"- 카테고리: **{a['area']}**", f"- 태그: {tags}", "",
        "## 제목 (추천 ★)", "", f"1. ★ {pick['title']} — {pick['type']}",
        *[f"{i + 2}. {t['title']} — {t['type']}" for i, t in enumerate(others)], "",
        "## 본문", "", "(body.txt)", "", "## 출처", "", *[f"- {s}" for s in a["sources"]],
        "", "## 사진 출처 (위키미디어 사진은 사진 아래에 작가·라이선스 표시가 필요해요)", "", *([f"- {c}" for c in credits] or ["- 없음"])]),
        encoding="utf-8")
    F.save(tdir / "chosen.yaml", {"title": pick["title"], "post": slug, "at": datetime.now(F.KST).strftime("%H:%M")})
    print(f"제작 완료 → {post}")
    return post


# ---------------------------------------------------------------- 사진: 실제 사진(위키미디어 공용) → 제품 AI 사진 → Pexels

FASHION_LEAD = ("Luxury fashion magazine editorial still-life photograph, soft natural studio daylight, refined styling on "
                "cream linen or warm stone, quiet-luxury mood, ultra-detailed textures of fabric, knit, leather and metal "
                "hardware, true-to-life colors, shallow depth of field, high-end catalog quality. ")  # 고화질 (2026-10-06)

def image(spec: dict, stem: Path, size: str, credits: list[str], used: set, quality: str = "high") -> str | None:
    if NO_AUTO_PHOTOS:  # 본문 사진은 프롬프트만, 자동으로 구하지 않음 (대표 결정 2026-10-08: 엉뚱한 무료 사진·위키미디어 동명 사진 문제)
        return None
    if spec["kind"] == "person":
        got = commons(spec.get("query_en") or spec["query"], spec["query"], stem, used)
        if got:
            credits.append(f"{got[0]}: 위키미디어 공용 · {got[1]} — {spec['alt']}")
            return got[0]
    if spec.get("prompt") and ai_photo(spec["prompt"] + " Product only, no people, no hands, no face.", stem.with_suffix(".png"), size,
                                       quality=quality, lead=FASHION_LEAD):
        credits.append(f"{stem.with_suffix('.png').name}: AI 제품 이미지(GPT Image) — {spec['alt']}")
        return stem.with_suffix(".png").name
    got = pexels(spec.get("stock_query", ""), stem.with_suffix(".jpg"), size, used)
    if got:
        credits.append(f"{stem.with_suffix('.jpg').name}: Pexels · {got} — {spec['alt']}")
        return stem.with_suffix(".jpg").name
    credits.append(f"{stem.name}: ⚠️ 사진 못 구함 — {spec['alt']}")
    return None


def commons(q_en: str, q_ko: str, stem: Path, used: set, must: list[str] | None = None) -> tuple[str, str] | None:
    """위키미디어 공용에서 그 인물 사진 중 자유 이용(CC0·퍼블릭 도메인·CC BY·CC BY-SA)만. (파일명, '작가 · 라이선스')."""
    for q in [x for x in (q_en, q_ko) if x]:
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
                "gsrsearch": f"{q} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600})
            pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        except Exception as e:  # noqa: BLE001
            print(f"위키미디어 실패 {q}: {str(e)[:100]}")
            continue
        for pg in pages:
            info = (pg.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            lic = re.sub(r"<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", ""))
            artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()[:60]
            if pg.get("pageid") in used or not any(f in lic.lower() for f in FREE) or info.get("width", 0) < 600:
                continue
            if must and not any(m.lower() in (pg.get("title") or "").lower() for m in must):  # 파일 이름에 회사 이름이 있어야 (경제, 2026-10-06)
                continue
            g = requests.get(info.get("thumburl") or info["url"], headers=UA, timeout=60)
            if not g.ok:
                continue
            used.add(pg.get("pageid"))
            out = stem.with_suffix(".jpg")
            out.write_bytes(g.content)
            return out.name, f"{artist or '작가 미상'} · {lic} · {info.get('descriptionurl', '')}"
    return None
