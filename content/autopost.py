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
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from market.common import ROOT, load_yaml, missing_secrets
from . import cards, clip, photos, receipt, themes
from .receipt import won
from .voice import check_draft

POSTS = ROOT / "posts"
SKILLS = ROOT / ".claude" / "skills"
EXAMPLE_POST = POSTS / "2026-10-01-이정후-영수증" / "post.md"
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
IMAGES = ("thumb.png", "card_quiz.png", "card_answer.png", "card_wage.png", "card_table.png")
QUIZ = re.compile(r"^퀴즈 카드: (.+?) 맞히기 \(정답 (.+?)\)", re.M)
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

PRICE_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "price_krw": {"type": "integer"},
        "deal_date": {"type": "string"},
        "source": {"type": "integer"},
    },
    "required": ["found", "price_krw", "deal_date", "source"],
    "additionalProperties": False,
}

PRICE_RULES = """너는 부동산 기사 요약문에서 실거래가 하나를 뽑는 도우미다.
- 요청한 단지의 전용 84㎡ '매매' 실거래가 중 거래일이 가장 최근인 것 하나만 고른다.
- 호가·전세·월세·분양가·입주권·평균값·다른 면적·다른 단지는 쓰지 않는다. 확실하지 않으면 found=false.
- price_krw는 원 단위 정수 (예: 34억3000만원 → 3430000000). 기사에 적힌 숫자만 쓰고 계산·추측하지 않는다.
- deal_date는 기사에 적힌 거래 날짜 (YYYY-MM-DD 또는 YYYY-MM, 없으면 빈 문자열). source는 기사 번호 [n].
"""

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
- 계약 총액·지급 유예 금액처럼 글에 필요한 다른 돈도 facts로 뽑는다 (key 예: contract_total, deferred, unit은 USD 또는 KRW). 원화 환산은 코드가 한다.
- salary_basis: 연봉 근거를 한 줄로, 금액 숫자 없이 (예: "6년 계약 중 2026년 연봉, 보도 기준", "10년 계약, 대부분 지급 유예"). 금액은 facts에만.
- usable=false: 올해 연봉 또는 나눌 기록이 요약문에 없을 때. reason에 무엇이 없는지 적는다.
- 사용자가 준 '종목 안내'가 있으면 따른다 (예: 골프는 연봉 대신 올해 상금).
"""

WRITE_RULES = """너는 네이버 블로그 "억소리 나는 스포츠"(닉네임 백억소리)의 글쓴이다. 목표는 홈판에서 눌리고 끝까지 읽히는 글이다.
위의 두 스킬 문서(blog-voice, money-content-writer)를 따른다. 특히 아래는 반드시 지킨다.

숫자
- 돈은 모두 원화로 쓴다 (달러 금액은 숫자표의 원화 환산값). "달러"라는 말은 마지막 "기준:" 문단의 환율 설명에만 쓴다.
- 글과 제목에는 사용자가 준 '숫자표'에 있는 숫자만 쓴다. 새로 계산하거나 반올림해서 키우지 않는다.
- 줄여 쓰기는 버림만 허용: "2억 32만원" → "2억", "298억 4,740만원" → "약 298억원".
- 금액은 붙여 쓴다: "9,045만원", "27억원", "2억 32만원" ("만 원", "억 원"처럼 띄우지 않는다).
- 출처끼리 차이가 있다고 표시된 숫자는 본문에 "보도에 따라 약간 차이가 있어요"를 한 번 적는다.

구조 (홈판형)
- 첫 줄은 제목의 답이 되는 숫자 한 줄. 제목에서 던진 숫자는 본문 첫 화면에서 회수한다.
- 문단은 3문장 이하, 짧은 문장과 긴 문장을 섞는다. 질문 2~4개. 최저임금 같은 교차 비교 1번.
- 이미지는 숫자표의 '이미지 자리' 목록대로, 각 줄을 따옴표 안 모양 그대로 한 줄씩 순서대로 넣는다 (카드에 쪽 번호가 있어 순서를 지킨다).
- 끝에서 둘째 문단: 다음에 계산해 볼 선수를 댓글로 묻는 질문 한 줄. 특정 선수 이름으로 다음 글을 약속하지 않는다 (그 선수 숫자가 안 모이면 못 쓴다).
- 마지막 문단: "기준: ..."으로 연봉·성적·환율·최저임금의 기준일과 출처 종류를 한 문장으로.

금지
- 기사 문장·표현 복사, 경쟁 글 흉내. 요약된 사실만 네 말로.
- 가짜 경험("직접 봤다", "경기장에서"), 사생활·연애·가족·논란·개인 재산, 도박(배당·토토), 투자 권유.
- "알아보겠습니다", "결론적으로", "다양한", "것입니다" 같은 AI 티 표현 (voice 검사에서 걸린다).
- 마크다운 기호(#, **, 표). 네이버 에디터에 그대로 붙여 넣을 일반 텍스트로 쓴다.

출력
- gate_pass: 숫자표로 '새로 계산한 숫자'라는 정보 이득을 만들 수 있으면 true. info_gain에 한 줄.
- titles 5개, 유형을 모두 다르게. recommended는 추천 제목 번호(1~5).

제목 (홈판에서는 썸네일 + 제목만 보고 누를지 정한다. 가장 공들일 것)
- 5개 모두 숫자표의 '제목용 짧은 이름'으로 시작한다 (검색 유입 + 스타 이름으로 눈길). 성+이름 전체를 쓰지 않는다.
- 추천 제목은 짧은 이름 + 숫자 후킹 (예: "오타니 9,496억 계약인데 올해 27억?", "이정후 298억, 시즌 끝나도 다 받을까?"). 숫자로 반전·궁금증을 만든다.
- 썸네일 금액(숫자표 '썸네일' 줄)은 추천 제목에 되풀이하지 않는다. 썸네일은 "얼마", 제목은 "왜?".
- 25자 이하 (띄어쓰기 포함). 던진 궁금증은 본문에서 반드시 답한다. 선수 이름은 태그에도 넣는다.
- 물음표는 1개까지. "충격", "경악", "헉", "소름", "역대급" 같은 과장어 금지.
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


def eok_text(krw: int) -> list[str]:
    """기사에 그 가격이 실제로 적혀 있는지 볼 때 찾을 표기 (34억3000만 / 34억3천만 / 34억 3,000만 ...)."""
    e, m = divmod(krw // 10_000, 10_000)
    if not m:
        return [f"{e}억"]
    c = f"{m // 1000}천" if m % 1000 == 0 else None
    return [f"{e}억{x}만" for x in (str(m), f"{m:,}", c) if x]


def fill_prices(hub, llm, items: list[dict], today: str, fallback: dict | None) -> tuple[list[dict], list[str]]:
    """fetch: news 물건은 글 쓰는 날 뉴스에서 전용 84㎡ 최근 매매 실거래가를 뽑는다 (Claude가 고르고 코드가 확인).
    기사에 없는 숫자·범위 밖·6개월 넘은 기사면 버리고 서울 평균(fallback)으로 대신한다."""
    out, notes = [], []
    for it in items:
        if it.get("fetch") != "news":
            out.append(it)
            continue
        got, why = None, "관련 기사 없음"
        news = [n for n in gather_news(hub, [it["query"]], per_query=15)
                if (date.fromisoformat(today) - date.fromisoformat(n["date"])).days <= 180]
        if news:
            r = llm.ask_json([PRICE_RULES], f"단지: {it['label']}\n오늘: {today}\n\n기사\n{news_prompt(news)}",
                             PRICE_SCHEMA, max_tokens=1000, **extract_opts())
            src = news[r["source"] - 1] if 1 <= r["source"] <= len(news) else None
            text = (src["title"] + " " + src["description"]).replace(" ", "") if src else ""
            if not r["found"] or not src:
                why = "기사에서 84㎡ 매매 실거래가를 찾지 못함"
            elif not it.get("min_krw", 0) <= r["price_krw"] <= it.get("max_krw", 10**13):
                why = f"범위 밖 가격 ({won(r['price_krw'])})"
            elif not any(x.replace(",", "") in text.replace(",", "") for x in eok_text(r["price_krw"])):
                why = f"기사에 없는 숫자 ({won(r['price_krw'])})"
            else:
                d = r["deal_date"] if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", r["deal_date"]) else src["date"]
                got = {**it, "price_krw": r["price_krw"], "as_of": d if len(d) == 10 else d + "-01",
                       "source": f"실거래가 보도 ({src['date']}, {won(r['price_krw'])}) {src['link']}"}
        if got:
            out.append(got)
        else:
            notes.append(f"{it['short']} 가격 못 씀 ({why}) → 서울 아파트 평균으로 대신")
            if fallback and all(x["key"] != fallback["key"] for x in out + items):
                out.append(fallback)
    return out, notes


def done_ids() -> set[str]:
    return {p.name for p in POSTS.iterdir() if p.is_dir()} if POSTS.exists() else set()


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


def season_card(facts: dict, unit_keys: list[str]) -> tuple[list[dict], str]:
    """시즌 성적 카드 (최대 6칸): 연봉을 나눈 기록 먼저, 그다음 나머지 기록."""
    keys = [k for k in unit_keys if k in facts] + [k for k in facts if k not in unit_keys
                                                     and k not in ("salary", "fx_krw_per_usd")]
    card = []
    for k in keys[:6]:
        v = facts[k]["value"]
        card.append({"label": facts[k].get("label", k), "value": f"{int(v):,}" if float(v).is_integer() else f"{v}"})
    dates = [facts[k].get("date", "") for k in keys[:6]]
    return card, max(dates) if dates else ""


def build_data(topic: dict, ex: dict, facts: dict, cfg: dict) -> tuple[dict | None, str]:
    """receipt.py 입력을 만든다. 모자라거나 말이 안 되는 숫자면 (None, 이유)."""
    sal = facts.get("salary")
    if not sal:
        return None, "올해 연봉을 찾지 못함"
    usd = ex["salary_currency"] == "USD"
    if usd and not 1e5 <= sal["value"] <= 1e8 or not usd and not 3e7 <= sal["value"] <= 1e11:
        return None, f"연봉 숫자가 이상함 ({sal['value']:,} {ex['salary_currency']})"
    d = {"player": topic["player"], "short_name": topic.get("short_name") or topic["player"].split(" ")[0],
         "team": topic.get("team", ""), "season": ex["season"],
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
    d["salary_basis"] = ex["salary_basis"]
    d["min_wage_monthly_krw"] = cfg["constants"]["min_wage_monthly_krw"]
    d["sport"] = topic.get("sport", "야구")
    head = ex["headline_unit"]  # 제목에 쓴 기록을 카드 첫 칸(금색)에
    d["card"], d["card_date"] = season_card(facts, sorted((u["key"] for u in units), key=lambda k: k != head))
    return {k: v for k, v in d.items() if v is not None}, ""


def number_sheet(d: dict, n: dict, facts: dict, ex: dict, cfg: dict) -> str:
    """글에 쓸 수 있는 숫자 전부. 글쓰기 검사도 이 표를 기준으로 한다."""
    head = receipt.headline(d)
    head_label = next(u["label"] for u in receipt.units(d) if u["key"] == head)
    L = [f"선수: {d['player']} ({d.get('team', '')}), 시즌 {d['season']}",
         f"제목용 짧은 이름: {d.get('short_name') or d['player'].split(' ')[0]}",
         f"썸네일: {d['player']} / {head_label} / {receipt.short_won(n['per'][head])} (추천 제목에는 이 금액을 다시 쓰지 않는다)"]
    fx = d.get("fx_krw_per_usd")
    L.append(f"올해 연봉: {won(n['salary_krw'])}" + (f" (달러 연봉을 {d['fx_label']} 환율로 환산)" if fx else ""))
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
        if f["unit"] == "USD":  # 달러 금액은 원화로만 보여준다 (대표 결정: 통화는 원화로)
            if not fx:
                continue
            L.append(f"- {f['label']}: 약 {won(f['value'] * fx)} (지금 환율로 환산 · {f['date']})")
            continue
        if f["unit"] == "KRW":
            L.append(f"- {f['label']}: {won(f['value'])} ({f['date']} · {f['rule']})")
            continue
        v = f"{f['value']:,}" if float(f["value"]).is_integer() else f"{f['value']}"
        diff = f" · 출처끼리 차이 {f['differs']} → 본문에 '보도에 따라 약간 차이' 표기" if f["differs"] else ""
        L.append(f"- {f['label']}: {v}{f['unit'] if f['unit'] not in ('KRW', 'USD') else ''} ({f['date']} · {f['rule']}){diff}")
    q = cards.quiz_unit(d, receipt.units(d), n["per"], receipt.headline(d))
    L.append(f"퀴즈 카드: {q['label']} 1번에 받는 돈 맞히기 (정답 {won(n['per'][q['key']])})")
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


TITLE_MAX = 25  # 짧은 이름 + 숫자 후킹 (대표 결정)
SHORT = re.compile(r"^제목용 짧은 이름: (\S+)", re.M)
TITLE_BANNED = ["충격", "경악", "헉", "소름", "역대급"]
THUMB = re.compile(r"^썸네일: (.+?) / (.+?) / (\S+?)원? \(", re.M)


def check_titles(p: dict, sheet: str) -> list[str]:
    """제목 규칙: 짧은 이름으로 시작, 25자 이하, 과장어 금지, 추천 제목은 숫자 후킹 + 썸네일 금액 되풀이 금지."""
    m = THUMB.search(sheet)
    if not m or not p["titles"]:
        return []
    name, money = m.group(1), m.group(3)
    s = SHORT.search(sheet)
    core = s.group(1) if s else name.split(" ")[0]  # '오타니 쇼헤이' → '오타니'
    out = []
    for i, t in enumerate(p["titles"], 1):
        text = t["text"].strip()
        if not text.startswith(core):
            out.append(f"제목{i}이 짧은 이름({core})으로 시작하지 않음")
        elif name != core and text.startswith(name):
            out.append(f"제목{i}에 긴 이름 → '{core}'로")
        if len(text) > TITLE_MAX:
            out.append(f"제목{i}이 {TITLE_MAX}자 넘음 ({len(text)}자)")
        if text.count("?") > 1 or any(w in text for w in TITLE_BANNED):
            out.append(f"제목{i}에 물음표 여러 개 또는 과장어")
    rec = p["titles"][p["recommended"] - 1]["text"] if 1 <= p["recommended"] <= len(p["titles"]) else ""
    if money.removesuffix("원") in rec.replace(" ", ""):
        out.append(f"추천 제목이 썸네일 금액({money})을 되풀이함 → 반전·궁금증 한 마디로")
    if not re.search(r"\d", rec):
        out.append("추천 제목에 숫자가 없음 → 이름 + 숫자 후킹으로")
    if not any(core in t for t in p.get("tags", [])) and p.get("tags") is not None:
        out.append(f"태그에 선수 이름({core}) 없음")
    return out


def check_post(p: dict, sheet: str) -> list[str]:
    problems = list(check_draft(p["body"]))
    for label, text in [("본문", p["body"])] + [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]:
        bad = unknown_numbers(text, sheet)
        if bad:
            problems.append(f"{label}에 숫자표에 없는 숫자: {', '.join(bad)}")
    m_img = re.search(r"^이미지 파일: (.+)$", sheet, re.M)
    for img in ([x.strip() for x in m_img.group(1).split(",")] if m_img else IMAGES):
        if img not in p["body"]:
            problems.append(f"이미지 자리 {img} 없음")
    hit = [w for w in BANNED if w in p["body"]]
    if hit:
        problems.append(f"금지 주제 단어: {', '.join(hit)}")
    problems += check_titles(p, sheet)
    if len(p["titles"]) != 5 or not 1 <= p["recommended"] <= len(p["titles"]):
        problems.append("제목 5개와 추천 번호(1~5)가 필요")
    for label, text in [("본문", "\n".join(l for l in p["body"].splitlines() if not l.startswith("기준")))] + \
            [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]:
        if "달러" in text:
            problems.append(f"{label}에 '달러' → 원화로 (환율은 '기준:' 문단에만)")
    m = QUIZ.search(sheet)
    if m and "card_quiz.png" in p["body"]:
        before = p["body"].split("card_quiz.png")[0]
        if m.group(2) in before or m.group(2).removesuffix("원") in before:
            problems.append(f"퀴즈 정답({m.group(2)})이 퀴즈 카드보다 먼저 나옴 → 정답 카드 뒤로")
    if "card_answer.png" in p["body"] and "card_quiz.png" in p["body"] and \
            p["body"].index("card_answer.png") < p["body"].index("card_quiz.png"):
        problems.append("정답 카드가 퀴즈 카드보다 앞에 있음")
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


def write_post(llm, topic: dict, sheet: str, max_revisions: int) -> tuple[dict, list[str], int]:
    w = llm_cfg().get("write", {})
    cap = llm_cfg().get("cost_cap_usd_per_post", 1.0)
    opts = {"model": w.get("model", "claude-sonnet-5-5"), "effort": w.get("effort", "medium")}
    system = writer_system()
    prompt = (f"카테고리: {topic['category']}\n글 방향: {topic['angle']}\n\n숫자표\n{sheet}\n\n"
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

def package_md(title: str, theme: str, category: str, facts: dict, post: dict, problems: list[str], rounds: int,
               cfg: dict, news_count: int, cost: float | None, extra_sources: list[str] = ()) -> str:
    rec = post["recommended"]
    status = "✅ 자동 검사 통과" if not problems and post["gate_pass"] else "⚠️ 검사 미통과 — 발행하지 말고 Claude에게 알려주세요"
    out = [f"# 발행 패키지 · {title}", "",
           f"**상태:** {status}  ", f"**게이트:** {'통과' if post['gate_pass'] else '미통과'} — 정보 이득: {post['info_gain']}  ",
           f"**자동 작성:** Claude 초안 → 코드 검사 (고쳐 쓰기 {rounds}회)" + (f" · API 비용 약 ${cost:.2f}" if cost else ""), ""]
    if problems:
        out += ["**남은 문제:**", ""] + [f"- {p}" for p in problems] + [""]
    out += ["## 제목 (추천 ★)", ""]
    out += [f"{i}. {'★ ' if i == rec else ''}{t['text']} — {t['type']}" for i, t in enumerate(post["titles"], 1)]
    plan = themes.image_plan(theme)
    out += ["", "## 이미지 (본문 [이미지] 자리에 넣기)", "", "| 순서 | 파일 | 위치 | 대표이미지 |", "| --- | --- | --- | --- |"]
    out += [f"| {i} | {f} | {lab} | {'✅ 대표이미지로 지정' if i == 1 else ''} |" for i, (lab, f, _) in enumerate(plan, 1)]
    out += ["", "## 카테고리 · 태그", "", f"- 카테고리: **{category}**", f"- 태그: {', '.join(post['tags'][:10])}", "",
            "## 본문 (복사해서 붙여넣기, [이미지 …] 줄은 지우고 그 자리에 사진 넣기)", "", post["body"].strip(), "",
            "## 출처", ""]
    links = sorted({l for f in facts.values() for l in f["sources"]})
    out += [f"- {l}" for l in links] + [f"- {x}" for x in extra_sources]
    out += [f"- 최저임금: {cfg['constants']['min_wage_source']}", ""]
    out += ["## 팩트체크 목록 (코드가 정한 값)", "", "| 수치 | 값 | 기사 날짜 | 정한 규칙 |", "| --- | --- | --- | --- |"]
    for k, f in facts.items():
        diff = f" (출처별 {', '.join(map(str, f['differs']))})" if f["differs"] else ""
        out.append(f"| {f['label']} | {f['value']:,} {f['unit']} | {f['date']} | {f['rule']}{diff} |")
    out += ["| 계산한 금액 | numbers.json | - | 코드 계산 |", "",
            "## 실험 기록용", "",
            f"- 테마: {theme} · 추천 제목 유형: {post['titles'][rec - 1]['type']} · 교차 비교: {post['cross_compare']}"
            f" · 이미지 {len(plan)} · 참고 기사 {news_count}건", ""]
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


def collect(hub, llm, topic: dict, today: str, cfg: dict) -> dict | str:
    """한 선수의 뉴스 → 숫자 뽑기 → 충돌 정리 → 계산 입력. 모자라면 이유(str)를 돌려준다."""
    news = gather_news(hub, topic["queries"] + [cfg["fx_query"]])
    hint = f"\n종목 안내: {topic['hint']}" if topic.get("hint") else ""
    ex = llm.ask_json([EXTRACT_RULES], f"선수: {topic['player']} ({topic.get('team', '')}, {topic.get('sport', '')}){hint}\n"
                      f"오늘: {today}\n\n뉴스 요약 (번호 = source):\n{news_prompt(news)}",
                      EXTRACT_SCHEMA, max_tokens=8000, **extract_opts())
    if not ex["usable"]:
        return ex["reason"]
    facts = resolve(ex["facts"], news)
    d, why = build_data(topic, ex, facts, cfg)
    if d is None:
        return why
    return {"d": d, "facts": facts, "ex": ex, "news": news}


def recent_players(k: int) -> set[str]:
    names = set()
    for f in sorted((x for x in POSTS.iterdir() if (x / "data.yaml").exists()), reverse=True)[:k] if POSTS.exists() else []:
        names |= set(themes.names_in(yaml.safe_load((f / "data.yaml").read_text(encoding="utf-8")) or {}))
    return names


def strip_lines(sheet: str, *prefixes: str) -> str:
    return "\n".join(l for l in sheet.splitlines() if not l.startswith(prefixes))


def theme_sheet(plan: dict, d: dict, n: dict, got: list[dict], cfg: dict) -> str:
    th = plan["theme"]
    if th == "receipt":
        return number_sheet(d, n, got[0]["facts"], got[0]["ex"], cfg)
    if th in ("same", "cross"):
        A, B = (x["d"].get("short_name") or x["d"]["player"] for x in got)
        win, lose = (A, B) if n["winner"] == "a" else (B, A)
        L = [f"비교: {A} vs {B} ({'같은 종목' if th == 'same' else '다른 종목'})",
             f"제목용 짧은 이름: {A}",
             f"썸네일: {A} vs {B} / 올해 연봉 / {receipt.short_won(n['a']['salary_krw'])} (추천 제목에는 이 금액을 다시 쓰지 않는다)",
             f"{A} 올해 연봉: {won(n['a']['salary_krw'])}", f"{B} 올해 연봉: {won(n['b']['salary_krw'])}",
             f"연봉 차이: {themes.ratio(n['salary_ratio'])}배",
             f"{n['unit_label']} 몸값: {A} {won(n['va'])} / {B} {won(n['vb'])} → {win}이 {lose}의 {themes.ratio(n['ratio'])}배",
             f"퀴즈 카드: {n['unit_label']} 몸값 누가 더 비쌀까 (정답 카드 전에는 누가 더 받는지 쓰지 않는다)"]
        for x, key in zip(got, ("a", "b")):
            L += ["", f"[{x['d'].get('short_name') or x['d']['player']} 상세]",
                  strip_lines(number_sheet(x["d"], n[key], x["facts"], x["ex"], cfg), "썸네일:", "제목용", "퀴즈 카드:")]
        return "\n".join(L)
    q = n["item"]
    L = [strip_lines(number_sheet(d, n, got[0]["facts"], got[0]["ex"], cfg), "썸네일:", "퀴즈 카드:"),
         f"썸네일: {d.get('short_name') or d['player']} / 올해 연봉이면 / {q['short']} {themes.count(q['salary_count'])}{q['unit']}"
         " (추천 제목에는 이 숫자를 다시 쓰지 않는다)",
         f"비교 물건 (글 전체에서 이것 하나만 쓴다): {q['label']} {won(q['price_krw'])} ({q['as_of']} 기준)",
         f"{q['short']}로 바꾸면 (개수는 버림):"]
    L += [f"- {r['label']} {won(r['value'])} → {themes.count(r['count'])}{q['unit']}" for r in n["rows"]]
    if n["inverse"]:
        L.append(f"{q['short']} 한 {q['unit']} 사려면 (버림):")
        L += [f"- {r['label']}로 {themes.count(q['price_krw'] / r['value'])}{'년' if r['key'] == 'salary' else cards.word(r['label'])}"
              for r in n["rows"]]
    if n["inverse"]:
        L.append(f"{q['short']} 한 {q['unit']} 사려면: {n['life_label']} 몸값 {won(n['life_per'])}로 {themes.count(n['inverse_count'])}{n['inverse_word']}")
        L.append(f"퀴즈 카드: {q['short']} 한 {q['unit']} 사려면 몇 {n['inverse_word']} 맞히기 (정답 {themes.count(n['inverse_count'])}{n['inverse_word']})")
    else:
        L.append(f"퀴즈 카드: {n['life_label']} 몸값으로 {q['short']} 몇 {q['unit']} 맞히기 (정답 {themes.count(q['unit_count'])}{q['unit']})")
    return "\n".join(L)


def run(hub, llm, *, today: str, topic_override: str | None = None, theme: str | None = None,
        out_root: Path = POSTS) -> tuple[str, Path | None]:
    cfg = load_yaml("post_queue.yaml")
    pool = load_yaml("players.yaml")
    if not topic_override and not theme and out_root == POSTS:
        today_made = [p for p in done_ids() if p.startswith(today)
                      and "**자동 작성:**" in (POSTS / p / "post.md").read_text(encoding="utf-8", errors="ignore")
                      if (POSTS / p / "post.md").exists()]
        if len(today_made) >= cfg.get("daily_limit", 1):
            return f"오늘 이미 {len(today_made)}편을 만들었습니다 (하루 한도 {cfg.get('daily_limit', 1)}편).", None
    notes: list[str] = []
    cache: dict[str, dict | str] = {}
    for plan in themes.plans(pool, recent_players(pool.get("recent_posts", 5)), today, n=5,
                             override=topic_override, theme=theme):
        got = []
        for p in plan["players"]:
            if p["name"] not in cache:
                cache[p["name"]] = collect(hub, llm, themes.topic(pool, p), today, cfg)
            got.append(cache[p["name"]])
        bad = [f"{p['name']}: {g}" for p, g in zip(plan["players"], got) if isinstance(g, str)]
        if bad:
            notes += [f"건너뜀 — {b}" for b in bad if b not in notes]
            continue
        th = plan["theme"]
        tinfo = pool["themes"][th]
        if th in ("same", "cross"):
            d = {"theme": th, "season": got[0]["d"]["season"], "sport": got[0]["d"].get("sport", "야구"),
                 "a": got[0]["d"], "b": got[1]["d"]}
            facts = {f"{k}.{key}": {**f, "label": f"{x['d'].get('short_name') or x['d']['player']} {f['label']}"}
                     for k, x in zip("ab", got) for key, f in x["facts"].items()}
        else:
            d = {**got[0]["d"], "theme": th}
            facts = got[0]["facts"]
            if th == "life":
                prices = load_yaml("prices.yaml")
                fallback = next((i for i in prices["items"] if i["key"] == "seoul_apt"), None)
                d["prices"], pn = fill_prices(hub, llm, themes.pick_prices(prices, f"{today}-{d['player']}"),
                                              today, fallback)
                notes += pn
                old = [i["short"] for i in d["prices"] if (date.fromisoformat(today) - date.fromisoformat(str(i["as_of"]))).days > 180]
                if old:
                    notes.append(f"가격 확인 필요 (6개월 넘음): {', '.join(old)} → config/prices.yaml")
        title = themes.title_name(d)
        slug = "-".join(x["d"].get("short_name", x["d"]["player"]).replace(" ", "") for x in got)
        folder = out_root / f"{today}-{th}-{slug}"
        folder.mkdir(parents=True, exist_ok=True)
        photos.fetch_all(folder, d.get("sport", "야구"), folder.name)  # 키가 없으면 사진 없이
        n = themes.build(folder, d)
        sheet = theme_sheet(plan, d, n, got, cfg) + "\n" + "\n".join(themes.image_lines(th))
        post, problems, rounds = write_post(llm, {"category": tinfo["category"], "angle": tinfo["angle"]}, sheet,
                                            cfg.get("max_revisions", 2))
        cost = llm.cost_usd()
        (folder / "data.yaml").write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (folder / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
        if photos.credit(folder):  # Pexels 이용 조건: 작가·Pexels 표시 (숫자 검사 뒤에 붙인다)
            post["body"] = post["body"].strip() + "\n\n" + photos.credit(folder)
        (folder / "body.txt").write_text(post["body"].strip() + "\n", encoding="utf-8")
        extra = [f"{i['label']}: {i['source']}" for i in d.get("prices", [])]
        (folder / "post.md").write_text(package_md(f"{title} · {tinfo['name']}", th, tinfo["category"], facts, post,
                                                   problems, rounds, cfg, sum(len(x["news"]) for x in got), cost, extra),
                                        encoding="utf-8")
        try:  # 네이버 클립용 세로 영상 (실패해도 글은 그대로)
            notes.append(clip.make(folder))
        except Exception as ex:
            notes.append(f"클립: 오류로 건너뜀 ({ex})")
        if out_root == POSTS:
            write_index()
        head = "✅ 발행 가능" if not problems and post["gate_pass"] else "⚠️ 확인 필요: " + "; ".join(problems or ["게이트 미통과"])
        return "\n".join(notes + [f"{title} ({tinfo['name']}) 글 완성 — {head}"]), folder
    return "\n".join(notes + ["쓸 수 있는 조합을 찾지 못했습니다 (연봉 보도가 있는 선수 부족). config/players.yaml 확인 필요."]), None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="키 없이 가짜 뉴스·가짜 응답으로 모양만 확인")
    ap.add_argument("--topic", default=None, help="선수 이름 (비우면 선수 풀에서 무작위)")
    ap.add_argument("--theme", default=None, choices=["receipt", "same", "cross", "life"], help="테마 고정 (비우면 무작위)")
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
        msg, folder = run(hub, llm, today=today, topic_override=a.topic, theme=a.theme, out_root=out_root)
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
