"""억선생의 경제판 하루 흐름 (대표 결정 2026-10-05): 키워드 → (대표 선택) → 제목 후보 → (대표 선택) → 전체 제작.

1단계 keywords : 코드(시세 변동) + Grok(X·웹 자체 조사) + 대표가 넣은 키워드(어드바이저·뉴스 랭킹·트렌드) → 후보 목록
2단계 titles   : 대표가 고른 키워드 → Claude 웹 검색 취재 메모 + Grok 오늘의 말투 → Claude 제목 10개
                 → 코드 검사(33~45자) → 대표가 고름 (마음에 안 들면 '다시 뽑기' = 다시 취재부터)
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
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

from market.common import ROOT

KST = ZoneInfo("Asia/Seoul")
from .blogs import get as _blog  # 경제·연예·패션 중 지금 블로그 (환경 변수 BLOG, 2026-10-05)
BLOG = _blog()
FLOW = BLOG["base"] / "flow"
POSTS = BLOG["base"] / "posts"
LIB = ROOT / "assets" / "art-library"
SKILLS = ROOT / ".claude" / "skills"
AREAS = ["국내주식", "미국주식", "금", "비트코인", "돈굴리기", "거시·환율"]


# ---------------------------------------------------------------- 비용 (대표 결정 2026-10-05: 기록해서 성과 분석에 쓰고, 월 5만원 상한)
COSTS = ROOT / "econ" / "costs.csv"
KRW = 1400            # 1달러 어림 환율 (보고용)
MONTH_CAP_KRW = 220000  # 월 상한: 넘으면 새 작업을 멈춘다 (대표 결정 2026-10-06: 초반엔 달린다, 하루 최소 경제 2·패션 2 → 약 20만 + 여유)
COST_FROM = "2026-10-06"  # 비용 다시 세기 시작한 날 (대표 지시 2026-10-06 "오늘 기점으로 다시 카운트"). 그 전 줄은 기록으로만 남김
SPENT = {"claude": 0.0, "gpt": 0.0, "grok": 0.0, "image": 0.0}  # 이번 실행에서 쓴 달러 (추정 포함)


def month_spent_krw(month: str | None = None) -> int:
    import csv
    month = month or today()[:7]
    if not COSTS.exists():
        return 0
    with COSTS.open(encoding="utf-8") as f:
        return int(sum(float(r["total_usd"]) for r in csv.DictReader(f) if r["date"].startswith(month) and r["date"] >= COST_FROM) * KRW)


def guard() -> None:
    used = month_spent_krw()
    if used >= MONTH_CAP_KRW:
        raise SystemExit(f"이번 달 AI 비용이 {used:,}원으로 상한 {MONTH_CAP_KRW:,}원에 닿아 멈춥니다. 대표에게 알려 주세요.")


def log_cost(cmd: str, item: str) -> None:
    import csv
    new = not COSTS.exists()
    COSTS.parent.mkdir(parents=True, exist_ok=True)
    if not new and not COSTS.read_text(encoding="utf-8").split("\n", 1)[0].endswith(",blog"):  # 옛 머리줄에 blog 칸 더하기 (없으면 성과 탭이 다 경제로 셈)
        head, _, rest = COSTS.read_text(encoding="utf-8").partition("\n")
        COSTS.write_text(head.rstrip() + ",blog\n" + rest, encoding="utf-8")
    with COSTS.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "cmd", "item", "claude_usd", "gpt_usd", "grok_usd", "image_usd", "total_usd", "blog"])
        w.writerow([today(), datetime.now(KST).strftime("%H:%M"), cmd, item[:40]]
                   + [f"{SPENT[k]:.4f}" for k in ("claude", "gpt", "grok", "image")] + [f"{sum(SPENT.values()):.4f}", BLOG["id"]])


def _usage_cost(u: dict, inp: float, out: float) -> float:
    """토큰 사용량(달러/100만 토큰 어림값)으로 비용 추정."""
    return ((u.get("input_tokens") or 0) * inp + (u.get("output_tokens") or 0) * out) / 1_000_000


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


GROK_PRICE = {"grok-4.3": (1.25, 2.5), "grok-4.5": (2.0, 6.0), "grok-4.6": (2.0, 6.0)}  # 달러/100만 토큰 (2026-08 공개 단가)


def grok(prompt: str, days: int = 1, web: bool = False, turns: int = 2) -> str:
    """Grok: X 검색(+web=True면 웹 검색) (Responses API). 실패하면 빈 문자열.
    비용 줄이기 (대표 지시 2026-10-05): 싼 모델(grok-4.3) 우선 · 최근 days일만 · 생각 턴 turns번까지.
    키워드 모으기는 X만(웹 기사는 RSS로 따로), 글 조사(쿠니네 방식)는 웹 + X."""
    if not key("XAI_API_KEY"):
        return ""
    h = {"Authorization": f"Bearer {key('XAI_API_KEY')}"}
    since = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        ids = [m["id"] for m in requests.get("https://api.x.ai/v1/models", headers=h, timeout=30).json()["data"]]
        model = _pick(ids, ["grok-4.3", "grok-4.5", "grok-4.6"], "grok")
        tools = [{"type": "x_search", "from_date": since}] + ([{"type": "web_search"}] if web else [])
        body = {"model": model, "input": prompt, "max_turns": turns, "tools": tools}
        r = requests.post("https://api.x.ai/v1/responses", headers=h, timeout=600, json=body)
        if r.status_code == 400:  # 이 모델·주소가 max_turns를 안 받으면 빼고 한 번 더
            body.pop("max_turns")
            r = requests.post("https://api.x.ai/v1/responses", headers=h, timeout=600, json=body)
        r.raise_for_status()
        data = r.json()
        calls = sum(1 for it in data.get("output", []) if str(it.get("type", "")).endswith("_call"))
        inp, out = GROK_PRICE.get(model, (2.0, 6.0))
        u = data.get("usage") or {}
        SPENT["grok"] += _usage_cost(u, inp, out) + calls * 0.005  # 토큰 + 검색 1번 $0.005
        print(f"Grok {model}: 검색 {calls}번, 토큰 {u.get('input_tokens')}/{u.get('output_tokens')}")
        return _resp_text(data)
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
        data = r.json()
        calls = sum(1 for it in data.get("output", []) if it.get("type") == "web_search_call")
        SPENT["gpt"] += _usage_cost(data.get("usage") or {}, 2.5, 10.0) + calls * 0.01  # 어림: 토큰 + 검색 1번 $0.01
        return _resp_text(data)
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
    u = msg.usage
    searches = getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
    SPENT["claude"] += (u.input_tokens * 2.0 + u.output_tokens * 10.0) / 1_000_000 + searches * 0.01
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def claude_json(system: list[str], prompt: str, schema: dict, stage: str) -> dict:
    from .llm import Claude
    c = Claude()
    out = c.ask_json(system, prompt, schema, stage=stage, max_tokens=12000)
    SPENT["claude"] += c.cost_usd()
    return out


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
    """여러 출처에서 모아 묶고 점수를 매긴다 (대표 지시 2026-10-05: Grok만 믿지 말고 겹치면 우선). content/econ_score.py"""
    from .econ_score import run
    day = FLOW / today()
    from .econ_score import CFG as _kcfg
    topic = (load(_kcfg(), {}) or {}).get("grok_topic") or (
        "한국 개인 투자자들이 가장 많이 이야기하는 경제·투자 화제. 분야는 국내주식·미국주식·금·비트코인·돈굴리기(예적금·ISA 등)·거시·환율. "
        "한 종목에 몰리지 않게, 작전주·테마주 추천·리딩방은 빼세요")
    n_g = (load(_kcfg(), {}) or {}).get("grok_count", 8)  # 패션은 15개 (2026-10-06 대표 지적: 패션 키워드가 약함)
    g = grok(f"오늘은 {today()}(한국 시간)입니다. 지금 X(트위터)에서 {topic}. 실제로 오늘 화제인 것 {n_g}개만. "
             'JSON 배열만 답하세요: [{"kw": "짧은 키워드", "area": "분야", "why": "왜 화제인지 한 줄", '
             '"person": "관련 인물이 있으면 이름(회사·소속), 없으면 빈칸"}]')
    grok_items = [it for it in (parse_json(g) or []) if isinstance(it, dict) and it.get("kw")]
    old = load(day / "keywords.yaml", {"items": []})
    mine = [x for x in old.get("items", []) if x.get("src") in ("대표", "캡처")]
    items = run(grok_items, mine)
    save(day / "keywords.yaml", {"date": today(), "updated": datetime.now(KST).strftime("%H:%M"), "items": items})
    print(f"키워드 {len(items)}개, 1위 {items[0]['kw']} {items[0]['score']}점" if items else "키워드 없음")
    return day / "keywords.yaml"


def add(text: str) -> None:
    """대표가 넣은 키워드 (도우미 입력칸 → 이슈 본문). 한 줄에 하나 또는 쉼표로."""
    day = FLOW / today()
    data = load(day / "keywords.yaml", {"date": today(), "items": []})
    have = {x["kw"] for x in data["items"]}
    new = []
    for kw in [k.strip(" -•\t") for k in re.split(r"[\n,]", text) if k.strip(" -•\t")]:
        if kw not in have and len(kw) <= 40:
            new.append({"kw": kw, "area": "", "src": "대표", "why": "대표가 조사해 넣음", "rows": ["D1"]})
    if new:  # 검색량·뉴스량 점수는 바로 매긴다 (AI 비용 없음). 다음 '다시 모으기' 때 다른 출처와 겹치면 더 오름
        from .econ_score import score
        data["items"] = sorted(score(new, {"D1": "대표"}) + data["items"], key=lambda x: -x.get("score", 0))
    save(day / "keywords.yaml", data)


# ---------------------------------------------------------------- 2단계: 제목 후보 (후킹 로직)

TITLE_RULES = """제목 공식 (억선생의 경제판, 홈판 + 검색. 2026-10-05 강사 프롬프트 반영):
- 공백 포함 45자 이내(33~45자 권장). 핵심키워드를 반드시 넣고, 가능하면 제목 앞부분에. 첫 15자 안에 멈출 요소(숫자·인물·대조).
- 제목 하나에 유머·센스·반전·현실 공감·결과·감정 중 2가지 이상. 읽은 사람이 "그래서 무슨 일이야?" 하게.
- 실제 찬반이 있는 주제면 한쪽 결론을 미리 정하지 말고 쟁점을 궁금하게 ("누구 말이 맞지?", "왜 반대가 나오지?").
- 10개가 서로 다른 문장 구조. 딱딱한 기사·검색형 제목 금지. 순서 숫자(1., 2.) 금지.
- 인물이 주인공이면 '회사 + 이름'을 앞에 (예: 삼성 이재용, 엔비디아 젠슨황).
- 금지: 낚시(본문에 없는 약속), 투자 권유(사라·팔아라·지금 담아야), 도박 말(판돈·올인), 단정 전망, 비방.
- 숫자·사실은 취재 메모에 있는 것만."""

STRONG = """[이번 글은 '강하게' 차례 (대표 결정 2026-10-05: 3편에 1편쯤)]
- 사실 범위 안에서 표현을 약 30% 세게: 결과·감정이 바로 느껴지게 ("다 털렸다", "이건 좀 억울하다" 수준까지).
- 사람들이 억울하거나 화날 만한 지점(누가 손해를 보나, 약속과 다른 결과, 불공평한 기준)을 실제 사실·숫자로 정면에.
- 그래도 지킬 것: 사실과 숫자는 그대로, 특정인 비방·모욕 금지, 투자 권유·단정 전망 금지, 본문에 없는 약속 금지."""


def strong_turn() -> bool:
    """3편에 1편: 지금까지 만든 경제 글 수로 정한다 (0,1편째 보통 → 2번째마다 강하게)."""
    n = sum(1 for x in POSTS.iterdir() if x.is_dir()) if POSTS.exists() else 0
    return n % 3 == 2


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
                                     "badge": {"type": "string", "description": "이 제목의 핵심 2~8자 (도우미 표시용, 썸네일에는 안 씀)"}}}}}}
    strong = strong_turn()
    out = claude_json([TITLE_RULES] + ([STRONG] if strong else []), (
        f"키워드: {kw}\n\n[취재 메모]\n{memo[:6000]}\n\n[X 분위기 (Grok)]\n{vibe[:1500] or '없음'}\n\n"
        f"[인물 표기 목록]\n{', '.join(p['tag'] for p in people)}\n\n"
        "위 공식으로 서로 다른 각도의 제목 10개를 만들어 주세요. type은 질문형·숫자형·대비형·반전형·인물형 중 하나."),
        schema, stage="제목")
    items = out["titles"][:10]
    for t in items:  # 코드 검사만 (고르는 눈은 대표, 2026-10-05 결정: GPT 순위 뺌)
        n = len(t["title"])
        t["chars"] = n
        core = kw.split()[0]
        t["flags"] = ([f"{n}자(45자 넘음)"] if n > 45 else [f"{n}자(짧음)"] if n < 25 else []) + (
            [f"키워드 '{core}' 없음"] if core not in t["title"] else [])
    items.sort(key=lambda t: bool(t["flags"]))  # 글자 수 경고 있는 제목은 뒤로
    (d / "chosen.yaml").unlink(missing_ok=True)
    save(d / "titles.yaml", {"keyword": kw, "person": out.get("person", ""), "made": datetime.now(KST).strftime("%H:%M"),
                             "strong": strong, "items": items})
    print(f"제목 {len(items)}개 → {d}")
    return d


# ---------------------------------------------------------------- 3단계: 전체 제작

def skill(name: str) -> str:
    f = SKILLS / name / "SKILL.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


WRITE_RULES = """억선생의 경제판 글 규칙 (DECISIONS 2026-10-04~05, 강사 프롬프트 반영 10-05). blog-voice 스킬의 '억선생의 경제판' 절도 따른다.

[쓰기 전 머릿속 분석 — 본문에 이 말들을 절대 쓰지 않는다]
- 이 키워드를 검색한 사람이 무엇부터 찾는지 '검색 의도 순서'를 정하고, 그 순서로 글을 짠다.
- 취재 메모의 최근 기사들을 비교해 지금 가장 주목받는 이슈를 중심에 둔다(최신 한 건만 보지 않는다). 기존과 달라진 점을 찾는다.
- 지금 가장 궁금한 점, 억울하거나 화날 만한 점, 기대·기쁨, 놀라운·의외인 점, 현실 공감, 반응이 커질 점, 찬반이 갈리는 쟁점,
  누구에겐 이익이고 누구에겐 부담인 점, 숫자 해석이 엇갈리는 점 — 이 10가지를 찾아 실제 사건·돈·생활 이야기에 녹인다.
- 사실과 숫자가 충분하면 의견이 가장 갈리는 실제 쟁점을 중심축으로. 억지 논쟁은 만들지 않는다.
- 본문에 '궁금해 미칠 부분', '화나는 부분', '억울한 부분', '후킹 포인트', '논쟁 포인트', '검색자가 궁금해하는 이유' 같은 분석 말 금지.

[본문]
- 본문은 1,500자 이내(Q&A·면책 제외). 정보를 주는 문장만 남기고 글자 수 채우기 문장은 뺀다. 문단마다 새 사실이나 해석.
- 도입부는 매번 다르게: 가장 중요한 숫자 / 최근 사건 / 달라진 상황 / 독자가 겪는 현실 문제 / 예상과 실제의 차이 /
  시장에서 보이는 현상 / 엇갈리는 이해관계 중 이 주제에 가장 흥미로운 것. 첫 문단에서 글의 핵심을 분명히, 결론을 억지로 숨기지 않는다.
- 제목의 약속(promise)은 첫 2~3줄에서 바로 답한다.
- 실제 블로거가 여러 자료를 조사해 자기 말로 설명하듯. 짧은 문장과 긴 문장을 섞고, 같은 어미 반복 금지, 원인→결과로 이어지는 이야기.
- 글쓴이는 억선생('저'): 문단마다 생각·의외였던 점·의견·반응 한 마디. 관찰 표현('지수를 보며', '공시를 읽다가')은 권장.
  매매·보유·현장 같은 가짜 경험 금지, 투자 권유 금지, 단정 전망 금지, 도박 말 금지.
- 핵심키워드는 본문에 자연스럽게, 전체 20회 이내.
- 숫자 비교가 있으면 표 하나(table)로. 없으면 table.rows는 빈 배열.
- 출처: 본문·표·Q&A·태그 어디에도 언론사명·기사명·URL·도메인·각주·'○○에 따르면(언론사)'을 쓰지 않는다.
  여러 자료에서 공통으로 확인된 사실만 자기 문장으로. 공식 발표가 중요할 때만 '한국은행 발표에 따르면', '공시를 보면',
  '회사 공식 발표에 따르면'처럼 기관 이름만(링크 없이). 확인한 출처 목록은 sources에만 적는다(블로그에 안 나감).
- 기사 문장은 옮기지 않는다. 숫자는 취재 메모에 있는 것만.
- AI 티 문구 금지: 단순히 ○○의 문제가 아닙니다 / 중요한 것은 지금부터입니다 / 여기서 주목해야 할 점은 / 그렇다면 우리는 어떻게
  해야 할까요 / 결국 핵심은 하나입니다 / 이제부터 하나씩 살펴보겠습니다 / 과연 어떤 결과가 / 지금까지 알아보았습니다 /
  정리하자면 / 시사하는 바가 큽니다 / 눈여겨볼 필요가 있습니다 / 귀추가 주목됩니다.
- 소제목은 짧게, 필요할 때만. 그림 자리표('[그림 1]') 쓰지 않음(코드가 넣음).
- 마무리는 주제에 맞게 자연스럽게(억선생 생각 + 독자에게 묻는 한 줄 가능). 끝에 qa 3개(질문 한 줄·답 한 줄),
  마지막 문단은 '※ 이 글은 경제 공부를 위한 정보이며 투자 권유가 아닙니다. 본문 그림은 AI로 만들었습니다.'
- tags는 주제와 관련된 해시태그용 단어 18개(# 없이, 핵심키워드 변형 포함)."""

PRESS = re.compile(r"https?://|www\.|\.(com|co\.kr|net)\b|연합뉴스|한국경제|매일경제|조선일보|중앙일보|동아일보|한겨레|머니투데이|"
                   r"이데일리|뉴스1|뉴시스|서울경제|헤럴드경제|아시아경제|파이낸셜뉴스|블룸버그|로이터|CNBC|월스트리트저널|WSJ|"
                   r"파이낸셜타임스|기사 원문|출처:")


ARTICLE = {"type": "object", "additionalProperties": False,
           "required": ["paragraphs", "tags", "image_tags", "short", "sources", "area", "thumb_scene", "qa", "table"],
           "properties": {
               "area": {"type": "string", "enum": AREAS},
               "qa": {"type": "array", "description": "글 끝 3줄 Q&A (질문·답 각 한 줄)",
                      "items": {"type": "object", "additionalProperties": False, "required": ["q", "a"],
                                "properties": {"q": {"type": "string"}, "a": {"type": "string"}}}},
               "table": {"type": "object", "additionalProperties": False, "required": ["title", "header", "rows", "after"],
                         "description": "숫자 비교 표 하나 (없으면 rows 빈 배열). 출처·언론사명 넣지 않음",
                         "properties": {"title": {"type": "string"}, "header": {"type": "array", "items": {"type": "string"}},
                                        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                                        "after": {"type": "integer", "description": "몇 번째 문단(1부터) 뒤에 넣을지"}}},
               "thumb_scene": {"type": "string", "description": (
                   "썸네일 그림 장면 (영어 2~3문장). 제목의 주인공(회사·자산·사건)을 한눈에 알아보게 조선 풍속화로: "
                   "회사면 그 회사의 대표 제품·산업을 조선 장터 물건으로 바꿔 그림(예: SK하이닉스 → 장인이 빛나는 "
                   "반도체 칩을 엽전처럼 쌓아 파는 공방, 금 → 금괴 궤짝), 오르면 축제·상승, 내리면 호랑이·먹구름 같은 분위기. "
                   "실존 인물 얼굴·회사 로고·글자·숫자는 넣지 않는다.")},
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
    sys_prompt = [skill("money-content-writer"), skill("blog-voice"), WRITE_RULES] + learned()
    art = claude_json(sys_prompt, (
        f"제목: {pick['title']}\n본문 첫 2~3줄에서 회수할 답: {pick['promise']}\n주인공 인물: {T.get('person') or '없음'}\n\n"
        f"[취재 메모]\n{memo[:9000]}\n\n창고 그림 태그 목록: {', '.join(lib_tags)}\n위 규칙으로 글을 써 주세요."),
        ARTICLE, stage="글쓰기")
    body = "\n\n".join(art["paragraphs"])
    art, body, voice_note = humanize(sys_prompt, art, body, memo)
    art, body, gain_note, gain_ok = info_gain(T["keyword"], pick["title"], sys_prompt, art, body, memo)
    check = gpt("아래 경제 블로그 초안의 숫자·날짜·기관 전망·인물 직책이 사실인지 웹 검색으로 확인하세요. "
                "주요 언론사·공식 기관 출처만 인정합니다. 틀리거나 확인 안 되는 것만 JSON으로: "
                '{"issues": [{"claim": "초안 문장", "problem": "무엇이 틀렸나", "fix": "고칠 내용(출처)"}]}. 문제가 없으면 '
                '{"issues": []}\n\n' + body, search=True)
    issues = (parse_json(check) or {}).get("issues", [])
    if issues:
        art = claude_json(sys_prompt, (
            f"아래 초안을 사실 대조 결과대로 고쳐 주세요. 확인 안 되는 문장은 뺍니다. 본문에 언론사명·링크는 쓰지 말고, 꼭 필요하면 "
            f"'한국은행 발표에 따르면'처럼 기관 이름만 씁니다. 근거 출처는 sources에만.\n\n"
            f"[초안]\n{body}\n\n[사실 대조 (GPT)]\n{json.dumps(issues, ensure_ascii=False)}\n\n[취재 메모]\n{memo[:6000]}"),
            ARTICLE, stage="고쳐쓰기")
    art, polish_note = polish(sys_prompt, art, T["keyword"])
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
    thumb_note = make_thumb(post, T.get("person", ""), art.get("thumb_scene", ""), used)
    # 본문: 첫 2문단 뒤, 중간, 끝 앞에 그림
    paras = [x for x in art["paragraphs"] if not re.fullmatch(r"\s*\[(그림|사진|이미지)\s*\d*\]\s*", x)]  # AI가 넣은 그림 자리표 제거
    slots = [2, max(3, len(paras) // 2), max(4, len(paras) - 2)]
    tb = art.get("table") or {}
    if tb.get("rows"):
        (post / "table.json").write_text(json.dumps({k: tb[k] for k in ("title", "header", "rows")}, ensure_ascii=False),
                                         encoding="utf-8")
    foot = [x for x in paras if x.startswith("※")]
    paras = [x for x in paras if not x.startswith("※")]
    lines = ["[이미지 1_썸네일: thumb.png]"]
    for i, p in enumerate(paras):
        lines.append(p)
        if tb.get("rows") and i + 1 == max(1, min(tb.get("after", 2), len(paras))):
            lines.append(f"[표 1: {tb['title']}]")
        for k, s in enumerate(slots):
            if i + 1 == s and k < len(files):
                lines.append(f"[이미지 {k + 2}_{files[k]}: {files[k]}.jpg]")
    if art.get("qa"):
        lines.append("\n".join(f"Q. {x['q']}\nA. {x['a']}" for x in art["qa"][:3]))
    lines += foot
    (post / "body.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    alts = [t for t in T["items"] if t is not pick][:2]
    tags = ",".join(art["tags"][:18] + ["억선생", "억선생의경제판"])  # 해시태그 20개 (강사 기준)
    (post / "post.md").write_text("\n".join([
        f"# 발행 패키지 · {T['keyword']}", "",
        f"**상태:** {'✅ 사실 대조 통과' if not issues else '✅ 사실 대조 후 고침(' + str(len(issues)) + '곳)'}"
        + ("" if gain_ok else " · ⚠️ 정보 이득 부족 — 발행 보류, Claude에게 알려 주세요"),
        f"**정보 이득:** {gain_note}",
        f"**썸네일:** {thumb_note}", f"**사람 냄새 검사:** {voice_note}", f"**형식 검사:** {polish_note}",
        f"**글 성격:** {'🔥 강하게 (3편에 1편)' if T.get('strong') else '보통'}", "", f"- 카테고리: **{art['area']}**", f"- 태그: {tags}", "",
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


def learned() -> list[str]:
    """대표가 고친 곳(최근) + Aside가 조사한 참고 블로거 구조(최신) → 글쓰기 참고 (대표 결정 2026-10-05: 학습 필수)."""
    out = []
    edits = sorted(POSTS.glob("*/edits.md"), reverse=True)[:6]
    if edits:
        out.append("[대표가 최근 고친 곳: 원래 → 고친 글. 같은 방향으로 처음부터 쓴다]\n"
                   + "\n".join(f.read_text(encoding="utf-8")[-1500:] for f in edits)[:6000])
    for pat, who in (("20*.md", "Aside"), ("참고-블로거-틀.md", "공개 RSS로 정리한 틀")):
        ref = sorted((ROOT / "econ" / "ref").glob(pat), reverse=True)[:1]
        if ref:
            out.append(f"[참고 블로거 조사({who}). 구조·흐름·제목 모양만 참고하고 문장·표현은 절대 옮기지 않는다]\n"
                       + ref[0].read_text(encoding="utf-8")[:5000])
    return out


GAIN = {"type": "object", "additionalProperties": False, "required": ["gain", "missing", "pass"],
        "properties": {"gain": {"type": "array", "items": {"type": "string"},
                                "description": "상위 글들에 없고 우리 초안에만 있는 것 (구체적으로)"},
                       "missing": {"type": "string", "description": "통과 못 하면, 취재 메모에서 더할 수 있는 새 정보"},
                       "pass": {"type": "boolean"}}}


def top10(keyword: str) -> list[dict]:
    """네이버 공식 블로그 검색 API 정확도순 상위 10개 제목·요약 (검색 화면 크롤링 아님)."""
    from market.common import load_yaml, request_json
    from market.naver_hub import ApiHub, clean
    if not (key("NCP_APIGW_API_KEY_ID") and key("NCP_APIGW_API_KEY")):
        return []
    hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
    try:
        data = request_json("GET", hub.base + hub.paths["blog_search"], headers=hub._headers(),
                            params={"query": keyword, "display": 10, "sort": "sim"})
    except Exception as e:  # noqa: BLE001
        print(f"네이버 검색 실패: {str(e)[:120]}")
        return []
    return [{"title": clean(it.get("title")), "desc": clean(it.get("description")), "date": it.get("postdate", "")}
            for it in data.get("items", [])]


def info_gain(keyword: str, title: str, sys_prompt: list[str], art: dict, body: str, memo: str
              ) -> tuple[dict, str, str, bool]:
    """정보 이득 게이트 (CLAUDE.md, 설계서 12.2): 상위 10개 글에 없는 것이 우리 글에 하나도 없으면 발행하지 않는다.
    한 번은 취재 메모에서 새 정보를 더해 고쳐 쓰고, 그래도 없으면 '발행 보류'로 표시한다."""
    rows = top10(keyword)
    if not rows:
        return art, body, "⚠️ 네이버 검색이 안 돼 검사를 못 함 (발행 전 Claude 확인)", False
    comp = "\n".join(f"{i}. {r['title']} ({r['date']}) — {r['desc']}" for i, r in enumerate(rows, 1))
    ask = ("아래 [상위 10개 글](네이버 검색 상위 제목·요약)과 [우리 초안]을 비교하세요. 상위 글들에 없고 우리 초안에만 있는 "
           "독자에게 쓸모 있는 것(새 숫자·비교·일정·관점·설명 방식)을 구체적으로 적으세요. 하나라도 분명하면 pass=true.\n\n"
           f"[검색어] {keyword}\n[상위 10개 글]\n{comp}\n\n[우리 초안]\n{body}")
    g = claude_json(["너는 깐깐한 편집장이다. 남의 글을 옮기지 않고, 상위 글과 겹치는 내용은 이득으로 치지 않는다."], ask, GAIN,
                    stage="정보 이득")
    if g["pass"] and g["gain"]:
        return art, body, "✅ 통과 — " + " / ".join(g["gain"][:3]), True
    fix = claude_json(sys_prompt, (
        f"이 초안은 네이버 상위 10개 글과 내용이 겹쳐 새로 얻을 정보가 없습니다. 취재 메모에 있는 사실만으로 아래를 더해 "
        f"다시 써 주세요(지어내기 금지, 상위 글 문장 옮기기 금지, 사람 냄새 유지).\n더할 것: {g['missing']}\n\n"
        f"[상위 10개 글 요약]\n{comp}\n\n[초안]\n{body}\n\n[취재 메모]\n{memo[:6000]}"), ARTICLE, stage="고쳐쓰기(정보 이득)")
    nbody = "\n\n".join(fix["paragraphs"])
    g2 = claude_json(["너는 깐깐한 편집장이다. 남의 글을 옮기지 않고, 상위 글과 겹치는 내용은 이득으로 치지 않는다."],
                     ask.replace(body, nbody), GAIN, stage="정보 이득(재검사)")
    if g2["pass"] and g2["gain"]:
        return fix, nbody, "✅ 고쳐 써서 통과 — " + " / ".join(g2["gain"][:3]), True
    return fix, nbody, "⛔ 상위 10개 글에 없는 정보를 못 찾음 — " + g2["missing"][:120], False


def polish(sys_prompt: list[str], art: dict, keyword: str) -> tuple[dict, str]:
    """강사 기준 형식 검사(코드): 본문 1,500자 이내 · 언론사명/링크 없음 · 핵심키워드 20회 이내. 어긋나면 한 번 고쳐 쓴다."""
    def check(a: dict) -> list[str]:
        prose = [x for x in a["paragraphs"] if not x.startswith("※")]
        text = "\n".join(prose)
        n, core = len(re.sub(r"\s", "", text)), keyword.split()[0]
        bad = []
        if n > 1600:
            bad.append(f"본문 {n}자(공백 빼고) → 1,500자 안으로 줄이기")
        m = PRESS.findall(text + " ".join(x["q"] + x["a"] for x in a.get("qa", [])))
        if m:
            bad.append(f"언론사명·링크 {len(m)}곳 → 빼고 사실만 (기관 발표는 기관 이름만)")
        if text.count(core) > 20:
            bad.append(f"핵심키워드 '{core}' {text.count(core)}회 → 20회 이내")
        return bad
    bad = check(art)
    if not bad:
        return art, "통과 (1,500자·출처 표기·키워드 횟수)"
    fixed = claude_json(sys_prompt, "아래 초안을 이 문제만 고쳐 다시 주세요. 내용·사실·사람 냄새는 그대로.\n- " + "\n- ".join(bad)
                        + "\n\n[초안]\n" + json.dumps(art, ensure_ascii=False), ARTICLE, stage="고쳐쓰기(형식)")
    left = check(fixed)
    return fixed, ("고쳐 씀: " + " / ".join(bad)) + (f" · ⚠️ 남음: {' / '.join(left)}" if left else "")


def humanize(sys_prompt: list[str], art: dict, body: str, memo: str) -> tuple[dict, str, str]:
    """사람 냄새·이야기 검사 (스포츠 때와 같은 기준, 2026-10-05): 생각 없는 문단이 25%를 넘거나 AI 티가 있으면 한 번 고쳐 쓴다."""
    from .voice import check_draft, human_gaps, prose_paragraphs
    gaps, ai = human_gaps(body), check_draft(body)
    total = max(1, len(prose_paragraphs(body)))
    if len(gaps) / total <= 0.25 and not ai:
        return art, body, f"통과 (생각 없는 문단 {len(gaps)}/{total})"
    fix = claude_json(sys_prompt, (
        "아래 초안은 사실은 맞지만 사람 냄새와 이야기가 부족합니다. 사실·숫자·출처는 그대로 두고 다음만 고쳐 주세요.\n"
        "1) 아래 문단마다 억선생('저')의 생각·의외였던 점·의견·반응을 한 마디씩 (문단마다 다른 말로, 하지 않은 경험은 금지)\n"
        "2) 첫머리를 그날의 한 장면으로, 이유는 '누가 무엇을 했나'로, 끝은 억선생 생각 + 독자에게 묻는 한 줄\n"
        f"3) AI 티 표현 고치기: {', '.join(ai) or '없음'}\n\n[생각이 안 보이는 문단 앞부분]\n" + "\n".join(gaps)
        + f"\n\n[초안]\n{body}\n\n[취재 메모]\n{memo[:4000]}"), ARTICLE, stage="고쳐쓰기(사람 냄새)")
    nbody = "\n\n".join(fix["paragraphs"])
    ngaps = human_gaps(nbody)
    if len(ngaps) <= len(gaps):
        return fix, nbody, f"고쳐 씀 (생각 없는 문단 {len(gaps)} → {len(ngaps)}/{max(1, len(prose_paragraphs(nbody)))})"
    return art, body, f"고쳐 써도 나아지지 않아 원본 유지 (생각 없는 문단 {len(gaps)}/{total})"


# ---------------------------------------------------------------- 썸네일

FONT = ROOT / "assets" / "fonts" / "Pretendard-Black.otf"


DRAW_THUMB = False  # 제목 장면 새로 그리기: 대표가 "원했던 것과 다름" → 재논의 전까지 끔(창고 그림, 글자 없음, 0원)


def make_thumb(post: Path, person: str, scene: str, used: list[str]) -> str:
    """썸네일 = 글자 없는 그림 한 장, 화풍 그대로, 제목에 맞는 장면 (대표 결정 2026-10-05).
    인물 글 = Gemini 얼굴·상반신 캐리커처(작은 'AI 일러스트' 표시만), 아니면 제목 장면을 GPT Image 2로 새로 그림.
    둘 다 안 되면 창고 그림 (글자 없이)."""
    from .hook_thumb import PAPER, INK, _cover
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
            c.paste(bust, ((W - bust.width) // 2, W - bust.height), bust)
            ImageDraw.Draw(c).text((W - 200, W - 50), "AI 일러스트", font=ImageFont.truetype(str(FONT), 28),
                                   fill=PAPER, stroke_width=3, stroke_fill=INK)  # 실존 인물 캐리커처 표시 규칙(10-05)
            c.save(post / "thumb.png")
            return f"인물 상반신({person}, Gemini 캐리커처), 글자 없음"
    if DRAW_THUMB and scene and draw_scene(scene, post / "thumb.png"):
        return "제목 장면 새로 그림(GPT Image 2 고화질), 글자 없음"
    from .art_library import pick as lib_pick
    name = (used or lib_pick(["시황"], [], 1) or ["market-morning"])[0]
    _cover(Image.open(LIB / f"{name}.jpg").convert("RGB"), W, W, 0.5).save(post / "thumb.png")
    return f"창고 그림({name}), 글자 없음" + ("" if not DRAW_THUMB else " (⚠️ 새 그림 실패)")


def draw_scene(scene: str, out: Path) -> bool:
    """제목 장면을 화풍(post_art.STYLE) 그대로 정사각형 고화질로 그린다. 1장 약 $0.21."""
    from .post_art import STYLE
    if not key("OPENAI_API_KEY"):
        return False
    r = requests.post("https://api.openai.com/v1/images/generations", timeout=600,
                      headers={"Authorization": f"Bearer {key('OPENAI_API_KEY')}"},
                      json={"model": "gpt-image-2", "n": 1, "size": "1024x1024", "quality": "high",
                            "prompt": STYLE + "Square blog thumbnail, one clear main subject large in the center, readable "
                                      "even when very small, bold contrast. " + scene
                                      + " Absolutely no text, letters, numbers, logos or signatures anywhere."})
    if r.status_code != 200:
        print(f"썸네일 그림 실패 HTTP {r.status_code}: {r.text[:160]}")
        return False
    SPENT["image"] += 0.21
    out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return True


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
    SPENT["image"] += 0.134  # 어림: Gemini 3 Pro 이미지 유료 단가 1장 (무료 한도 안이면 실제 0원)
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
    if cmd != "add":
        guard()
    try:
        _run(cmd)
    finally:
        if any(SPENT.values()):
            log_cost(cmd, " ".join(sys.argv[2:4]))


def _run(cmd: str) -> None:
    if cmd == "keywords":
        keywords()
    elif cmd == "add":
        add(sys.argv[2])
    elif cmd == "titles":  # 경제 = 쿠니네 방식, 연예·패션 = 강사 연예·패션 프롬프트 (대표 결정 2026-10-05)
        mod = __import__("content.kunine" if BLOG["id"] == "econ" else "content.celeb", fromlist=["titles"])
        kws = [k.strip() for k in re.split(r"\s+/\s+|\n", sys.argv[2]) if k.strip()][:5]  # 여러 개는 ' / '로 (대표 지시 2026-10-06)
        bad = []
        for kw in kws:
            try:
                guard()
                mod.titles(kw)
            except Exception as ex:  # 하나가 실패해도 나머지는 계속
                print(f"제목 실패: {kw}: {ex}")
                bad.append(kw)
        if bad and len(bad) == len(kws):
            raise SystemExit("제목 만들기가 모두 실패했어요: " + ", ".join(bad))
    elif cmd == "produce":
        mod = __import__("content.kunine" if BLOG["id"] == "econ" else "content.celeb", fromlist=["produce"])
        mod.produce(sys.argv[2], int(sys.argv[3]))
    else:
        raise SystemExit(f"모르는 명령: {cmd}")


if __name__ == "__main__":
    # `python -m`으로 돌리면 이 파일이 __main__으로 한 번 더 올라가, 다른 모듈(econ_score 등)이 쓴 비용이 따로 쌓인다.
    # 같은 모듈(content.econ_flow)로 돌려서 비용 기록(SPENT)을 하나로 모은다 (2026-10-05 키워드 Claude 비용 누락 수정).
    from content import econ_flow as _m
    _m.main()
