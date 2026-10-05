"""쿠니네 방식 블로그 (대표 결정 2026-10-05: "쿠니네 방식으로 다 맞춘다").

역할: 조사 = Grok(웹 + X) · 글 = Claude · 그림 = GPT Image(실사풍) → 없으면 Pexels 무료 사진. (GPT 사실 대조는 대표 결정으로 뺌)
프롬프트: prompts/kunine-blog.md(강사 원문, 그대로) + prompts/kunine-addon.md(우리 자동화용 덧붙임).

titles <키워드>        : Grok 조사 메모 → Claude가 6유형 × 5개 = 30개 + 유형별 BEST 6 + 최종 BEST 5
produce <주제폴더> <번호>: 고른 제목으로 본문(1,500자) · 표 · Q&A · 해시태그 20 → 정보 이득·사실 대조·형식 검사
                         → 소제목 구간마다 그 아래 글과 이어지는 사진 2장 + 썸네일 → econ/posts/<글>/ (발행 도우미)
억선생 자료(그림 창고·캐릭터·쇼츠)는 클립용으로 남겨 두고 블로그에는 쓰지 않는다.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path

import requests

from market.common import ROOT
from . import econ_flow as F

PROMPT = ROOT / "prompts" / "kunine-blog.md"
ADDON = ROOT / "prompts" / "kunine-addon.md"
TYPES = ["비교형", "실행형", "이득형", "궁금형", "위협형", "반전형"]
REF_LINE = "참조문헌: 뉴스, 언론보도 및 공식자료"  # 강사 지정 문구, Q&A 뒤에 정확히 한 번
AI_NOTE = "※ 일부 이미지는 AI로 만든 이미지입니다. 이 글은 정보 제공용이며 투자 권유가 아닙니다."
MAX_IMAGES = 6           # 본문 사진 최대 (소제목 구간마다 2장)
IMG_QUALITY = "medium"   # 1장 약 $0.06 (가로) — 비용 때문에 medium. 실사풍은 medium도 거칠지 않음(첫 주 확인)


def prompt() -> list[str]:
    return [re.sub(r"<!--.*?-->", "", PROMPT.read_text(encoding="utf-8"), flags=re.S).strip(),
            re.sub(r"<!--.*?-->", "", ADDON.read_text(encoding="utf-8"), flags=re.S).strip()]


# ---------------------------------------------------------------- 조사 (Grok)

def research(kw: str) -> str:
    return F.grok(
        f"오늘은 {F.today()}(한국 시간)입니다. 블로그 글을 쓰기 위한 조사 메모를 만들어 주세요. 핵심키워드: {kw}\n"
        "웹과 X를 검색해 어제·오늘 나온 최신 뉴스·공식 발표·공시만 날짜순으로 확인하고, 여러 자료를 교차검증하세요"
        "(배경 설명에 꼭 필요한 숫자만 그 전 자료 허용).\n"
        "아래 순서로 짧게 정리:\n"
        "1) 이 키워드를 검색한 사람이 무엇부터 찾는지 (검색 의도 순서)\n"
        "2) 가장 최신 뉴스와 반복해서 나오는 핵심 이슈 (날짜 포함)\n"
        "3) 확인된 숫자·금액·날짜·조건 (기준 시점과 출처를 함께)\n"
        "4) 해석이 엇갈리는 점, 찬반·이해관계, 사람들이 놀라거나 억울해하거나 기대하는 점 (X 반응 포함, 소문은 '소문' 표시)\n"
        "5) 기관·증권가 전망 (누가 어떻게)\n"
        "6) 앞으로 일정\n"
        "맨 끝에 '출처:' 아래 기사 제목과 URL 목록. 확인 안 된 건 지어내지 말고 모른다고 쓰세요.",
        days=2, web=True, turns=2)  # 어제·오늘 뉴스만 (대표 결정 2026-10-05), 턴 2번으로 비용 절약


# ---------------------------------------------------------------- 제목 (6유형 × 5)

TITLES = {"type": "object", "additionalProperties": False, "required": ["groups", "final", "person"],
          "properties": {
              "person": {"type": "string", "description": "글 주인공 인물이 있으면 '회사 이름', 없으면 빈칸"},
              "groups": {"type": "array", "description": "비교형·실행형·이득형·궁금형·위협형·반전형 순서로 6개",
                         "items": {"type": "object", "additionalProperties": False,
                                   "required": ["type", "candidates", "best"],
                                   "properties": {"type": {"type": "string", "enum": TYPES},
                                                  "candidates": {"type": "array", "items": {"type": "string"}},
                                                  "best": {"type": "integer", "description": "candidates 중 BEST의 번호(0부터)"}}}},
              "final": {"type": "array", "description": "유형별 BEST 6개를 다시 비교해 고른 최종 BEST 5 (1번이 메인 추천)",
                        "items": {"type": "object", "additionalProperties": False, "required": ["title", "type"],
                                  "properties": {"title": {"type": "string"}, "type": {"type": "string", "enum": TYPES}}}}}}


def title_guide() -> str:
    """제목 고수(경제토르·유미) 공식 — 구조만 참고 (대표 지시 2026-10-05, content/title_refs.py)"""
    from .title_refs import guide_text
    return guide_text()


def titles(kw: str) -> Path:
    d = F.FLOW / F.today() / F.topic_slug(kw)
    d.mkdir(parents=True, exist_ok=True)
    memo = research(kw) or F.claude_research(kw)  # Grok이 안 되면 Claude 웹 검색으로 대신
    (d / "research.md").write_text(f"# 조사 메모: {kw}\n\n{memo}\n", encoding="utf-8")
    out = F.claude_json(prompt() + [g for g in [title_guide()] if g], (
        f"핵심키워드: {kw}\n\n[조사 메모]\n{memo[:10000]}\n\n"
        "이번 단계는 **제목만** 만듭니다(본문은 다음 단계). 원문의 '제목 후보 생성 규칙'대로 6유형 × 5개, 유형별 BEST, "
        "최종 BEST 5를 JSON으로 주세요."), TITLES, stage="제목(쿠니네)")
    core = kw.split()[0]
    items, seen = [], set()

    def add(title: str, typ: str, rank: int | None, best: bool) -> int:
        if title in seen:
            return next(i for i, t in enumerate(items) if t["title"] == title)
        seen.add(title)
        n = len(title)
        items.append({"title": title, "type": typ, "rank": rank, "best": best, "chars": n,
                      "flags": ([f"{n}자(45자 넘음)"] if n > 45 else []) + ([f"키워드 '{core}' 없음"] if core not in title else [])})
        return len(items) - 1

    bests = {g["type"]: g["candidates"][g["best"]] for g in out["groups"] if g["candidates"]
             and 0 <= g["best"] < len(g["candidates"])}
    for r, f in enumerate(out["final"][:5], 1):  # 최종 BEST 5가 1~5번
        add(f["title"], f["type"], r, f["title"] in bests.values())
    groups = []
    for g in out["groups"]:
        idx = [add(t, g["type"], None, t == bests.get(g["type"])) for t in g["candidates"][:5]]
        groups.append({"type": g["type"], "idx": idx, "best": idx[g["best"]] if 0 <= g["best"] < len(idx) else None})
    (d / "chosen.yaml").unlink(missing_ok=True)
    F.save(d / "titles.yaml", {"keyword": kw, "person": out.get("person", ""), "mode": "쿠니네",
                               "made": datetime.now(F.KST).strftime("%H:%M"), "items": items, "groups": groups})
    print(f"제목 {len(items)}개 (최종 BEST 5) → {d}")
    return d


# ---------------------------------------------------------------- 본문

IMG = {"type": "object", "additionalProperties": False, "required": ["prompt", "stock_query", "alt"],
       "properties": {"prompt": {"type": "string"}, "stock_query": {"type": "string"}, "alt": {"type": "string"}}}
BODY = {"type": "object", "additionalProperties": False,
        "required": ["intro", "sections", "closing", "table", "qa", "tags", "sources", "thumb", "area"],
        "properties": {
            "area": {"type": "string", "enum": F.AREAS},
            "intro": {"type": "array", "items": {"type": "string"}, "description": "도입부 문단들"},
            "sections": {"type": "array", "description": "소제목 구간 2~4개",
                         "items": {"type": "object", "additionalProperties": False,
                                   "required": ["heading", "images", "paragraphs"],
                                   "properties": {"heading": {"type": "string"},
                                                  "images": {"type": "array", "items": IMG,
                                                             "description": "이 구간 맨 위에 놓을 사진 2장 (아래 문단과 강하게 이어지게)"},
                                                  "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
            "closing": {"type": "array", "items": {"type": "string"}, "description": "마무리 문단들"},
            "table": {"type": "object", "additionalProperties": False, "required": ["title", "header", "rows", "after"],
                      "properties": {"title": {"type": "string"}, "header": {"type": "array", "items": {"type": "string"}},
                                     "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                                     "after": {"type": "integer", "description": "몇 번째 소제목 구간(1부터) 뒤에"}}},
            "qa": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["q", "a"],
                                              "properties": {"q": {"type": "string"}, "a": {"type": "string"}}}},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "해시태그용 단어 20개 (# 없이)"},
            "sources": {"type": "array", "items": {"type": "string"}, "description": "근거 출처 (블로그에 안 나감)"},
            "thumb": IMG}}


def text_of(a: dict) -> str:
    return "\n\n".join(a["intro"] + [p for s in a["sections"] for p in [s["heading"]] + s["paragraphs"]] + a["closing"])


def check(a: dict, kw: str) -> list[str]:
    """형식 검사(코드): 1,500자 이내 · 언론사명/링크 없음 · 핵심키워드 20회 이내 · Q&A 3개 · 해시태그 20개."""
    t = text_of(a)
    bad, core = [], kw.split()[0]
    if len(t) > 1550:
        bad.append(f"본문 {len(t)}자 → 공백 포함 1,500자 안으로")
    m = F.PRESS.findall(t + " ".join(x["q"] + x["a"] for x in a["qa"]) + " ".join(a["tags"]))
    if m:
        bad.append(f"언론사명·링크 {len(m)}곳 → 빼고 사실만 (공식 발표는 기관 이름만)")
    if t.count(core) > 20:
        bad.append(f"핵심키워드 '{core}' {t.count(core)}회 → 20회 이내")
    if len(a["qa"]) != 3:
        bad.append(f"Q&A {len(a['qa'])}개 → 3개")
    if len(a["tags"]) < 18:
        bad.append(f"해시태그 {len(a['tags'])}개 → 20개")
    return bad


def gain(kw: str, a: dict) -> tuple[bool, str]:
    """정보 이득 게이트 (CLAUDE.md): 네이버 블로그 검색 상위 10개(제목·요약)에 없는 것이 하나라도 있나."""
    rows = F.top10(kw)
    if not rows:
        return False, "⚠️ 네이버 검색이 안 돼 검사를 못 함 (발행 전 확인)"
    comp = "\n".join(f"{i}. {r['title']} — {r['desc']}" for i, r in enumerate(rows, 1))
    g = F.claude_json(["너는 깐깐한 편집장이다. 상위 글과 겹치는 내용은 이득으로 치지 않는다."],
                      f"[검색어] {kw}\n[상위 10개 글]\n{comp}\n\n[우리 초안]\n{text_of(a)}\n\n상위 글들에 없고 우리 초안에만 있는 "
                      "독자에게 쓸모 있는 것(새 숫자·비교·일정·관점)을 적고, 하나라도 분명하면 pass=true.", F.GAIN, stage="정보 이득")
    return bool(g["pass"] and g["gain"]), (" / ".join(g["gain"][:3]) if g["gain"] else g["missing"])


def produce(slug: str, n: int) -> Path:
    tdir = next(F.FLOW.glob(f"*/{slug}"), None)
    if not tdir:
        raise SystemExit(f"주제 폴더 없음: {slug}")
    T = F.load(tdir / "titles.yaml")
    pick, kw = T["items"][n - 1], T["keyword"]
    memo = (tdir / "research.md").read_text(encoding="utf-8")
    sys_prompt = prompt() + F.learned()[:1]  # 대표가 고친 곳(있으면)만 덧붙임
    ask = (f"핵심키워드: {kw}\n확정 제목: {pick['title']} ({pick['type']})\n\n[조사 메모]\n{memo[:10000]}\n\n"
           "이번 단계는 **본문만** 씁니다(제목은 정해졌습니다). 원문의 본문 규칙과 덧붙임 규칙대로 JSON으로 주세요.")
    a = F.claude_json(sys_prompt, ask, BODY, stage="글쓰기(쿠니네)")
    ok_gain, gain_note = True, "생략 (대표 결정 2026-10-05)"  # 정보 이득 검사 뺌 — gain()은 다시 켤 때를 위해 남김
    issues: list[dict] = []  # GPT 사실 대조는 뺐다 (대표 결정 2026-10-05: "검사는 필요 없을 것 같다"). 숫자는 Grok 조사 메모 안에서만 쓴다
    bad = check(a, kw)
    if issues or bad:
        a = F.claude_json(sys_prompt, ask + "\n\n[고칠 것]\n" + "\n".join(f"- {b}" for b in bad)
                          + ("\n[사실 대조(GPT)]\n" + json.dumps(issues, ensure_ascii=False) if issues else "")
                          + "\n\n[지난 초안]\n" + json.dumps(a, ensure_ascii=False), BODY, stage="고쳐쓰기(사실·형식)")
    left = check(a, kw)
    post = F.POSTS / slug
    post.mkdir(parents=True, exist_ok=True)
    # 사진: 썸네일 + 구간마다 2장 (AI 실사풍 → 안 되면 Pexels)
    credits = []
    thumb = image(a["thumb"], post / "thumb.png", "1024x1024", credits, used=set())
    lines = [f"[이미지 1_썸네일: {thumb}]"] if thumb else []
    lines += a["intro"]
    k, used = 2, set()
    for si, sec in enumerate(a["sections"], 1):
        for im in sec["images"][:2]:
            if k - 1 > MAX_IMAGES:
                break
            f = image(im, post / f"img{k}.png", "1536x1024", credits, used)
            if f:
                label = re.sub(r"[:\[\]]", " ", im["alt"])[:20].strip()  # 도우미가 읽는 자리표 모양을 깨지 않게
                lines.append(f"[이미지 {k}_{label}: {f}]")
                k += 1
        lines.append(f"■ {sec['heading']}")
        lines += sec["paragraphs"]
        tb = a["table"]
        if tb.get("rows") and si == max(1, min(tb.get("after", 1), len(a["sections"]))):
            (post / "table.json").write_text(json.dumps({x: tb[x] for x in ("title", "header", "rows")}, ensure_ascii=False),
                                             encoding="utf-8")
            lines.append(f"[표 1: {tb['title']}]")
    lines += a["closing"]
    lines.append("\n".join(f"Q. {x['q']}\nA. {x['a']}" for x in a["qa"][:3]))
    lines += [REF_LINE, AI_NOTE]
    (post / "body.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    finals = [t for t in T["items"] if t.get("rank") and t is not pick][:4]
    tags = ",".join(x.replace("#", "").replace(" ", "") for x in a["tags"][:20])
    status = "✅ 발행 가능 (사실 대조 생략, 숫자는 조사 메모 기준)"
    if not ok_gain:
        status += " · ⚠️ 정보 이득 부족 — 발행 보류, Claude에게 알려 주세요"
    if left:
        status += " · ⚠️ 형식: " + " / ".join(left)
    (post / "post.md").write_text("\n".join([
        f"# 발행 패키지 · {kw} (쿠니네 방식)", "",
        f"**상태:** {status}", f"**정보 이득:** {gain_note}",
        f"**본문:** {len(text_of(a))}자 · 사진 {k - 2}장 + 썸네일", "",
        f"- 카테고리: **{a['area']}**", f"- 태그: {tags}", "",
        "## 제목 (추천 ★)", "", f"1. ★ {pick['title']} — {pick['type']}",
        *[f"{i + 2}. {t['title']} — {t['type']}" for i, t in enumerate(finals)], "",
        "## 본문", "", "(body.txt)", "", "## 출처", "", *[f"- {s}" for s in a["sources"]],
        "", "## 사진 출처", "", *([f"- {c}" for c in credits] or ["- 없음"]),
        ]),
        encoding="utf-8")
    F.save(tdir / "chosen.yaml", {"title": pick["title"], "post": slug, "at": datetime.now(F.KST).strftime("%H:%M")})
    print(f"제작 완료 → {post}")
    return post


# ---------------------------------------------------------------- 사진 (대표 결정: AI 실사풍 먼저, 안 되면 무료 사진)

def image(spec: dict, out: Path, size: str, credits: list[str], used: set) -> str | None:
    if ai_photo(spec["prompt"], out, size):
        credits.append(f"{out.name}: AI 생성(GPT Image) — {spec['alt']}")
        return out.name
    got = pexels(spec["stock_query"], out.with_suffix(".jpg"), size, used)
    if got:
        credits.append(f"{out.with_suffix('.jpg').name}: Pexels · {got} — {spec['alt']}")
        return out.with_suffix(".jpg").name
    credits.append(f"{out.name}: ⚠️ 사진 못 구함 — {spec['alt']}")
    return None


def ai_photo(desc: str, out: Path, size: str) -> bool:
    if not F.key("OPENAI_API_KEY"):
        return False
    r = requests.post("https://api.openai.com/v1/images/generations", timeout=600,
                      headers={"Authorization": f"Bearer {F.key('OPENAI_API_KEY')}"},
                      json={"model": "gpt-image-2", "n": 1, "size": size, "quality": IMG_QUALITY, "prompt": (
                          "Photorealistic editorial news photograph, natural light, real-world location, sharp focus. "
                          + desc + " No identifiable real person's face, no logos, no brand marks, no readable text, "
                          "letters or numbers anywhere, no watermark, no charts.")})
    if r.status_code != 200:
        print(f"AI 사진 실패 HTTP {r.status_code}: {r.text[:160]}")
        return False
    F.SPENT["image"] += 0.042 if size == "1024x1024" else 0.063  # 어림: medium 단가
    out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return True


def pexels(query: str, out: Path, size: str, used: set) -> str | None:
    k = F.key("PEXELS_API_KEY")
    if not k or not query:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": k}, timeout=30,
                         params={"query": query, "per_page": 10,
                                 "orientation": "square" if size == "1024x1024" else "landscape"})
        r.raise_for_status()
        for ph in r.json().get("photos", []):
            if ph["id"] in used:
                continue
            g = requests.get(ph["src"]["large2x"], timeout=60)
            if g.ok:
                used.add(ph["id"])
                out.write_bytes(g.content)
                return f"{ph.get('photographer', '')} ({ph.get('url', '')})"
    except Exception as e:  # noqa: BLE001
        print(f"Pexels 실패 {query}: {str(e)[:100]}")
    return None
