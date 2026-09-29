"""자동 글쓰기: 뉴스 수집 → 숫자 뽑기(Claude) → 충돌 정리·계산·그래픽(코드) → 글쓰기(Claude) → 검사(코드) → 발행 패키지.

- 수집은 네이버 뉴스 검색 API(허용된 통로)로 제목·요약문만 받는다. 요약문은 숫자를 뽑는 데만 쓰고 저장하지 않는다.
- 숫자는 코드가 계산하고, 글에는 코드가 만든 '숫자표'에 있는 숫자만 쓸 수 있다 (검사로 강제).
- 출처끼리 숫자가 다르면 DECISIONS의 숫자 충돌 규칙을 코드로 적용한다 (최신 기사 → 같은 날이면 다수 → 차이 표기).
- 발행은 운영자가 한다 (네이버 블로그에는 글쓰기 API가 없다). 이 코드는 posts/<날짜>-<id>/에 패키지만 만든다.

사용법: python -m content.autopost [--sample] [--topic 대기열id또는선수이름]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from market.common import ROOT, load_yaml, missing_secrets
from . import receipt
from .receipt import won
from .voice import check_draft

POSTS = ROOT / "posts"
SKILLS = ROOT / ".claude" / "skills"
EXAMPLE_POST = POSTS / "2026-10-01-이정후-영수증" / "post.md"
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
BANNED = ["토토", "프로토", "배당", "베팅", "배팅", "열애", "여자친구", "남자친구", "이혼", "루머", "인성 논란"]

# ---------------------------------------------------------------- 스키마

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "usable": {"type": "boolean"},
        "reason": {"type": "string"},
        "season": {"type": "integer"},
        "salary_currency": {"type": "string", "enum": ["USD", "KRW"]},
        "salary_basis": {"type": "string"},
        "facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "label": {"type": "string"}, "value": {"type": "number"},
                           "unit": {"type": "string"}, "source": {"type": "integer"}},
            "required": ["key", "label", "value", "unit", "source"], "additionalProperties": False}},
        "units": {"type": "array", "items": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "label": {"type": "string"}},
            "required": ["key", "label"], "additionalProperties": False}},
        "headline_unit": {"type": "string"},
        "story": {"type": "array", "items": {
            "type": "object",
            "properties": {"point": {"type": "string"}, "source": {"type": "integer"}},
            "required": ["point", "source"], "additionalProperties": False}},
    },
    "required": ["usable", "reason", "season", "salary_currency", "salary_basis", "facts", "units",
                 "headline_unit", "story"],
    "additionalProperties": False,
}

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "gate_pass": {"type": "boolean"},
        "info_gain": {"type": "string"},
        "titles": {"type": "array", "items": {
            "type": "object",
            "properties": {"text": {"type": "string"},
                           "type": {"type": "string", "enum": ["숫자형", "대비형", "순위형", "반전형", "질문형"]}},
            "required": ["text", "type"], "additionalProperties": False}},
        "recommended": {"type": "integer"},
        "body": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "cross_compare": {"type": "string"},
    },
    "required": ["gate_pass", "info_gain", "titles", "recommended", "body", "tags", "cross_compare"],
    "additionalProperties": False,
}

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "player": {"type": "string"}, "team": {"type": "string"}, "sport": {"type": "string"},
        "angle": {"type": "string"},
        "queries": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["found", "player", "team", "sport", "angle", "queries"],
    "additionalProperties": False,
}

EXTRACT_RULES = """너는 스포츠 기사 요약문에서 숫자 사실만 뽑는 담당이다. 글은 쓰지 않는다.

규칙
- 요약문에 글자로 적힌 숫자만 뽑는다. 추측·계산·기억으로 채우지 않는다. 없으면 빼거나 usable=false.
- 같은 사실을 여러 기사가 말하면 기사마다 한 줄씩 따로 적는다 (source = 기사 번호). 어느 쪽이 맞는지는 코드가 정한다.
- key는 영어 소문자_밑줄. 연봉은 반드시 key "salary", 올해 시즌 연봉 1년치(계약 총액 아님). 단위(unit)는 USD 또는 KRW, value는 원·달러 그대로의 숫자(예: 2200만 달러 → 22000000).
- 연봉이 달러면 원달러 환율도 key "fx_krw_per_usd"로 뽑는다 (가장 최근 마감 환율, 1달러당 원).
- 경기·이닝·안타 같은 올 시즌 누적 기록은 key를 짧게 (games, innings, wins, strikeouts, at_bats, hits, home_runs, goals, assists 등). 타율·평균자책점도 facts에 넣되 units에는 넣지 않는다.
- units: 연봉을 나눌 단위 2~4개. key는 facts의 key, label은 "1경기", "1이닝"처럼. 0이거나 없는 기록은 넣지 않는다.
- headline_unit: 제목에 쓸 가장 눈길 끄는 단위 key.
- story: 글 맥락이 되는 사실 3~6개를 짧게 네 말로 (기사 문장 복사 금지). 숫자는 facts에 있는 것만. 사생활·연애·가족·논란·도박은 빼라.
- salary_basis: 연봉 근거를 한 줄로 (예: "6년 1억1300만 달러 계약 중 2026년 연봉, 보도 기준").
- usable=false: 올해 연봉 또는 나눌 기록이 요약문에 없을 때. reason에 무엇이 없는지 적는다.
"""

WRITE_RULES = """너는 네이버 블로그 "억소리 나는 스포츠"(닉네임 백억소리)의 글쓴이다. 목표는 홈판에서 눌리고 끝까지 읽히는 글이다.
위의 두 스킬 문서(blog-voice, money-content-writer)를 따른다. 특히 아래는 반드시 지킨다.

숫자
- 글과 제목에는 사용자가 준 '숫자표'에 있는 숫자만 쓴다. 새로 계산하거나 반올림해서 키우지 않는다.
- 줄여 쓰기는 버림만 허용: "2억 32만 원" → "2억", "298억 4,740만 원" → "약 298억 원".
- 출처끼리 차이가 있다고 표시된 숫자는 본문에 "보도에 따라 약간 차이가 있어요"를 한 번 적는다.

구조 (홈판형)
- 첫 줄은 제목의 답이 되는 숫자 한 줄. 제목에서 던진 숫자는 본문 첫 화면에서 회수한다.
- 문단은 3문장 이하, 짧은 문장과 긴 문장을 섞는다. 질문 2~4개. 최저임금 같은 교차 비교 1번.
- 이미지 자리는 정확히 이 두 줄을 각각 한 줄로 넣는다: "[이미지 1_첫문단아래: thumb.png]" (첫 문단 바로 아래), "[이미지 2_영수증: receipt.png]" (단위별 금액을 말하기 직전).
- 끝에서 둘째 문단: 다음 글 예고가 주어지면 한 줄로 예고한다. 없으면 독자 의견을 묻는 질문.
- 마지막 문단: "기준: ..."으로 연봉·성적·환율·최저임금의 기준일과 출처 종류를 한 문장으로.

금지
- 기사 문장·표현 복사, 경쟁 글 흉내. 요약된 사실만 네 말로.
- 가짜 경험("직접 봤다", "경기장에서"), 사생활·연애·가족·논란·개인 재산, 도박(배당·토토), 투자 권유.
- "알아보겠습니다", "결론적으로", "다양한", "것입니다" 같은 AI 티 표현 (voice 검사에서 걸린다).
- 마크다운 기호(#, **, 표). 네이버 에디터에 그대로 붙여 넣을 일반 텍스트로 쓴다.

출력
- gate_pass: 숫자표로 '새로 계산한 숫자'라는 정보 이득을 만들 수 있으면 true. info_gain에 한 줄.
- titles 5개, 유형을 모두 다르게. recommended는 추천 제목 번호(1~5). 제목 앞부분에 큰 숫자.
- tags: 10개 이하, 띄어쓰기 없이.
- cross_compare: 본문에 쓴 교차 비교 한 줄 요약.
"""


# ---------------------------------------------------------------- 수집

def gather_news(hub, queries: list[str], per_query: int = 15) -> list[dict]:
    """검색어마다 최신 기사 per_query개 (중복 제거), 최신순."""
    seen, out = set(), []
    for q in queries:
        kept = 0
        for it in hub.news(q, display=30):
            if kept >= per_query:
                break
            if it["link"] in seen or not it["description"]:
                continue
            seen.add(it["link"])
            out.append(it)
            kept += 1
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def news_prompt(news: list[dict]) -> str:
    return "\n".join(f"[{i}] ({it['date']}) {it['title']} — {it['description']}" for i, it in enumerate(news, 1))


def done_ids() -> set[str]:
    return {p.name for p in POSTS.iterdir() if p.is_dir()} if POSTS.exists() else set()


def pick_topic(cfg: dict, override: str | None = None) -> dict | None:
    names = done_ids()
    for t in cfg.get("queue", []):
        if override and override not in (t["id"], t["player"]):
            continue
        if override or not any(n.endswith("-" + t["id"]) for n in names):
            return t
    if override:  # 대기열에 없는 선수 이름을 직접 준 경우
        return {"id": f"{override}-영수증", "player": override, "team": "", "sport": "", "category": "선수 몸값",
                "angle": "올해 연봉을 경기 기록 단위로 쪼갠다", "queries": [f"{override} 연봉", f"{override} 시즌 성적"]}
    return None


def discover_topic(cfg: dict, hub, llm) -> dict | None:
    """대기열이 비면 최근 뉴스에서 연봉과 올 시즌 기록이 둘 다 보도된 선수를 고른다."""
    news = gather_news(hub, cfg.get("discover_queries", []), per_query=12)
    done = sorted({n.split("-", 3)[-1].removesuffix("-영수증") for n in done_ids()})
    prompt = (f"이미 쓴 선수: {', '.join(done) or '없음'}\n\n아래 뉴스 요약에서 '올해 연봉'과 '올 시즌 기록'이 모두 보도된 "
              "선수 1명을 골라라. 이미 쓴 선수는 빼고, 사생활·논란 기사로만 알려진 선수도 뺀다. queries는 네이버 뉴스 검색어 3~4개.\n\n"
              + news_prompt(news))
    t = llm.ask_json(["너는 스포츠 돈 블로그의 편집자다. 검색이 많이 될 스타 선수를 우선한다."], prompt, TOPIC_SCHEMA,
                     max_tokens=4000, **extract_opts())
    if not t.get("found"):
        return None
    return {"id": f"{t['player'].replace(' ', '')}-영수증", "category": "선수 몸값", **t}


# ---------------------------------------------------------------- 숫자 정리 (코드)

def resolve(facts: list[dict], news: list[dict]) -> dict[str, dict]:
    """같은 key의 숫자가 기사마다 다르면: 1) 최신 기사 2) 같은 날이면 다수 3) 차이를 note로 남긴다."""
    groups: dict[str, list[dict]] = {}
    for f in facts:
        if 1 <= f["source"] <= len(news):
            groups.setdefault(f["key"], []).append({**f, "date": news[f["source"] - 1]["date"],
                                                    "link": news[f["source"] - 1]["link"]})
    out = {}
    for key, cands in groups.items():
        latest = max(c["date"] for c in cands)
        top = [c for c in cands if c["date"] == latest]
        value = Counter(c["value"] for c in top).most_common(1)[0][0]
        chosen = [c for c in top if c["value"] == value]
        values = sorted({c["value"] for c in cands})
        rule = "출처 1개" if len(cands) == 1 else ("모두 같음" if len(values) == 1 else
               ("최신 기사" if len(top) < len(cands) else "같은 날짜 다수"))
        out[key] = {"value": value, "label": chosen[0]["label"], "unit": chosen[0]["unit"], "date": latest,
                    "sources": sorted({c["link"] for c in chosen}), "rule": rule,
                    "differs": values if len(values) > 1 else None}
    return out


def build_data(topic: dict, ex: dict, facts: dict, cfg: dict) -> tuple[dict | None, str]:
    """receipt.py 입력을 만든다. 모자라거나 말이 안 되는 숫자면 (None, 이유)."""
    sal = facts.get("salary")
    if not sal:
        return None, "올해 연봉을 찾지 못함"
    usd = ex["salary_currency"] == "USD"
    if usd and not 1e5 <= sal["value"] <= 1e8 or not usd and not 3e7 <= sal["value"] <= 1e11:
        return None, f"연봉 숫자가 이상함 ({sal['value']:,} {ex['salary_currency']})"
    d = {"player": topic["player"], "team": topic.get("team", ""), "season": ex["season"],
         "salary_label": f"연봉 {won(sal['value'])} · {ex['salary_basis']}" if not usd else None}
    if usd:
        fx = facts.get("fx_krw_per_usd")
        if not fx or not 900 <= fx["value"] <= 2500:
            return None, "환율을 찾지 못함"
        d |= {"salary_usd": sal["value"], "fx_krw_per_usd": fx["value"],
              "fx_label": f"1달러 = {fx['value']:,}원 ({fx['date']})"}
    else:
        d["salary_krw"] = sal["value"]
    units = [{"key": u["key"], "label": u["label"], "count": facts[u["key"]]["value"]}
             for u in ex["units"] if u["key"] in facts and facts[u["key"]]["value"] > 0]
    if len(units) < 2:
        return None, "연봉을 나눌 기록이 2개 미만"
    d["units"] = units
    d["headline_unit"] = ex["headline_unit"]
    d["min_wage_monthly_krw"] = cfg["constants"]["min_wage_monthly_krw"]
    return {k: v for k, v in d.items() if v is not None}, ""


def number_sheet(d: dict, n: dict, facts: dict, ex: dict, cfg: dict) -> str:
    """글에 쓸 수 있는 숫자 전부. 글쓰기 검사도 이 표를 기준으로 한다."""
    L = [f"선수: {d['player']} ({d.get('team', '')}), 시즌 {d['season']}"]
    if d.get("salary_usd"):
        L.append(f"올해 연봉: {d['salary_usd'] / 1e4:,.0f}만 달러 = {won(n['salary_krw'])} ({d['fx_label']})")
    else:
        L.append(f"올해 연봉: {won(n['salary_krw'])}")
    L.append(f"연봉 근거: {ex['salary_basis']}")
    for u in receipt.units(d):
        L.append(f"{u['label']}당: {won(n['per'][u['key']])} (올 시즌 {u['count']:,}, 버림 표기 {won(n['per'][u['key']]).split(' ')[0]})")
        if n.get("min_wage_years_per"):
            L.append(f"  = 최저임금 연봉 {n['min_wage_years_per'][u['key']]:.1f}년치")
    if n.get("min_wage_yearly_krw"):
        L.append(f"최저임금 1년: {won(n['min_wage_yearly_krw'])} ({cfg['constants']['min_wage_label']})")
    L.append("기록·사실 (기사 날짜 · 정한 규칙):")
    for k, f in facts.items():
        if k in ("salary", "fx_krw_per_usd"):
            continue
        v = f"{f['value']:,}" if float(f["value"]).is_integer() else f"{f['value']}"
        diff = f" · 출처끼리 차이 {f['differs']} → 본문에 '보도에 따라 약간 차이' 표기" if f["differs"] else ""
        L.append(f"- {f['label']}: {v}{f['unit'] if f['unit'] not in ('KRW', 'USD') else ''} ({f['date']} · {f['rule']}){diff}")
    L.append("맥락 (네 말로 풀어 쓸 것):")
    L += [f"- {s['point']}" for s in ex["story"]]
    return "\n".join(L)


def unknown_numbers(text: str, sheet: str, extra: str = "") -> list[str]:
    """숫자표에 없는 숫자. 31 이하 정수(날짜·순서)와 연도는 허용한다."""
    allowed = {t.replace(",", "") for t in NUM.findall(sheet + " " + extra)}
    bad = []
    for t in NUM.findall(text):
        v = t.replace(",", "")
        if v in allowed or (v.isdigit() and (int(v) <= 31 or 2000 <= int(v) <= 2035)):
            continue
        bad.append(t)
    return sorted(set(bad))


def check_post(p: dict, sheet: str) -> list[str]:
    problems = list(check_draft(p["body"]))
    for label, text in [("본문", p["body"])] + [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]:
        bad = unknown_numbers(text, sheet)
        if bad:
            problems.append(f"{label}에 숫자표에 없는 숫자: {', '.join(bad)}")
    for img in ("thumb.png", "receipt.png"):
        if img not in p["body"]:
            problems.append(f"이미지 자리 {img} 없음")
    hit = [w for w in BANNED if w in p["body"]]
    if hit:
        problems.append(f"금지 주제 단어: {', '.join(hit)}")
    if len(p["titles"]) != 5 or not 1 <= p["recommended"] <= len(p["titles"]):
        problems.append("제목 5개와 추천 번호(1~5)가 필요")
    if re.search(r"^#|\*\*", p["body"], re.M):
        problems.append("마크다운 기호(#, **)를 빼고 일반 텍스트로")
    return problems


# ---------------------------------------------------------------- 글쓰기 (Claude)

def writer_system() -> list[str]:
    docs = [(SKILLS / s / "SKILL.md").read_text(encoding="utf-8") for s in ("blog-voice", "money-content-writer")]
    example = ""
    if EXAMPLE_POST.exists():
        t = EXAMPLE_POST.read_text(encoding="utf-8")
        m = re.search(r"## 본문[^\n]*\n(.*?)\n## 출처", t, re.S)
        example = ("# 이 블로그에 이미 올린 글 (말투·길이·구조 참고용. 문장을 재사용하지 말 것)\n\n" + m.group(1)) if m else ""
    return [t for t in docs + [example, WRITE_RULES] if t.strip()]


def llm_cfg() -> dict:
    return load_yaml("global.yaml").get("llm", {})


def extract_opts() -> dict:
    e = llm_cfg().get("extract", {})
    return {"model": e.get("model", "claude-sonnet-5-5"), "effort": e.get("effort", "low")}


def write_post(llm, topic: dict, sheet: str, next_topic: dict | None, max_revisions: int) -> tuple[dict, list[str], int]:
    w = llm_cfg().get("write", {})
    cap = llm_cfg().get("cost_cap_usd_per_post", 1.0)
    opts = {"model": w.get("model", "claude-sonnet-5-5"), "effort": w.get("effort", "medium")}
    system = writer_system()
    teaser = f"다음 글 예고: {next_topic['player']} — {next_topic['angle']}" if next_topic else "다음 글 예고: 없음"
    prompt = (f"카테고리: {topic['category']}\n글 방향: {topic['angle']}\n{teaser}\n\n숫자표\n{sheet}\n\n"
              "이 숫자표로 발행 패키지를 JSON으로 만들어라.")
    post = llm.ask_json(system, prompt, POST_SCHEMA, **opts)
    problems = check_post(post, sheet)
    rounds = 0
    while problems and rounds < max_revisions and llm.cost_usd() < cap:
        rounds += 1
        fix = (prompt + "\n\n아래는 네가 쓴 초안이다. 검사에서 걸린 문제만 고치고, 나머지는 유지해서 같은 JSON 형식으로 다시 내라.\n"
               "문제:\n" + "\n".join(f"- {x}" for x in problems) + "\n\n초안:\n" + json.dumps(post, ensure_ascii=False))
        post = llm.ask_json(system, fix, POST_SCHEMA, **opts)
        problems = check_post(post, sheet)
    return post, problems, rounds


# ---------------------------------------------------------------- 패키지

def package_md(topic: dict, d: dict, facts: dict, post: dict, problems: list[str], rounds: int,
               cfg: dict, news_used: list[dict], cost: float | None) -> str:
    rec = post["recommended"]
    status = "✅ 자동 검사 통과" if not problems and post["gate_pass"] else "⚠️ 검사 미통과 — 발행하지 말고 Claude에게 알려주세요"
    out = [f"# 발행 패키지 · {d['player']} {d['season']} 연봉 영수증", "",
           f"**상태:** {status}  ", f"**게이트:** {'통과' if post['gate_pass'] else '미통과'} — 정보 이득: {post['info_gain']}  ",
           f"**자동 작성:** Claude 초안 → 코드 검사 (고쳐 쓰기 {rounds}회)" + (f" · API 비용 약 ${cost:.2f}" if cost else ""), ""]
    if problems:
        out += ["**남은 문제:**", ""] + [f"- {p}" for p in problems] + [""]
    out += ["## 제목 (추천 ★)", ""]
    out += [f"{i}. {'★ ' if i == rec else ''}{t['text']} — {t['type']}" for i, t in enumerate(post["titles"], 1)]
    out += ["", "## 이미지 (본문 [이미지] 자리에 넣기)", "", "| 순서 | 파일 | 위치 | 대표이미지 |", "| --- | --- | --- | --- |",
            "| 1 | thumb.png | 첫 문단 아래 | ✅ 대표이미지로 지정 |", "| 2 | receipt.png | 영수증 설명 위 | |", "",
            "## 카테고리 · 태그", "", f"- 카테고리: **{topic['category']}**", f"- 태그: {', '.join(post['tags'][:10])}", "",
            "## 본문 (복사해서 붙여넣기, [이미지 …] 줄은 지우고 그 자리에 사진 넣기)", "", post["body"].strip(), "",
            "## 출처", ""]
    links = sorted({l for f in facts.values() for l in f["sources"]})
    out += [f"- {l}" for l in links] + [f"- 최저임금: {cfg['constants']['min_wage_source']}", ""]
    out += ["## 팩트체크 목록 (코드가 정한 값)", "", "| 수치 | 값 | 기사 날짜 | 정한 규칙 |", "| --- | --- | --- | --- |"]
    for k, f in facts.items():
        diff = f" (출처별 {', '.join(map(str, f['differs']))})" if f["differs"] else ""
        out.append(f"| {f['label']} | {f['value']:,} {f['unit']} | {f['date']} | {f['rule']}{diff} |")
    out += ["| 단위별 금액 | numbers.json | - | 코드 계산 |", "",
            "## 실험 기록용", "",
            f"- 추천 제목 유형: {post['titles'][rec - 1]['type']} · 교차 비교: {post['cross_compare']} · 이미지 2 · 참고 기사 {len(news_used)}건", ""]
    return "\n".join(out)


def write_index() -> None:
    """posts/README.md: 휴대폰에서 posts 폴더를 열면 바로 보이는 목록."""
    rows = []
    for p in sorted((x for x in POSTS.iterdir() if x.is_dir()), reverse=True):
        md = p / "post.md"
        if not md.exists():
            continue
        t = md.read_text(encoding="utf-8")
        st = "⚠️ 확인 필요" if "⚠️" in t.split("## 제목")[0] else "✅ 발행 가능"
        title = next((l.split("★ ", 1)[1].rsplit(" — ", 1)[0] for l in t.splitlines() if "★ " in l), p.name)
        rows.append(f"| {p.name[:10]} | [{title}]({p.name}/post.md) | {st} |")
    POSTS.joinpath("README.md").write_text(
        "# 발행 대기 글\n\n만든 글 목록입니다 (최신이 위). 글을 눌러 제목·본문·이미지를 복사해 발행하세요.\n\n"
        "| 날짜 | 추천 제목 | 상태 |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n", encoding="utf-8")


def run(hub, llm, *, today: str, topic_override: str | None = None, out_root: Path = POSTS) -> tuple[str, Path | None]:
    cfg = load_yaml("post_queue.yaml")
    if not topic_override and out_root == POSTS:
        today_made = [p for p in done_ids() if p.startswith(today)
                      and "**자동 작성:**" in (POSTS / p / "post.md").read_text(encoding="utf-8", errors="ignore")
                      if (POSTS / p / "post.md").exists()]
        if len(today_made) >= cfg.get("daily_limit", 1):
            return f"오늘 이미 {len(today_made)}편을 만들었습니다 (하루 한도 {cfg.get('daily_limit', 1)}편).", None
    notes: list[str] = []
    if topic_override:
        candidates = [pick_topic(cfg, topic_override)]
    else:
        candidates = [t for t in cfg.get("queue", []) if not any(n.endswith("-" + t["id"]) for n in done_ids())][:3]
        if not candidates:
            found = discover_topic(cfg, hub, llm)
            candidates = [found] if found else []
    for topic in candidates:  # 숫자가 모자라면 다음 선수로 넘어간다 (최대 3명)
        news = gather_news(hub, topic["queries"] + [cfg["fx_query"]])
        ex = llm.ask_json([EXTRACT_RULES], f"선수: {topic['player']} ({topic.get('team', '')}, {topic.get('sport', '')})\n"
                          f"오늘: {today}\n\n뉴스 요약 (번호 = source):\n{news_prompt(news)}",
                          EXTRACT_SCHEMA, max_tokens=8000, **extract_opts())
        if not ex["usable"]:
            notes.append(f"{topic['player']}: 건너뜀 — {ex['reason']}")
            continue
        facts = resolve(ex["facts"], news)
        d, why = build_data(topic, ex, facts, cfg)
        if d is None:
            notes.append(f"{topic['player']}: 건너뜀 — {why}")
            continue
        folder = out_root / f"{today}-{topic['id']}"
        folder.mkdir(parents=True, exist_ok=True)
        n = receipt.build(folder, d)
        sheet = number_sheet(d, n, facts, ex, cfg)
        queue = [t for t in cfg.get("queue", []) if t["id"] != topic["id"]
                 and not any(x.endswith("-" + t["id"]) for x in done_ids())]
        post, problems, rounds = write_post(llm, topic, sheet, queue[0] if queue else None, cfg.get("max_revisions", 2))
        cost = llm.cost_usd()
        (folder / "data.yaml").write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (folder / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
        (folder / "body.txt").write_text(post["body"].strip() + "\n", encoding="utf-8")
        (folder / "post.md").write_text(package_md(topic, d, facts, post, problems, rounds, cfg, news, cost), encoding="utf-8")
        if out_root == POSTS:
            write_index()
        head = "✅ 발행 가능" if not problems and post["gate_pass"] else "⚠️ 확인 필요: " + "; ".join(problems or ["게이트 미통과"])
        return "\n".join(notes + [f"{topic['player']} 글 완성 — {head}"]), folder
    return "\n".join(notes + ["쓸 수 있는 주제를 찾지 못했습니다. 대기열(config/post_queue.yaml)에 선수를 추가해 주세요."]), None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="키 없이 가짜 뉴스·가짜 응답으로 모양만 확인")
    ap.add_argument("--topic", default=None)
    ap.add_argument("--out", default=None, help="결과 폴더 (기본 posts/)")
    a = ap.parse_args()
    today = date.today().isoformat()
    out_root = Path(a.out) if a.out else POSTS
    if a.sample:
        from .sample_post import FakeClaude, FakeNewsHub
        hub, llm = FakeNewsHub(), FakeClaude()
        a.topic = a.topic or "예시선수"
    else:
        miss = missing_secrets("anthropic") + missing_secrets("naver_hub")
        if miss:
            print(f"키가 없어 실행하지 않았습니다: {', '.join(miss)} (GitHub Secrets에 등록 필요)")
            _summary(f"⚠️ 키가 없어 글을 쓰지 않았습니다: {', '.join(miss)}")
            return
        from market.naver_hub import ApiHub
        from .llm import Claude
        hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
        llm = Claude()
    try:
        msg, folder = run(hub, llm, today=today, topic_override=a.topic, out_root=out_root)
    except Exception as e:  # 키·요금·API 오류: 메시지만 남기고 실패로 끝낸다 (키 값은 메시지에 없음)
        _summary(f"❌ 글쓰기 실패: {type(e).__name__}: {str(e)[:300]}\n\nClaude에게 이 화면을 알려주세요.")
        raise
    if hasattr(llm, "usage"):
        u = llm.usage
        msg += (f"\nClaude 호출 {u['calls']}회 · 입력 {u['input']:,} · 출력 {u['output']:,} · 캐시 읽기 {u['cache_read']:,} 토큰"
                f" · 약 ${llm.cost_usd():.2f}")
    print(msg)
    if folder:
        print(f"결과: {folder}")
    _summary(msg + (f"\n\n결과 폴더: `{folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder}`" if folder else ""))


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("## 자동 글쓰기\n\n" + text.replace("\n", "  \n") + "\n")


if __name__ == "__main__":
    main()
