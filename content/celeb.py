"""연예인 패션 블로그(캐시미어 다이어리) (대표 결정 2026-10-05, 연예·패션은 같은 날 하나로 합침).

프롬프트: prompts/ent-fashion-blog.md(강사 원문, 그대로) + prompts/addon-common-celeb.md(우리 자동화용) + 블로그별 페르소나
(prompts/addon-fashion.md, config/blogs.yaml의 addon).
역할: 조사 = Grok(웹 + X, 어제·오늘) · 글 = Claude · 사진 = 실제 사진(위키미디어 공용, 자유 이용 허락된 것) → 제품 AI 사진(GPT Image)
→ Pexels. SNS·방송 장면·언론사 사진은 자동으로 가져오지 않는다(저작권·초상권).

titles <키워드>          : 그룹 1(주인공 숨김)·2(이름 노출)·3(관련 인물) 각 5개 + 최종 추천 1개
produce <주제폴더> <번호> : 인사말 · 1,500자 이상 본문 · 숫자 없는 요약 · 해시태그 19개 이하 · 구간마다 사진 2장 + 썸네일
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import requests

from market.common import ROOT
from . import econ_flow as F
from .kunine import ai_photo, pexels, photo_prompt

UA = {"User-Agent": "shorts-engine/1.0 (blog image lookup; contact via GitHub)"}
FREE = ("cc0", "public domain", "cc by", "cc-by", "pd")  # 위키미디어 자유 이용 라이선스만
META = ("사용자가 제공", "첨부한", "첨부 자료", "캡처", "검색해보니", "확인해보니", "이번 글에서는", "이번 포스팅에서는",
        "제가 확인한 바로는", "자료를 기준으로", "제공된 정보", "검색 결과", "출처를 확인", "이미지 삽입", "사진 삽입", "사진 자리")
HIGH_UPTO = 4  # 글 맨 앞부터 이 번호까지 고화질 (1 = 썸네일)
MAX_IMAGES = 12  # 원문 "최대한 많이" — 구간마다 최대 3장 (대표 지시 2026-10-06 "패션은 사진에 힘주고")


def prompt() -> list[str]:
    b = F.BLOG
    files = [b["prompt"], "prompts/addon-common-celeb.md", b["addon"]]
    return [re.sub(r"<!--.*?-->", "", (ROOT / f).read_text(encoding="utf-8"), flags=re.S).strip() for f in files]


def research(kw: str) -> str:
    return F.grok(
        f"오늘은 {F.today()}(한국 시간)입니다. 블로그 글을 쓰기 위한 조사 메모를 만들어 주세요. 키워드(주어): {kw}\n"
        "웹과 X에서 어제·오늘 나온 기사·공식 SNS·브랜드 공식 사이트를 확인하고 교차검증하세요. 아래 순서로 짧게:\n"
        "1) 무슨 일인지 (방송·행사·공항·SNS·작품, 날짜)\n"
        "2) 착용·사용 제품: 제품명·브랜드·가격(원, 공식 판매가와 기준 시점). 제품마다 따로. 세트 상품인지 각각 판매인지\n"
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


def titles(kw: str) -> Path:
    d = F.FLOW / F.today() / F.topic_slug(kw)
    d.mkdir(parents=True, exist_ok=True)
    memo = research(kw) or F.claude_research(kw)
    (d / "research.md").write_text(f"# 조사 메모: {kw}\n\n{memo}\n", encoding="utf-8")
    out = F.claude_json(prompt() + [g for g in [title_guide()] if g], (
        f"키워드(주어): {kw}\n\n[조사 메모]\n{memo[:10000]}\n\n이번 단계는 **제목만** 만듭니다. 원문의 제목 규칙대로 그룹 1·2·3 각 5개와 "
        "최종 추천 1개를 JSON으로 주세요."), TITLES, stage="제목(연예·패션)")
    person = out.get("person", "")
    items, groups = [], []

    def add(t: str, g: str, rank: int | None) -> int:
        for i, x in enumerate(items):
            if x["title"] == t:
                return i
        n = len(t)
        flags = ([f"{n}자(30자 넘음)"] if n > 30 else []) + (["괄호"] if re.search(r"[\[\]()]", t) else [])
        if g.startswith("그룹 1") and person and person in t:
            flags.append("주인공 이름 들어감")
        items.append({"title": t, "type": g.split()[0] + " " + g.split()[1], "rank": rank, "best": rank == 1,
                      "chars": n, "flags": flags})
        return len(items) - 1

    add(out["final"], next((g["group"] for g in out["groups"] if out["final"] in g["titles"]), GROUPS[0]), 1)
    for g in out["groups"]:
        groups.append({"type": g["group"], "idx": [add(t, g["group"], None) for t in g["titles"][:5]], "best": None})
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
            "greeting": {"type": "string", "description": "블로그 인사말로 시작하는 첫 문단"},
            "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["heading", "images", "paragraphs"],
                                                    "properties": {"heading": {"type": "string"},
                                                                   "images": {"type": "array", "items": IMG},
                                                                   "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
            "summary": {"type": "string", "description": "숫자·순서 말 없는 짧은 전체 요약"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "19개 이하"},
            "sources": {"type": "array", "items": {"type": "string"}},
            "thumb": IMG}}


def text_of(a: dict) -> str:
    return "\n\n".join([a["greeting"]] + [p for s in a["sections"] for p in [s["heading"]] + s["paragraphs"]])


def check(a: dict) -> list[str]:
    t, bad = text_of(a), []
    if len(t) < 1500:
        bad.append(f"본문 {len(t)}자 → 1,500자 이상(1,800~2,500자)")
    if re.search(r"\d|첫째|둘째|셋째|두 가지|세 가지", a["summary"]):
        bad.append("요약에 숫자·순서 말 → 빼기")
    hit = [m for m in META if m in t]
    if hit:
        bad.append("제작 과정 문장 → 빼기: " + ", ".join(hit[:5]))
    if F.PRESS.search(t):
        bad.append("언론사명·링크 → 빼기")
    if len(a["tags"]) >= 20:
        bad.append(f"해시태그 {len(a['tags'])}개 → 19개 이하")
    greet = {"fashion": "캐다입니다"}.get(F.BLOG["id"], "")
    if greet and greet not in a["greeting"]:
        bad.append(f"인사말 '{greet}'로 시작하기")
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
           "이번 단계는 **본문만** 씁니다(제목은 정해졌습니다). 원문 본문 규칙과 덧붙임·블로그 설정대로 JSON으로 주세요.")
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
        if spec["kind"] == "person":
            return f"[실제 사진 찾기] {spec['query']} — {spec['alt']}"
        return photo_prompt(spec["prompt"] + " Product only, no people, no hands, no face.", size, lead=FASHION_LEAD)

    thumb = image(a["thumb"], post / "thumb", "1024x1024", credits, used)
    prompts.append({"n": 1, "label": "썸네일 · " + a["thumb"]["alt"], "make": True, "file": thumb or "", "size": "1024x1024",
                    "person": a["thumb"]["kind"] == "person", "desc": a["thumb"].get("prompt", ""), "find": a["thumb"].get("query", ""),
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
                            "person": im["kind"] == "person", "desc": im.get("prompt", ""), "find": im.get("query", ""),
                            "prompt": ask(im, "1536x1024")})
            k += 1
        lines.append(f"■ {sec['heading']}")
        lines += sec["paragraphs"]
    lines.append(a["summary"])
    lines.append("※ 일부 이미지는 AI로 만든 제품 이미지입니다. 협찬·광고가 아닌 정보 글입니다.")
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
