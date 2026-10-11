"""쿠니네 방식 블로그 (대표 결정 2026-10-05: "쿠니네 방식으로 다 맞춘다").

역할: 조사 = Grok(웹 + X) · 글 = Claude · 사진 = 대표가 무료 앱으로 직접(마스터 §10: 실제 기업·현장·통계 사진, 본문 일치). (GPT 사실 대조는 대표 결정으로 뺌)
프롬프트: prompts/kunine-blog.md(강사 원문, 그대로) + prompts/kunine-addon.md(우리 자동화용 덧붙임).

titles <키워드>        : Grok 조사 메모 → Claude가 8유형 × 4개 = 32개 (유형마다 버튼) + 최종 BEST 1(★) (2026-10-10)
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
from .title_refs import VERSION_SCHEMA, versions_ask

PROMPT = ROOT / "prompts" / "kunine-blog.md"
ADDON = ROOT / "prompts" / "kunine-addon.md"
TYPES = ["비교형", "실행형", "이득형", "궁금형", "위협형", "반전형", "확신형", "자극형"]  # 2026-10-10 원문 8유형
PER_TYPE = 4   # 유형마다 만드는 후보 수 (대표 2026-10-10: 비용 위해 5→2 했다가 "제목이 너무 적다"로 4로. 도우미엔 유형마다 전부 보임)
REF_LINE = "참조문헌: 뉴스, 언론보도 및 공식자료"  # 강사 지정 문구, Q&A 뒤에 정확히 한 번
AI_NOTE = "※ 일부 이미지는 AI로 만든 이미지입니다. 이 글은 정보 제공용이며 투자 권유가 아닙니다."
MAX_IMAGES = 6           # 본문 사진 최대 (소제목 구간마다 2장)
IMG_QUALITY = "medium"   # 1장 약 $0.06 (가로) — 비용 때문에 medium. 실사풍은 medium도 거칠지 않음(첫 주 확인)
NO_AUTO_PHOTOS = True  # 대표 결정 2026-10-08: 사진은 대표가 프롬프트로 직접 (자동 무료·AI·위키미디어 사진 안 넣음)
AI_IMAGES = False        # 사진 자동 그리기(API) 끔 — 대표가 ChatGPT·제미나이 구독으로 직접 (대표 결정 2026-10-06). 다시 켜려면 True
HIGH_UPTO = 2            # 글 맨 앞부터 이 번호까지 고화질 AI (1 = 썸네일, 2 = 본문 첫 장), 나머지는 무료 사진
BRAND_QUALITY = "high"   # 회사(간판) 사진은 고화질 (대표 지시 2026-10-06: GPT 대화창 결과와 퀄이 다르다)


def prompt() -> list[str]:
    # 글 방식은 쿠니네 원문 + 덧붙임만 (대표 지시 2026-10-06: 고수에게서는 제목·키워드만 배움)
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


# ---------------------------------------------------------------- 제목 (8유형 × 5, 2026-10-10)

TITLES = {"type": "object", "additionalProperties": False, "required": ["groups", "final", "person"],
          "properties": {
              "person": {"type": "string", "description": "글 주인공 인물이 있으면 '회사 이름', 없으면 빈칸"},
              "groups": {"type": "array", "description": "비교형·실행형·이득형·궁금형·위협형·반전형·확신형·자극형 순서로 8개",
                         "items": {"type": "object", "additionalProperties": False,
                                   "required": ["type", "candidates", "best"],
                                   "properties": {"type": {"type": "string", "enum": TYPES},
                                                  "candidates": {"type": "array", "items": {"type": "string"}},
                                                  "best": {"type": "integer", "description": "candidates 중 BEST의 번호(0부터)"}}}},
              "final": {"type": "array", "description": "유형별 best 8개 중 고른 최종 BEST 1 (1번이 최종 1순위)",
                        "items": {"type": "object", "additionalProperties": False, "required": ["title", "type"],
                                  "properties": {"title": {"type": "string"}, "type": {"type": "string", "enum": TYPES}}}}}}


def title_guide() -> str:
    """제목 고수(경제토르·유미) 공식 — 구조만 참고 (대표 지시 2026-10-05, content/title_refs.py)"""
    from .title_refs import guide_text
    return guide_text(F.BLOG["id"])


def titles(kw: str) -> Path:
    d = F.FLOW / F.today() / F.topic_slug(kw)
    d.mkdir(parents=True, exist_ok=True)
    memo = research(kw) or F.claude_research(kw)  # Grok이 안 되면 Claude 웹 검색으로 대신
    (d / "research.md").write_text(f"# 조사 메모: {kw}\n\n{memo}\n", encoding="utf-8")
    out = F.claude_json(prompt() + [g for g in [title_guide()] if g], (
        f"핵심키워드: {kw}\n\n[조사 메모]\n{memo[:10000]}\n\n"
        "이번 단계는 **제목만** 만듭니다(본문은 다음 단계). 원문의 제목 규칙대로 8유형마다 4개씩(= 32개) 만들고, 유형마다 그중 best 하나를 고르고, "
        "그 유형별 best 8개 중 최종 BEST 1을 골라 JSON으로 주세요(45자 이내 기본, 자연스러우면 조금 길어도 됨).\n\n" + __import__("content.blog_stats", fromlist=["x"]).title_hint(F.BLOG["id"]) + __import__("content.good_rules", fromlist=["x"]).title_hint(F.BLOG["id"])),
        TITLES, stage="제목(쿠니네)")
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
    for r, f in enumerate(out["final"][:1], 1):  # 최종 BEST 1이 ★ (대표 결정 2026-10-10)
        add(f["title"], f["type"], r, f["title"] in bests.values())
    groups = []
    for g in out["groups"]:
        idx = [add(t, g["type"], None, t == bests.get(g["type"])) for t in g["candidates"][:PER_TYPE]]
        groups.append({"type": g["type"], "idx": idx, "best": idx[g["best"]] if 0 <= g["best"] < len(idx) else None})
    from .good_rules import ensure  # 반응굿 유형이 하나도 없으면 3개 보충 (대표 지시 2026-10-08)
    extra = ensure(items, F.BLOG["id"], kw, memo, prompt(), 45)
    if extra:
        groups.insert(0, {"type": "반응굿 유형", "idx": [add(t, "반응굿 유형", None, False) for t in extra], "best": None})
    (d / "chosen.yaml").unlink(missing_ok=True)
    F.save(d / "titles.yaml", {"keyword": kw, "person": out.get("person", ""), "mode": "쿠니네",
                               "made": datetime.now(F.KST).strftime("%H:%M"), "items": items, "groups": groups})
    print(f"제목 {len(items)}개 (유형별 best + 최종 ★) → {d}")
    return d


# ---------------------------------------------------------------- 본문

IMG = {"type": "object", "additionalProperties": False, "required": ["brand", "real_query", "prompt", "stock_query", "alt"],
       "properties": {"brand": {"type": "string", "description": "사진에 나오는 회사의 영문 공식 이름(예: Samsung Electronics, SK hynix). 회사가 아니면 빈칸"},
                      "real_query": {"type": "string", "description": "위키미디어 공용에서 그 회사의 실제 사옥·공장·매장 사진을 찾을 영어 검색어(예: Samsung Electronics Seocho building). 없으면 빈칸"},
                      "prompt": {"type": "string"}, "stock_query": {"type": "string"}, "alt": {"type": "string"}}}
BODY = {"type": "object", "additionalProperties": False,
        "required": ["intro", "sections", "closing", "table", "qa", "tags", "sources", "pixabay", "thumb", "area"],
        "properties": {
            "area": {"type": "string", "enum": F.AREAS},
            "intro": {"type": "array", "items": {"type": "string"}, "description": "도입부 문단들"},
            "sections": {"type": "array", "description": "질문형 소제목 구간 5~7개",
                         "items": {"type": "object", "additionalProperties": False,
                                   "required": ["heading", "images", "paragraphs"],
                                   "properties": {"heading": {"type": "string"},
                                                  "images": {"type": "array", "items": IMG,
                                                             "description": "이 구간 맨 위에 놓을 사진 1장 (아래 문단과 강하게 이어지게)"},
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
            "pixabay": {"type": "array", "items": {"type": "string"}, "description": "픽사베이 검색용 추천 키워드 5개 (영어)"},
            "thumb": IMG}}


def text_of(a: dict) -> str:
    return re.sub(r"\*\*|__|(?<!\*)\*(?!\*)", "", "\n\n".join(a["intro"] + [p for s in a["sections"] for p in [s["heading"]] + s["paragraphs"]] + a["closing"]))  # 글자 수는 강조 표시 빼고


def check(a: dict, kw: str) -> list[str]:
    """형식 검사(코드, 2026-10-10 원문): 질문형 소제목 5~7개 · 표 1개 이상 · 언론사명/링크 없음 · 핵심키워드 20회 이내 · Q&A 3개 · 해시태그 20개.
    글자 수 상한은 새 원문에 없어 검사하지 않음."""
    t = text_of(a)
    bad, core = [], kw.split()[0]
    if not 5 <= len(a["sections"]) <= 7:
        bad.append(f"소제목 구간 {len(a['sections'])}개 → 질문형 5~7개")
    if not (a.get("table") or {}).get("rows"):
        bad.append("표 없음 → 비교표 1개 이상")
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


def checklist(a: dict, kw: str, pick: dict | None = None) -> list[tuple[bool, str]]:
    """원문 프롬프트를 지켰는지 전체 점검표 (대표 요청 2026-10-10 '올리기 전 원문대로인지, 부족한 건 뭔지'). (됐나, 설명)."""
    t = text_of(a)
    core = kw.split()[0]
    n_sec = len(a["sections"])
    q_sec = sum(1 for sec in a["sections"] if sec.get("heading", "").strip().endswith("?"))
    press = F.PRESS.findall(t + " ".join(x["q"] + x["a"] for x in a["qa"]) + " ".join(a["tags"]))
    px = len(a.get("pixabay") or [])
    kc = t.count(core)
    emoji = len(re.findall(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", t))  # §13 과도한 이모지
    weird = re.findall(r"[`|{}<>\\]|\[\d+\]", t)  # §13 이상문자·내부 참조코드
    intro0 = (a.get("intro") or [""])[0]
    num_start = bool(re.search(r"\d", intro0[:20]))  # §4 첫 문장 숫자·사실로 시작
    # 원문 §15 자체 검수 중 '코드로 셀 수 있는' 항목만 (대표 지적 2026-10-10: 자의 해석·누락 없이 원문대로)
    return [
        (5 <= n_sec <= 7, f"§4 소제목(질문형) 5~7개 ({n_sec}개)"),
        (q_sec == n_sec and n_sec > 0, f"§4 소제목 전부 질문형 ({q_sec}/{n_sec})"),
        (bool((a.get("table") or {}).get("rows")), "§8 비교표 1개 이상 " + ("(있음)" if (a.get("table") or {}).get("rows") else "(없음)")),
        (len(a["qa"]) == 3, f"§9 Q&A 정확히 3개 ({len(a['qa'])}개)"),
        (18 <= len(a["tags"]) <= 21, f"§11 해시태그 20개 ({len(a['tags'])}개)"),
        (core in " ".join(a["tags"]).replace(" ", ""), f"§11 해시태그에 핵심키워드 '{core}' 포함"),
        (kc <= 20, f"§6 핵심키워드 '{core}' 20회 이내 ({kc}회)"),
        (not press, "§12 언론사명·링크·괄호출처 없음 " + (f"({len(press)}곳)" if press else "")),
        (px >= 5, f"§10 픽사베이 검색어 5개 ({px}개)"),
        (num_start, "§4 도입 숫자·사실로 시작"),
        (emoji <= 3, f"§13 과도한 이모지 없음 ({emoji}개)"),
        (not weird, "§13 이상문자·내부코드 없음 " + (f"({len(weird)}곳)" if weird else "")),
        (True, "§12 참조문헌 문구 1회 (코드가 자동 삽입)"),
    ] + ([
        (len(pick.get("title", "")) <= 45, f"§2 제목 45자 이내 ({len(pick.get('title',''))}자)"),
        (core in pick.get("title", "").replace(" ", ""), f"§2·6 제목에 핵심키워드 '{core}' 포함"),
    ] if pick else [])


def human_check() -> list[str]:
    """코드로 못 재는(사람이 봐야 하는) 원문 항목 — 자동 통과로 속이지 않게 따로 안내 (대표 지적 2026-10-10)."""
    # 글(본문) 검수용만 — 제목 개수·유형·제목끼리 중복은 '제목 생성' 단계 몫이라 뺌 (글 1개짜리에 '32개 만들라'는 헛짚음 방지, 2026-10-11)
    return ["말투가 자연스러운지(AI 티·같은 어미 반복 없이)",
            "숫자·사실이 맞는지(반올림·근삿값 차이는 괜찮음 — 단위·사실이 틀리거나 기준이 뒤섞인 것만, 전망/확정 구분)",
            "제목이 약속한 내용을 본문이 설명했는지", "'조사 메모에 따르면' 같은 작업 메모식 표현 없이 네이버에 바로 쓸 수 있는지"]


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
           "이번 단계는 **본문만** 씁니다(제목은 정해졌습니다). 원문의 본문 규칙과 덧붙임 규칙대로 JSON으로 주세요." "\n본문은 확정 제목이 약속한 것(숫자·질문·반전·비교)에 반드시 답하도록, 조사 메모에서 제목과 직접 관련된 사실을 먼저 씁니다(대표 확인 2026-10-09).")
    a = F.claude_json(sys_prompt, ask, BODY, stage="글쓰기(쿠니네)")
    ok_gain, gain_note = True, "생략 (대표 결정 2026-10-05)"  # 정보 이득 검사 뺌 — gain()은 다시 켤 때를 위해 남김
    issues: list[dict] = []  # GPT 사실 대조는 뺐다 (대표 결정 2026-10-05: "검사는 필요 없을 것 같다"). 숫자는 Grok 조사 메모 안에서만 쓴다
    # 원문 체크 8/10 넘을 때까지 최대 2번만 고쳐쓰기 (대표 요청 2026-10-10). 실패 기록은 남긴다. 검사는 코드(무료), 고쳐쓰기만 1회 비용
    from .econ_score import CFG as _kcfg
    cfg = F.load(_kcfg(), {}) or {}
    ratio = cfg.get("checklist_pass_ratio", 0.8)  # 원문 체크 통과율 목표 (대표 '8/10' → 80%)
    max_fix = cfg.get("max_rewrite", 3)  # 고쳐쓰기 최대 횟수 — 글로 고칠 수 있는 건 다 고칠 때까지 (안 줄면 멈춤, 2026-10-11)
    fix_log: list[str] = []
    first_bad: list[str] = []  # 처음에 걸린 것 전부 (고친 것 계산용, 2026-10-11)
    prev_bad = None
    for attempt in range(max_fix + 1):
        cl = checklist(a, kw, pick)
        fails = [txt for ok, txt in cl if not ok]
        ed = F.editor_review(text_of(a), pick["title"], kw, human_check()) if cfg.get("strict_editor") else []
        cur_bad = fails + ed
        if attempt == 0:
            first_bad = cur_bad
        need = int(len(cl) * ratio + 0.999)
        done = len(cl) - len(fails) >= need and not ed
        stuck = prev_bad is not None and len(cur_bad) >= prev_bad  # 지난번보다 안 줄면 글만으론 못 고치는 것 → 멈춤(비용 아낌)
        if done or stuck or attempt >= max_fix:
            break
        prev_bad = len(cur_bad)
        fix_log.append(f"{attempt + 1}차: 원문 {len(cl) - len(fails)}/{len(cl)}"
                       + (" · 원문부족 " + " / ".join(fails) if fails else "") + (" · 편집장 " + " / ".join(ed) if ed else ""))
        a = F.claude_json(sys_prompt, ask + "\n\n[반드시 고칠 것 — 글 수정만으로 고칠 수 있는 건 하나도 남기지 말고 모두 반영. "
                          "새 사실·외부 자료가 있어야만 고칠 수 있는 것은 그대로 둬도 된다]\n" + "\n".join(f"- {b}" for b in cur_bad)
                          + "\n\n[지난 초안]\n" + json.dumps(a, ensure_ascii=False), BODY, stage=f"고쳐쓰기{attempt + 1}")
    remaining = fails + ed          # 고쳐쓰기 뒤에도 남은 것 (글만으론 못 고치는 것 = 사람 확인)
    fixed = [x for x in first_bad if x not in remaining]   # 처음 걸렸다가 고쳐진 것
    left = check(a, kw)
    post = F.POSTS / slug
    post.mkdir(parents=True, exist_ok=True)
    # 사진: 썸네일 + 구간마다 2장 (AI 실사풍 → 안 되면 Pexels)
    credits, prompts = [], []
    thumb = image(a["thumb"], post / "thumb.png", "1024x1024", credits, used=set())
    prompts.append({"n": 1, "label": "썸네일 · " + a["thumb"]["alt"], "make": True, "file": thumb or "",
                    "desc": a["thumb"]["prompt"], "brand": a["thumb"].get("brand", ""), "size": "1024x1024",
                    "prompt": photo_prompt(a["thumb"]["prompt"], "1024x1024", a["thumb"].get("brand", ""))})
    lines = [f"[이미지 1_썸네일: {thumb or '-'}]"]
    lines += a["intro"]
    k, used = 2, set()
    for si, sec in enumerate(a["sections"], 1):
        for im in sec["images"][:1]:  # 구간마다 1장 (소제목 5~7개라, 2026-10-10)
            if k - 1 > MAX_IMAGES:
                break
            # 맨 앞 2장(썸네일 + 본문 첫 장)은 대표가 ChatGPT·제미나이로 직접(고화질), 나머지는 무료 사진 (대표 결정 2026-10-06)
            f = image(im, post / f"img{k}.png", "1536x1024", credits, used, tier="high" if k <= HIGH_UPTO else "free")
            label = re.sub(r"[:\[\]]", " ", im["alt"])[:20].strip()  # 도우미가 읽는 자리표 모양을 깨지 않게
            lines.append(f"[이미지 {k}_{label}: {f or '-'}]")
            prompts.append({"n": k, "label": im["alt"], "make": True, "file": f or "",
                            "desc": im["prompt"], "brand": im.get("brand", ""), "size": "1536x1024",
                            "prompt": photo_prompt(im["prompt"], "1536x1024", im.get("brand", ""))})
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
    (post / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.get("pixabay"):  # 원문 '픽사베이 추천 검색어 5개' (2026-10-10) → 도우미 사진 칸에 표시
        (post / "pixabay.txt").write_text("\n".join(a["pixabay"][:5]), encoding="utf-8")
    (post / "body.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    finals = [t for t in T["items"] if t.get("rank") and t is not pick][:4]
    from .tags import fix as fix_tags  # 붙인 형태 + 낱말 둘 다 (대표 지적 2026-10-10 '#애플주가'·'애플 주가')
    tags = ",".join(fix_tags(a["tags"], kw, 20))
    status = "✅ 발행 가능 (사실 대조 생략, 숫자는 조사 메모 기준)"
    if not ok_gain:
        status += " · ⚠️ 정보 이득 부족 — 발행 보류, Claude에게 알려 주세요"
    if left:
        status += " · ⚠️ 형식: " + " / ".join(left)
    if remaining:  # 편집장이 고쳐쓰고도 남은 지적 → 발행 전 확인 (대표 지적 2026-10-11)
        status += f" · ⚠️ 편집장 지적 {len(remaining)}건 — 발행 전 확인"
    if NO_CREDIT:
        status += " · ⚠️ OpenAI 크레딧이 없어 AI 사진 대신 무료 사진으로 채움 — 대표가 크레딧 충전 필요"
    cl = checklist(a, kw, pick)
    (post / "post.md").write_text("\n".join([
        f"# 발행 패키지 · {kw} (쿠니네 방식)", "",
        f"**상태:** {status}", f"**정보 이득:** {gain_note}",
        "", "## 원문 체크", "", *[f"- {'✅' if ok else '⚠️'} {txt}" for ok, txt in cl],
        *(["", "### 고쳐쓰기 기록(남긴 것)", *[f"- {x}" for x in fix_log]] if fix_log else []),
        *(["", "## 편집장 검토", "", f"고침 {len(fixed)} · 남음 {len(remaining)}",
           "", "### 고친 것", *([f"- {x}" for x in fixed] or ["- 없음"]),
           "", "### 아직 남은 것", *([f"- {x}" for x in remaining] or ["- 없음"])]
          if cfg.get("strict_editor") else
          ["", "### 코드로 못 재는 항목 (사람이 확인)", *[f"- 👀 {x}" for x in human_check()]]), "",
        f"**본문:** {len(text_of(a))}자 · 사진 {k - 2}장 + 썸네일", "",
        f"- 카테고리: **{a['area']}**", f"- 태그: {tags}", "",
        "## 제목 (추천 ★)", "", f"1. ★ {pick['title']} — {pick['type']}",
        *[f"{i + 2}. {t['title']} — {t['type']}" for i, t in enumerate(finals)], "",
        "## 본문", "", "(body.txt)", "", "## 출처", "", *[f"- {s}" for s in a["sources"]],
        "", "## 사진 출처", "", *([f"- {c}" for c in credits] or ["- 없음"]),
        ]),
        encoding="utf-8")
    F.save(tdir / "chosen.yaml", {"title": pick["title"], "post": slug, "at": datetime.now(F.KST).strftime("%H:%M"),
                                   "kw": kw, **F.post_meta(kw, pick.get("type", ""))})
    print(f"제작 완료 → {post}")
    return post


# ---------------------------------------------------------------- 사진 (대표 결정: AI 실사풍 먼저, 안 되면 무료 사진)

def image(spec: dict, out: Path, size: str, credits: list[str], used: set, tier: str = "high") -> str | None:
    """경제 사진 (대표 결정 2026-10-06): 글 맨 앞 2장(썸네일·본문 첫 장)은 고화질 AI, 나머지는 무료 사진만.
    회사가 나오면 진짜 간판·로고가 보이게(같은 날 "삼성전자인데 동네 창고처럼"), 위키미디어 실제 사진은 비상용."""
    if NO_AUTO_PHOTOS:  # 본문 사진은 프롬프트만, 자동으로 구하지 않음 (대표 결정 2026-10-08: 엉뚱한 무료 사진·위키미디어 동명 사진 문제)
        return None
    brand, real = spec.get("brand", "").strip(), spec.get("real_query", "").strip()
    if tier == "high" and ai_photo(spec["prompt"], out, size, brand, quality=BRAND_QUALITY):
        credits.append(f"{out.name}: AI 생성(GPT Image, 고화질) — {spec['alt']}")
        return out.name
    if tier == "free":  # 무료 사진 먼저
        got = pexels(spec["stock_query"], out.with_suffix(".jpg"), size, used)
        if got:
            credits.append(f"{out.with_suffix('.jpg').name}: Pexels · {got} — {spec['alt']}")
            return out.with_suffix(".jpg").name
    if brand and real:
        from .celeb import commons
        got = commons(real, "", out.with_suffix(""), used, must=[w for w in re.split(r"\s+", brand) if len(w) > 2][:2])
        if got:
            if size == "1024x1024":  # 썸네일은 정사각형으로 가운데 자르기
                from PIL import Image
                f = out.with_suffix(".jpg")
                im = Image.open(f).convert("RGB")
                w, h = im.size
                c = min(w, h)
                im.crop(((w - c) // 2, (h - c) // 2, (w + c) // 2, (h + c) // 2)).save(f, quality=92)
            credits.append(f"{got[0]}: 실제 사진 · {got[1]} — {spec['alt']} (CC BY·BY-SA는 사진 아래 작가·라이선스 표시)")
            return got[0]
    if tier == "high":
        got = pexels(spec["stock_query"], out.with_suffix(".jpg"), size, used)
        if got:
            credits.append(f"{out.with_suffix('.jpg').name}: Pexels · {got} — {spec['alt']}")
            return out.with_suffix(".jpg").name
    credits.append(f"{out.name}: ⚠️ 사진 못 구함 — {spec['alt']}")
    return None


NO_CREDIT = []  # OpenAI 크레딧이 떨어지면 표시 (2026-10-06: 모르는 사이 Pexels로만 채워진 일이 있어 발행 패키지에 경고)


def photo_prompt(desc: str, size: str, brand: str = "", lead: str = "") -> str:
    """사진 한 장을 그릴 영어 설명 전체. API에도, 도우미의 'ChatGPT·제미나이에 붙여넣기'에도 같은 글을 쓴다 (2026-10-06)."""
    shape = "Square 1:1 image. " if size == "1024x1024" else "Landscape 3:2 image. "
    # 경제 마스터 §10 원문(실제 기업·기관·현장·공식 통계 이미지, 본문과 정확히 일치, 장식용 금지)에 맞춤 (대표 지시 2026-10-10)
    return (shape + (lead or "Realistic documentary photograph of the real subject exactly as it looks in real life — "
                             "the actual company building, product, trading floor, official chart or news scene described. "
                             "True to the article, natural light, sharp focus. No decorative, staged or fictional elements. ")
            + desc + (  # 회사 사진은 그 회사의 실제 간판·로고가 보이게 (대표 지시 2026-10-06)
                f" This must clearly be {brand}: show its real, accurate corporate signage — the actual "
                f"{brand} logo and company name exactly as they appear on its real buildings, correctly spelled. "
                "No other readable text. No identifiable real person's face, no watermark, no charts."
                if brand else
                " No identifiable real person's face, no logos, no brand marks, no readable text, "
                "letters or numbers anywhere, no watermark, no charts."))


def ai_photo(desc: str, out: Path, size: str, brand: str = "", quality: str = "", lead: str = "") -> bool:
    """quality·lead: 패션은 고화질·잡지 정물 구도로 (대표 지시 2026-10-06 "패션은 사진에 힘주고")."""
    if not AI_IMAGES or not F.key("OPENAI_API_KEY") or NO_CREDIT:
        return False
    r = requests.post("https://api.openai.com/v1/images/generations", timeout=600,
                      headers={"Authorization": f"Bearer {F.key('OPENAI_API_KEY')}"},
                      json={"model": "gpt-image-2", "n": 1, "size": size,
                            "quality": quality or (BRAND_QUALITY if brand else IMG_QUALITY),
                            "prompt": photo_prompt(desc, size, brand, lead)})
    if r.status_code != 200:
        print(f"AI 사진 실패 HTTP {r.status_code}: {r.text[:160]}")
        if r.status_code == 429 and "credit" in r.text.lower():
            NO_CREDIT.append(True)
        return False
    # 어림 단가: gpt-image-2 (2026-09 공개 가격 정리 기준, 2026-10-06 고침): high 정사각 $0.211·가로 $0.165, medium 정사각 $0.053·가로 $0.041
    if brand or quality == "high":
        F.SPENT["image"] += 0.211 if size == "1024x1024" else 0.165
    else:
        F.SPENT["image"] += 0.053 if size == "1024x1024" else 0.041
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
