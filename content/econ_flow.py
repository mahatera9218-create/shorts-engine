"""억선생의 경제판 하루 흐름 (대표 결정 2026-10-05): 키워드 → (대표 선택) → 제목 후보 → (대표 선택) → 전체 제작.

1단계 keywords : 코드(시세 변동) + Grok(X·웹 자체 조사) + 대표가 넣은 키워드(어드바이저·뉴스 랭킹·트렌드) → 후보 목록
2단계 titles   : 대표가 고른 키워드 → Claude 웹 검색 취재 메모 + Grok 오늘의 말투 → Claude 제목 10개 → GPT 독자 순위
                 → 코드 검사(33~45자 등) → 대표가 고름
3단계 produce  : 고른 제목으로 글(Claude) → GPT 사실 대조 → Claude 고치기 → 썸네일(인물이면 상반신 캐리커처, 아니면 창고 그림)
                 + 본문 그림(창고) + 쇼츠 대본 → econ/posts/<날짜-주제>/ (발행 도우미)
모든 단계의 결과는 econ/flow/<날짜>/ 에 남고, 발행 도우미(content/econ_desk.py)가 보여 준다. 키는 GitHub Secrets에서만.

사용법: python -m content.econ_flow keywords
        python -m content.econ_flow add "키워드1\n키워드2"
        python -m content.econ_flow titles "금값 급락"
        python -m content.econ_flow produce <주제폴더> <제목번호>
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

from market.common import ROOT

KST = ZoneInfo("Asia/Seoul")
FLOW = ROOT / "econ" / "flow"
POSTS = ROOT / "econ" / "posts"
LIB = ROOT / "assets" / "art-library"
SKILLS = ROOT / ".claude" / "skills"
AREAS = ["국내주식", "미국주식", "금", "비트코인", "돈굴리기", "거시·환율"]


def key(n: str) -> str:
    return os.environ.get(n, "").strip()


def today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def topic_slug(kw: str) -> str:
    return f"{today()}-" + (re.sub(r"[^0-9A-Za-z가-힣]+", "-", kw).strip("-")[:24] or "주제")


def parse_json(text: str):
    """AI 답에서 첫 JSON 덩어리를 꺼낸다."""
    m = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.S) or re.search(r"([\[{].*[\]}])", text, re.S)
    return json.loads(m.group(1)) if m else None


def load(p: Path, default=None):
    return (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or default


def save(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


# ---------------------------------------------------------------- AI 부르기

def _pick(models: list[str], prefer: list[str], must: str) -> str:
    for p in prefer:
        if p in models:
            return p
    ok = [m for m in models if must in m and not any(x in m for x in ("image", "vision", "audio", "tts", "realtime",
                                                                         "embed", "mini", "nano", "transcribe"))]
    return sorted(ok)[-1] if ok else models[0]


def _resp_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]
    out = []
    for item in data.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text") and c.get("text"):
                out.append(c["text"])
    return "\n".join(out)


def grok(prompt: str) -> str:
    """Grok: X 검색 + 웹 검색 (Responses API). 실패하면 빈 문자열."""
    if not key("XAI_API_KEY"):
        return ""
    h = {"Authorization": f"Bearer {key('XAI_API_KEY')}"}
    try:
        ids = [m["id"] for m in requests.get("https://api.x.ai/v1/models", headers=h, timeout=30).json()["data"]]
        model = _pick(ids, ["grok-4.6", "grok-4.5", "grok-4.3"], "grok")
        r = requests.post("https://api.x.ai/v1/responses", headers=h, timeout=300, json={
            "model": model, "input": prompt, "tools": [{"type": "x_search"}, {"type": "web_search"}]})
        r.raise_for_status()
        return _resp_text(r.json())
    except Exception as e:  # Grok이 안 되면 그 몫만 빼고 계속
        print(f"Grok 실패: {type(e).__name__} {str(e)[:150]}")
        return ""


def gpt(prompt: str, search: bool = False) -> str:
    """GPT: 다른 회사의 눈(독자 순위·사실 대조). search=True면 웹 검색."""
    if not key("OPENAI_API_KEY"):
        return ""
    h = {"Authorization": f"Bearer {key('OPENAI_API_KEY')}"}
    try:
        ids = [m["id"] for m in requests.get("https://api.openai.com/v1/models", headers=h, timeout=30).json()["data"]]
        model = _pick(ids, ["gpt-5.5", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1"], "gpt-")
        body = {"model": model, "input": prompt}
        if search:
            body["tools"] = [{"type": "web_search"}]
        r = requests.post("https://api.openai.com/v1/responses", headers=h, json=body, timeout=300)
        r.raise_for_status()
        return _resp_text(r.json())
    except Exception as e:
        print(f"GPT 실패: {type(e).__name__} {str(e)[:150]}")
        return ""


def claude_research(topic: str) -> str:
    """Claude 웹 검색으로 출처 달린 취재 메모 (Perplexity 대신, 2026-10-05)."""
    import anthropic
    c = anthropic.Anthropic()
    msg = c.messages.create(
        model="claude-sonnet-5-5", max_tokens=4000,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": (
            f"오늘은 {today()}(한국 시간)입니다. 경제 블로그 글을 쓰기 위한 취재 메모를 만들어 주세요. 주제: {topic}\n"
            "주요 언론사·공식 기관(한국은행·연준·거래소·기업 공시 등) 출처만 쓰세요. 아래 순서로 짧게:\n"
            "1) 지금 무슨 일이 있었나 (사실, 날짜·시각 포함) 2) 핵심 숫자 (기준 시각과 출처) 3) 왜 그런가 (배경)\n"
            "4) 기관·증권사 전망 (누가 무엇을, 출처) 5) 앞으로 일정 6) 관련 인물(회사 + 이름, 직책)\n"
            "맨 끝에 '출처:' 아래 기사 제목과 URL 목록. 모르는 건 모른다고 쓰고 지어내지 마세요.")}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def claude_json(system: list[str], prompt: str, schema: dict, stage: str) -> dict:
    from .llm import Claude
    return Claude().ask_json(system, prompt, schema, stage=stage, max_tokens=12000)


# ---------------------------------------------------------------- 1단계: 키워드

def price_moves() -> list[dict]:
    out = []
    try:
        for t in requests.get("https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH", timeout=20).json():
            pct = t["signed_change_rate"] * 100
            if abs(pct) >= 3:
                name = {"KRW-BTC": "비트코인", "KRW-ETH": "이더리움"}[t["market"]]
                out.append({"kw": f"{name} {pct:+.1f}%", "area": "비트코인", "src": "코드(업비트 24시간)",
                            "why": f"24시간 {pct:+.1f}% 움직임"})
    except Exception as e:
        print(f"업비트 실패: {e}")
    return out


def keywords() -> Path:
    day = FLOW / today()
    items = price_moves()
    g = grok(f"오늘은 {today()}(한국 시간)입니다. 지금 X(트위터)와 웹에서 한국 개인 투자자들이 가장 많이 이야기하는 "
             "경제·투자 화제 8개를 찾아 주세요. 분야는 국내주식·미국주식·금·비트코인·돈굴리기(예적금·ISA 등)·거시·환율. "
             "한 종목에 몰리지 않게, 실제로 오늘 화제인 것만. 작전주·테마주 추천·리딩방은 빼세요. "
             'JSON 배열만 답하세요: [{"kw": "짧은 키워드", "area": "분야", "why": "왜 화제인지 한 줄", '
             '"person": "관련 인물이 있으면 회사+이름(예: 삼성 이재용), 없으면 빈칸"}]')
    for it in parse_json(g) or []:
        if isinstance(it, dict) and it.get("kw"):
            items.append({"kw": it["kw"], "area": it.get("area", ""), "src": "Grok(X·웹)", "why": it.get("why", ""),
                          "person": it.get("person", "")})
    old = load(day / "keywords.yaml", {"items": []})
    mine = [x for x in old.get("items", []) if x.get("src") == "대표"]
    save(day / "keywords.yaml", {"date": today(), "updated": datetime.now(KST).strftime("%H:%M"), "items": mine + items})
    print(f"키워드 {len(mine) + len(items)}개 (대표 {len(mine)} · Grok/코드 {len(items)})")
    return day / "keywords.yaml"


def add(text: str) -> None:
    """대표가 넣은 키워드 (도우미 입력칸 → 이슈 본문). 한 줄에 하나 또는 쉼표로."""
    day = FLOW / today()
    data = load(day / "keywords.yaml", {"date": today(), "items": []})
    have = {x["kw"] for x in data["items"]}
    for kw in [k.strip(" -•\t") for k in re.split(r"[\n,]", text) if k.strip(" -•\t")]:
        if kw not in have and len(kw) <= 40:
            data["items"].insert(0, {"kw": kw, "area": "", "src": "대표", "why": "대표가 조사해 넣음"})
    save(day / "keywords.yaml", data)


# ---------------------------------------------------------------- 2단계: 제목 후보 (후킹 로직)

TITLE_RULES = """제목 공식 (억선생의 경제판, 홈판 + 검색):
- 33~45자. 첫 15자 안에 검색 키워드와 멈출 요소(숫자·인물·대조)를 둔다.
- 질문형 + 강한 사실 1개(숫자) + 긴장 1개(시간차·반전·통념 뒤집기·사건) + 빈칸 1개(본문 첫 2~3줄에서 회수).
- 인물이 주인공이면 '회사 + 이름'을 앞에 (예: 삼성 이재용, 엔비디아 젠슨황).
- 금지: 과장어(역대급·충격·폭망), 낚시(본문에 없는 약속), 투자 권유(사라·팔아라·지금 담아야), 도박 말(판돈·올인), 단정 전망.
- 숫자·사실은 취재 메모에 있는 것만."""


def titles(kw: str) -> Path:
    d = FLOW / today() / topic_slug(kw)
    d.mkdir(parents=True, exist_ok=True)
    memo = claude_research(kw)
    (d / "research.md").write_text(f"# 취재 메모: {kw}\n\n{memo}\n", encoding="utf-8")
    vibe = grok(f"X(트위터)에서 오늘 '{kw}' 이야기를 하는 한국 투자자들이 실제로 쓰는 표현·단어·분위기를 "
                "5줄로 요약해 주세요(욕설·혐오 표현 빼고). 사실 확인이 안 된 소문은 '소문'이라고 표시.")
    people = load(ROOT / "config" / "people.yaml", {"people": []})["people"]
    schema = {"type": "object", "additionalProperties": False, "required": ["titles", "person"],
              "properties": {
                  "person": {"type": "string", "description": "주인공 인물 '회사 이름'(예: 삼성 이재용). 없으면 빈칸"},
                  "titles": {"type": "array", "items": {
                      "type": "object", "additionalProperties": False,
                      "required": ["title", "type", "promise", "badge"],
                      "properties": {"title": {"type": "string"}, "type": {"type": "string"},
                                     "promise": {"type": "string", "description": "본문 첫 2~3줄에서 회수할 답 한 줄"},
                                     "badge": {"type": "string", "description": "썸네일에 얹을 핵심 2~8자 (인물이면 회사+이름, 아니면 숫자·대상)"}}}}}}
    out = claude_json([TITLE_RULES], (
        f"키워드: {kw}\n\n[취재 메모]\n{memo[:6000]}\n\n[X 분위기 (Grok)]\n{vibe[:1500] or '없음'}\n\n"
        f"[인물 표기 목록]\n{', '.join(p['tag'] for p in people)}\n\n"
        "위 공식으로 서로 다른 각도의 제목 10개를 만들어 주세요. type은 질문형·숫자형·대비형·반전형·인물형 중 하나."),
        schema, stage="제목")
    items = out["titles"][:10]
    # GPT: 경제 초보 독자 눈으로 누를 것 같은 순 3개 (다른 회사의 눈)
    listing = "\n".join(f"{i + 1}. {t['title']}" for i, t in enumerate(items))
    rank = parse_json(gpt("당신은 네이버 홈 피드를 훑는 30~40대 경제 초보 독자입니다. 아래 제목 중 가장 누르고 싶은 순서로 "
                          "3개를 고르고, 과장·낚시로 느껴지는 번호도 알려 주세요. JSON만: "
                          '{"top": [번호, 번호, 번호], "bait": [번호...], "why": "한 줄"}\n\n' + listing)) or {}
    top = [i - 1 for i in rank.get("top", []) if isinstance(i, int) and 1 <= i <= len(items)]
    bait = {i - 1 for i in rank.get("bait", []) if isinstance(i, int)}
    for i, t in enumerate(items):  # 코드 검사
        n = len(t["title"])
        t["chars"] = n
        t["flags"] = ([f"{n}자(33~45자 밖)"] if not 33 <= n <= 45 else []) + (["GPT: 낚시 느낌"] if i in bait else [])
        t["rank"] = top.index(i) + 1 if i in top else None
    items.sort(key=lambda t: (bool(t["flags"]), t["rank"] or 99))  # 경고(글자 수·낚시) 있는 제목은 뒤로
    save(d / "titles.yaml", {"keyword": kw, "person": out.get("person", ""), "gpt_why": rank.get("why", ""),
                             "items": items})
    print(f"제목 {len(items)}개 → {d}")
    return d


# ---------------------------------------------------------------- 3단계: 전체 제작

def skill(name: str) -> str:
    f = SKILLS / name / "SKILL.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


WRITE_RULES = """억선생의 경제판 글 규칙 (DECISIONS 2026-10-04~05):
- 제목의 질문에 본문 첫 2~3줄에서 바로 답한다.
- 순서: 답 → 오늘 숫자(기준 시각·출처) → 왜(배경) → 기관·증권사 전망(누가, 출처) → 앞으로 일정 → 글쓴이 생각(권유 없음) → 면책 한 줄.
- 기사는 소스로만 참고하고 새로 쓴다. 남의 문장 옮기지 않는다. 숫자는 취재 메모에 있는 것만.
- 가짜 경험('제가 투자해 보니') 금지, 투자 권유 금지, 단정 전망 금지, 도박 말 금지.
- 말투: 상위 경제 블로거처럼 쉽고 담백하게. 문단은 2~4문장. 소제목은 질문형.
- 그림 자리는 코드가 넣으니 '[그림 1]' 같은 자리표를 쓰지 않는다.
- 분량 1,500~2,500자. 끝에 '※ 이 글은 경제 공부를 위한 정보이며 투자 권유가 아닙니다. 본문 그림은 AI로 만들었습니다.'"""

ARTICLE = {"type": "object", "additionalProperties": False,
           "required": ["paragraphs", "tags", "image_tags", "short", "sources", "area"],
           "properties": {
               "area": {"type": "string", "enum": AREAS},
               "paragraphs": {"type": "array", "items": {"type": "string"}},
               "tags": {"type": "array", "items": {"type": "string"}},
               "image_tags": {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                              "description": "본문 그림 3장 자리마다 어울리는 창고 태그 2~3개 (예: [급락, 하락])"},
               "short": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["cap", "say"],
                                                    "properties": {"cap": {"type": "string"}, "say": {"type": "string"}}},
                         "description": "쇼츠 6장면: 자막(10자 안팎)·대사(한 문장, 짧게)"},
               "sources": {"type": "array", "items": {"type": "string"}}}}


def produce(slug: str, n: int) -> Path:
    tdir = next(FLOW.glob(f"*/{slug}"), None)
    if not tdir:
        raise SystemExit(f"주제 폴더 없음: {slug}")
    T = load(tdir / "titles.yaml")
    pick = T["items"][n - 1]
    memo = (tdir / "research.md").read_text(encoding="utf-8")
    lib_tags = sorted({t for s in load(ROOT / "config" / "art_library.yaml")["scenes"] for t in s["tags"]})
    sys_prompt = [skill("money-content-writer"), skill("blog-voice"), WRITE_RULES]
    art = claude_json(sys_prompt, (
        f"제목: {pick['title']}\n본문 첫 2~3줄에서 회수할 답: {pick['promise']}\n주인공 인물: {T.get('person') or '없음'}\n\n"
        f"[취재 메모]\n{memo[:9000]}\n\n창고 그림 태그 목록: {', '.join(lib_tags)}\n위 규칙으로 글을 써 주세요."),
        ARTICLE, stage="글쓰기")
    body = "\n\n".join(art["paragraphs"])
    check = gpt("아래 경제 블로그 초안의 숫자·날짜·기관 전망·인물 직책이 사실인지 웹 검색으로 확인하세요. "
                "주요 언론사·공식 기관 출처만 인정합니다. 틀리거나 확인 안 되는 것만 JSON으로: "
                '{"issues": [{"claim": "초안 문장", "problem": "무엇이 틀렸나", "fix": "고칠 내용(출처)"}]}. 문제가 없으면 '
                '{"issues": []}\n\n' + body, search=True)
    issues = (parse_json(check) or {}).get("issues", [])
    if issues:
        art = claude_json(sys_prompt, (
            f"아래 초안을 사실 대조 결과대로 고쳐 주세요. 확인 안 되는 문장은 빼거나 '~로 알려졌다'가 아니라 출처를 밝혀 쓰세요.\n\n"
            f"[초안]\n{body}\n\n[사실 대조 (GPT)]\n{json.dumps(issues, ensure_ascii=False)}\n\n[취재 메모]\n{memo[:6000]}"),
            ARTICLE, stage="고쳐쓰기")
    post = POSTS / slug
    post.mkdir(parents=True, exist_ok=True)
    # 그림: 썸네일 + 본문 창고 그림 3장
    from .art_library import pick as lib_pick
    used: list[str] = []
    files = []
    for tags in art["image_tags"][:3]:
        got = lib_pick(tags, used, 1)
        if got:
            used.append(got[0])
            shutil.copy(LIB / f"{got[0]}.jpg", post / f"{got[0]}.jpg")
            files.append(got[0])
    thumb_note = make_thumb(post, T.get("person", ""), pick["badge"], used)
    # 본문: 첫 2문단 뒤, 중간, 끝 앞에 그림
    paras = [x for x in art["paragraphs"] if not re.fullmatch(r"\s*\[(그림|사진|이미지)\s*\d*\]\s*", x)]  # AI가 넣은 그림 자리표 제거
    slots = [2, max(3, len(paras) // 2), max(4, len(paras) - 2)]
    lines = ["[이미지 1_썸네일: thumb.png]"]
    for i, p in enumerate(paras):
        lines.append(p)
        for k, s in enumerate(slots):
            if i + 1 == s and k < len(files):
                lines.append(f"[이미지 {k + 2}_{files[k]}: {files[k]}.jpg]")
    (post / "body.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    alts = [t for t in T["items"] if t is not pick][:2]
    tags = ",".join(art["tags"][:12] + ["억선생", "억선생의경제판"])
    (post / "post.md").write_text("\n".join([
        f"# 발행 패키지 · {T['keyword']}", "",
        f"**상태:** {'✅ 사실 대조 통과' if not issues else '✅ 사실 대조 후 고침(' + str(len(issues)) + '곳)'}",
        f"**썸네일:** {thumb_note}", "", f"- 카테고리: **{art['area']}**", f"- 태그: {tags}", "",
        "## 제목 (추천 ★)", "", f"1. ★ {pick['title']} — {pick['type']}",
        *[f"{i + 2}. {t['title']} — {t['type']}" for i, t in enumerate(alts)], "",
        "## 본문", "", "(body.txt)", "", "## 출처", "", *[f"- {s}" for s in art["sources"]],
        "", "## 사실 대조 (GPT)", "", *([f"- {x.get('claim', '')} → {x.get('fix', '')}" for x in issues] or ["- 문제 없음"])]),
        encoding="utf-8")
    short_lines = [f"{s['cap']} | {s['say']}" for s in art["short"]]
    (post / "short-script.txt").write_text("\n".join(short_lines) + "\n", encoding="utf-8")
    (post / "short.txt").write_text(
        f"{pick['title'][:40]}\n{pick['promise']}\nAI 그림·AI 음성으로 만들었어요. 투자 권유가 아닙니다.\n"
        + " ".join("#" + t.replace(" ", "") for t in art["tags"][:5]) + " #억선생\n", encoding="utf-8")
    save(tdir / "chosen.yaml", {"title": pick["title"], "post": slug, "at": datetime.now(KST).strftime("%H:%M")})
    print(f"제작 완료 → {post}")
    return post


# ---------------------------------------------------------------- 썸네일

FONT = ROOT / "assets" / "fonts" / "Pretendard-Black.otf"


def make_thumb(post: Path, person: str, badge: str, used: list[str]) -> str:
    """인물이면 얼굴·상반신 캐리커처를 크게(Gemini) + 이름 배지, 아니면 창고 그림 + 핵심 배지 (대표 결정 2026-10-05)."""
    from .hook_thumb import RED, PAPER, INK, GOLD, _seal, _cover
    people = {p["tag"]: p for p in load(ROOT / "config" / "people.yaml", {"people": []})["people"]}
    p = people.get(person.strip())
    W = 1080
    if p and key("GEMINI_API_KEY"):
        bust = gemini_bust(p["en"])
        if bust:
            c = Image.new("RGB", (W, W), PAPER)
            bg = _cover(Image.open(LIB / f"{(used or ['market-morning'])[0]}.jpg").convert("RGB"), W, W, 0.5)
            c = Image.blend(c, bg, 0.35)
            bust.thumbnail((int(W * 0.95), int(W * 0.95)))
            c.paste(bust, ((W - bust.width) // 2 + 60, W - bust.height), bust)
            draw_badge(c, person or badge)
            ImageDraw.Draw(c).text((W - 220, W - 56), "AI 일러스트", font=ImageFont.truetype(str(FONT), 32),
                                   fill=PAPER, stroke_width=4, stroke_fill=INK)
            _seal(c, 40, W - 150, 110, RED, PAPER)
            c.save(post / "thumb.png")
            return f"인물 상반신({person}, Gemini 캐리커처) + 배지"
    from .art_library import pick as lib_pick
    art = (used or lib_pick([badge], [], 1) or ["market-morning"])[0]
    c = _cover(Image.open(LIB / f"{art}.jpg").convert("RGB"), W, W, 0.5)
    draw_badge(c, badge)
    _seal(c, W - 150, W - 150, 110, RED, PAPER)
    c.save(post / "thumb.png")
    return f"창고 그림({art}) + 배지"


def draw_badge(c: Image.Image, text: str) -> None:
    from .hook_thumb import INK, GOLD
    d = ImageDraw.Draw(c)
    size = 130
    while size > 60 and d.textlength(text, font=ImageFont.truetype(str(FONT), size)) > c.width - 160:
        size -= 4
    f = ImageFont.truetype(str(FONT), size)
    w = d.textlength(text, font=f)
    d.rounded_rectangle((40, 40, 40 + w + 64, 40 + size + 48), radius=26, fill=INK)
    d.text((72, 52), text, font=f, fill=GOLD)


def gemini_bust(en: str) -> Image.Image | None:
    """인물 얼굴·상반신 캐리커처 (조선 화풍, 초록 화면 → 오려냄). 규칙: 사진 아님·중립/긍정 표정·글자·로고 없음."""
    from .head_swap import gemini_edit  # 같은 Gemini 호출 재사용 (참고 그림 = 억선생 그림체)
    from .motion_short import unscreen
    ref = (ROOT / "reports" / "쇼츠-시안" / "금값-출렁" / "parts" / "hero_happy-green.png").read_bytes()
    prompt = ("Using the attached image only as the painting-style reference, draw a NEW picture: a head-and-upper-body "
              f"portrait (face and chest only, large, filling the frame) of {en}, as a hand-painted Joseon-era "
              "caricature in the same ink-and-wash style, wearing a black gat hat and an indigo hanbok jeogori, "
              "friendly confident smile, looking at the viewer. Clearly an illustration with visible brush lines, "
              "not a photo. Flat pure green background (#00FF00). No text, no logos.")
    data, who = gemini_edit(ref, prompt)
    if not data:
        print(f"상반신 실패: {who}")
        return None
    tmp = ROOT / ".cache" / "bust.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(data)).convert("RGB").save(tmp)
    unscreen(tmp)
    im = Image.open(tmp).convert("RGBA")
    return im.crop(im.getbbox())


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "keywords"
    if cmd == "keywords":
        keywords()
    elif cmd == "add":
        add(sys.argv[2])
    elif cmd == "titles":
        titles(sys.argv[2])
    elif cmd == "produce":
        produce(sys.argv[2], int(sys.argv[3]))
    else:
        raise SystemExit(f"모르는 명령: {cmd}")


if __name__ == "__main__":
    main()
