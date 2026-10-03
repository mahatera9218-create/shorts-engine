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
import random
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from market.common import ROOT, load_yaml, missing_secrets
from . import cards, clip, mark, marketers, photos, ranking, receipt, themes
from .desk import clean_tags
from .receipt import won
from .voice import check_draft, human_gaps

POSTS = ROOT / "posts"
# 외화 연봉 (2026-09-30: EPL·라리가·NBA 추가). 금액은 그날 환율로 원화 환산만 보여 주고, 통화 이름은 '기준:' 문단에만.
FX = {"USD": {"word": "달러", "key": "fx_krw_per_usd", "range": (900, 2500), "salary": (1e5, 1.5e8)},
      "EUR": {"word": "유로", "key": "fx_krw_per_eur", "range": (1000, 2800), "salary": (1e5, 1.5e8)},
      "GBP": {"word": "파운드", "key": "fx_krw_per_gbp", "range": (1200, 3200), "salary": (1e5, 1.5e8)}}
SKILLS = ROOT / ".claude" / "skills"
EXAMPLE_POST = SKILLS / "blog-voice" / "example-post.md"  # 말투·길이 참고용 (대표가 좋다고 한 첫 글, 예고 문장 제거)
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
IMAGES = ("thumb.png", "card_quiz.png", "card_answer.png", "card_wage.png", "card_table.png")
QUIZ = re.compile(r"^퀴즈 카드: (.+?) 맞히기 \(정답 (.+?)\)", re.M)
TEASER = re.compile(r"다음\s*(글|편|영수증|포스팅|포스트|시간|회차|이야기|주인공|차례|대결)|다음\s*번\s*글|다음엔\s*\S+\s*(선수|연봉|몸값)(을|를|의|으로|로)?\s*(다룰|쪼갤|계산|알아)")
BANNED = ["토토", "프로토", "배당", "베팅", "배팅", "열애", "여자친구", "남자친구", "이혼", "루머", "인성 논란"]

# ---------------------------------------------------------------- 스키마

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "usable": {"type": "boolean"},
        "reason": {"type": "string"},
        "season": {"type": "integer"},
        "salary_currency": {"type": "string", "enum": ["USD", "EUR", "GBP", "KRW"]},
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

TITLE_TYPES = ["숫자형", "대비형", "순위형", "반전형", "질문형"]
BRIEF_KEYS = {"reader": "독자", "reader_question": "독자의 질문", "promise": "제목·썸네일의 약속",
              "payoff": "본문에서 회수하는 곳", "only_here": "이 글에만 있는 것", "takeaway": "읽고 남는 한 줄",
              "why_naver": "네이버·광고주 기대에 맞는 이유",
              "ad_fit": "기대하는 광고 묶음과 그걸 부르는 문맥"}

PRODUCT_RULES = """너는 상품 기사 요약문에서 이 제품의 현재 판매가 하나를 뽑는 도우미다 (당일 검색량 상위 소비재, 2026-10-03).
- 요청한 제품(모델·용량이 맞는 것)의 **출고가·시작가·공식가·최저가** 중 하나를 원화 정수로.
- 중고가·할부 월 납입금·보상/카드 할인가·해외가는 쓰지 않는다. 모델이 다르면 found=false.
- price_krw는 원 단위 정수 (예: 150만원 → 1500000). 기사에 적힌 숫자만, 계산·추측 금지.
- deal_date는 기사 날짜(YYYY-MM 또는 YYYY-MM-DD, 없으면 빈 문자열). source는 기사 번호 [n].
"""


REGION_RULES = """너는 부동산 기사 요약문에서 지역 아파트 평균 매매가격 하나를 뽑는 도우미다.
- 요청한 지역(시·광역시) 전체의 아파트 평균 매매가격(한국부동산원·KB부동산 통계를 인용한 보도)만 쓴다.
- 중위가격·전세·월세·분양가·특정 단지·구 단위·㎡당(평당) 가격·다른 지역은 쓰지 않는다. 확실하지 않으면 found=false.
- price_krw는 원 단위 정수. 기사에 적힌 숫자만 쓰고 계산·추측하지 않는다.
- deal_date는 통계 기준 월 (YYYY-MM, 없으면 빈 문자열). source는 기사 번호 [n].
"""

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "brief": {"type": "object", "properties": {k: {"type": "string"} for k in BRIEF_KEYS},
                  "required": list(BRIEF_KEYS), "additionalProperties": False},
        "gate_pass": {"type": "boolean"},
        "info_gain": {"type": "string"},
        "titles": {"type": "array", "items": {
            "type": "object",
            "properties": {"text": {"type": "string"},
                           "type": {"type": "string", "enum": TITLE_TYPES}},
            "required": ["text", "type"], "additionalProperties": False}},
        "recommended": {"type": "integer"},
        "body": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "cross_compare": {"type": "string"},
        "clip_caption": {"type": "string"},
        "clip_question": {"type": "string"},
    },
    "required": ["brief", "gate_pass", "info_gain", "titles", "recommended", "body", "tags", "cross_compare",
                 "clip_caption", "clip_question"],
    "additionalProperties": False,
}

REVIEW_CRITERIA = ["약속 회수", "새 정보", "머무를 이유", "신뢰", "남는 한 줄", "광고주 안전", "사람 말투"]
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {"type": "array", "items": {
            "type": "object",
            "properties": {"criterion": {"type": "string", "enum": REVIEW_CRITERIA},
                           "score": {"type": "integer"}, "reason": {"type": "string"}},
            "required": ["criterion", "score", "reason"], "additionalProperties": False}},
        "fixes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["scores", "fixes"],
    "additionalProperties": False,
}
REVIEW_PASS = 4     # 4점 미만 기준이 있으면 한 번 고쳐 쓴다
REVIEW_FLOOR = 2    # 고쳐 쓴 뒤 2점 이하가 있거나
REVIEW_MEAN = 3.5   # 평균이 3.5 미만이면 기준 미달 (대표 결정 2026-10-01 비용 효율: 전부 4점 이상만 통과시키니 9편 중 1편만 남음)


def review_ok(scores: list[dict]) -> bool:
    vals = [x["score"] for x in scores]
    return bool(vals) and min(vals) > REVIEW_FLOOR and sum(vals) / len(vals) >= REVIEW_MEAN

REVIEW_RULES = """너는 네이버 블로그 "억소리 나는 스포츠"의 편집장이다. 위 스킬 문서의 0단계(9가지 질문과 지금의 가설)를 기준으로
초안을 홈피드에서 이 글을 처음 보는 독자의 눈으로 읽고, 아래 7개 기준을 1~5점으로 매겨라. 후하게 주지 마라.
- 약속 회수: 추천 제목·썸네일이 던진 궁금증을 본문 첫 화면(첫 3문단)에서 답하나. 낚시로 끝나면 1점.
  추천 제목과 썸네일이 같은 이야기(같은 숫자에서 이어지는 궁금증, 같은 비교 대상)인가. 서로 딴 얘기면 2점 이하,
  fixes에 "추천 제목을 썸네일과 짝이 되게"라고 적는다.
  퀴즈 정답은 규칙상 퀴즈 카드 뒤에만 나온다. 제목의 답을 첫 화면에서 줬다면 퀴즈 정답이 뒤에 있는 것은 감점하지 않는다.
  제목이 퀴즈 정답을 묻고 있으면 fixes에 "추천 제목을 첫 화면에서 답할 수 있는 궁금증으로 바꿔라"라고 적는다.
- 새 정보: 기사·다른 블로그에 없는, 이 글이 직접 계산한 숫자가 중심인가.
- 머무를 이유: 퀴즈·카드·문단 흐름이 끝까지 읽게 만드나. 억지로 늘린 문장이 있으면 감점.
- 신뢰: 기준일·출처 종류·계산 방법이 보이나. 과장·단정이 없나.
- 남는 한 줄: 읽고 나서 친구에게 말할 한 줄이 분명한가.
- 광고주 안전: 광고 옆에 놓여도 괜찮은가 (비방·논란·도박·사생활·선정 없음).
- 사람 말투: 블로거가 쓴 것처럼 읽히나 (AI 상투어·기계적 반복 없음). 글쓴이('저')의 생각·의외였던 점·의견이 근거와 함께 보이나.
  숫자와 사실만 이어지면 3점 이하. 하지 않은 경험(직관·만남·구매)을 꾸몄으면 1점. 글쓴이 설정의 가치관과 어긋나면 3점 이하.
fixes에는 4점 미만 기준을 올릴 구체적인 수정 지시만 적는다 (숫자표에 없는 숫자를 새로 넣으라는 지시는 금지). 모두 4점 이상이면 빈 목록."""

EXTRACT_RULES = """너는 스포츠 기사 요약문에서 숫자 사실만 뽑는 담당이다. 글은 쓰지 않는다.

규칙
- 요약문에 글자로 적힌 숫자만 뽑는다. 추측·계산·기억으로 채우지 않는다. 없으면 빼거나 usable=false.
- 같은 사실을 여러 기사가 말하면 기사마다 한 줄씩 따로 적는다 (source = 기사 번호). 어느 쪽이 맞는지는 코드가 정한다.
- key는 영어 소문자_밑줄. 연봉은 반드시 key "salary", 올해 시즌 연봉 1년치(계약 총액 아님). 단위(unit)는 USD·EUR·GBP·KRW 중 하나, value는 그 통화 그대로의 숫자(예: 2200만 달러 → 22000000).
- 주급만 보도됐으면 연봉으로 바꾸지 말고 usable=false (연봉 1년치로 보도된 숫자만).
- 연봉이 외화면 그 통화의 원화 환율도 뽑는다: key "fx_krw_per_usd"(1달러당 원) / "fx_krw_per_eur"(1유로당 원) / "fx_krw_per_gbp"(1파운드당 원), 가장 최근 마감 환율.
- 경기·이닝·안타 같은 올 시즌 누적 기록은 key를 짧게 (games, innings, wins, strikeouts, at_bats, hits, home_runs, goals, assists 등). 타율·평균자책점도 facts에 넣되 units에는 넣지 않는다.
- units: 연봉을 나눌 단위 2~4개. key는 facts의 key, label은 "1경기", "1이닝"처럼. 0이거나 없는 기록은 넣지 않는다.
- headline_unit: 제목에 쓸 가장 눈길 끄는 단위 key.
- story: 글 맥락이 되는 사실 3~6개를 짧게 네 말로 (기사 문장 복사 금지). 숫자는 facts에 있는 것만. 사생활·연애·가족·논란·도박은 빼라.
- 계약 총액·지급 유예 금액처럼 글에 필요한 다른 돈도 facts로 뽑는다 (key 예: contract_total, deferred, unit은 USD·EUR·GBP·KRW). 원화 환산은 코드가 한다.
- salary_basis: 연봉 근거를 한 줄로, 금액 숫자 없이 (예: "6년 계약 중 2026년 연봉, 보도 기준", "10년 계약, 대부분 지급 유예"). 금액은 facts에만.
- usable=false: 올해 연봉 또는 나눌 기록이 요약문에 없을 때. reason에 무엇이 없는지 적는다.
- 사용자가 준 '종목 안내'가 있으면 따른다 (예: 골프는 연봉 대신 올해 상금).
"""

WRITE_RULES = """너는 네이버 블로그 "억소리 나는 스포츠"(닉네임 백억소리)의 글쓴이다. 목표는 홈판에서 눌리고 끝까지 읽히는 글이다.
위의 두 스킬 문서(blog-voice, money-content-writer)를 따른다. 특히 아래는 반드시 지킨다.

숫자
- 돈은 모두 원화로 쓴다 (외화 금액은 숫자표의 원화 환산값). "달러"·"유로"·"파운드"라는 말은 마지막 "기준:" 문단의 환율 설명에만 쓴다.
- 글과 제목에는 사용자가 준 '숫자표'에 있는 숫자만 쓴다. 새로 계산하거나 반올림해서 키우지 않는다.
- 줄여 쓰기는 버림만 허용: "2억 32만원" → "2억", "298억 4,740만원" → "약 298억원".
- 금액은 붙여 쓴다: "9,045만원", "27억원", "2억 32만원" ("만 원", "억 원"처럼 띄우지 않는다).
- 출처끼리 차이가 있다고 표시된 숫자는 본문에 "보도에 따라 약간 차이가 있어요"를 한 번 적는다.

구조 (홈판형)
- 첫 줄은 제목의 답이 되는 숫자 한 줄. 제목에서 던진 숫자는 본문 첫 화면에서 회수한다.
- 문단은 3문장 이하, 짧은 문장과 긴 문장을 섞는다. 질문 2~4개. 최저임금 같은 교차 비교 1번.
- 이미지는 숫자표의 '이미지 자리' 목록대로, 각 줄을 따옴표 안 모양 그대로 한 줄씩 순서대로 넣는다 (카드에 쪽 번호가 있어 순서를 지킨다).
- 끝에서 둘째 문단: 궁금한 선수를 댓글로 묻는 열린 질문 한 줄 (예: "누구 연봉을 쪼개 보면 좋을까요?").
- 다음 글 예고 금지: "다음 글은 ○○", "다음 영수증은 ○○", "다음 편에서"처럼 다음 글이 누구·무엇인지 쓰지 않는다 (아직 정해지지 않았다). 코드 검사에서 걸린다.
- 마지막 문단: "기준: ..."으로 연봉·성적·환율·최저임금의 기준일과 출처 종류를 한 문장으로.

사람 냄새 (2026-10-01 대표 지적: 숫자와 사실만 이어져 사람이 쓴 느낌이 없다)
- 글쓴이 '저'가 나온다. 이 블로그는 연봉을 직접 쪼개 보는 스포츠 팬이다. 계산하면서 든 생각·의외였던 점을 1~2번
  (예: "솔직히 1승에 차 한 대도 안 될 줄 알았는데, 1.5대가 나와서 다시 계산해 봤어요").
- 자기 의견 하나를 근거와 함께 (예: "저는 이 몸값이 아깝다고 보진 않아요. 선발 한 명이 1년에 132이닝을 막아 주는 값이니까요").
  선수를 깎아내리거나 단정하지 않고, 근거는 숫자표 안에서.
- 숫자의 한계를 솔직하게 한 줄 (예: "물론 경기 밖 훈련·재활까지 생각하면 이 계산은 단순하죠").
- 독자 입장에서 공감 한 번 (월급날·할부·연말정산처럼 누구나 아는 장면). '우리'는 써도 된다.
- 금지: 하지 않은 경험 꾸미기(경기장에서 봤다, 만났다, 샀다, 지인이 말했다), 감정 과장(충격·소름).
- 기계적인 꼴 금지: 매 문단 '숫자 + 사실' 반복, "~일까요? 맞혀 보세요" 같은 꼴을 두 번 이상, 끝에 "OO은 OO를 받는다." 같은 요약 단정문.
- 문단마다 하나: 첫 문단(검색 답 한 줄)·사진/표 자리·질문 한 줄 소제목·"기준:" 줄을 뺀 모든 문단에 글쓴이의 의도·감정·생각·의견이 드러나는 말을 하나 이상
  (예: 저는, 제가 계산해 보니, 솔직히, 의외였던 건, 궁금했던 건, 아쉬운 건, ~것 같아요, ~네요, 제 눈엔, 우리). 같은 말을 돌려 쓰지 말고 문단마다 다르게.
  숫자 문장 뒤에 그 숫자를 보고 든 생각을 붙이는 식이면 된다. 코드 검사에서 걸린다.

대표 지시 9가지 (2026-10-02, 코드 검사에서 걸린다)
1. 제목: 키워드 나열 말고 검색하는 사람이 물어볼 질문 그대로 (위 '제목').
2. 첫 줄에 결론부터: 첫 문단은 제목 질문의 숫자 답 한 줄. 배경 설명(왜 이 선수인지, 시즌 이야기)은 뒤로.
3. 같은 키워드 여러 번 박지 않기: '이름 + 연봉'은 본문에 3번까지. 나머지는 "올해 몸값", "이 금액"처럼 바꿔 말한다.
4. 글쓴이의 생각·의견·반응은 네가 직접 쓴다 (대표가 쓸 칸 없음, 2026-10-03: 바로 발행). 단, 하지 않은 경험(직접 봤다·갔다·만났다·샀다·먹었다)은 지어내지 않는다 — 광고가 붙는 글이라 공정위 기만광고·네이버 저품질 위험. 생각·의견·가치관은 마음껏, 경험은 금지.
5. "많이·대부분·상당히·엄청" 같은 막연한 양 대신 숫자 (예: "143경기 중 140경기", "열 명 중 일곱"). 숫자표에 없는 숫자는 만들지 않는다. 숫자가 없으면 그 말을 뺀다.
6. 표 하나는 꼭: '[표 1: …]' 자리 (항목 8~10개는 코드가 맞춘다).
7. 표를 이미지로 대신하지 않는다: 카드 이미지는 보조이고, 표는 '[표 1]' 자리의 네이버 표다.
8. 질문형 소제목 2~3개: 한 줄짜리 질문 문단, 바로 다음 문장이 숫자 답 (AI 브리핑이 그 답을 잘라 간다).
9. 긴 대시(—, –) 쓰지 않는다. 쉼표나 마침표로.

오늘의 사건 훅 (대표 결정 2026-10-03: 경기 직후 검색을 잡되 우리 각도로)
- 숫자표에 '오늘의 사건'이 있으면: 제목과 첫 문단을 그 사건에 건다. 그다음 바로 우리 계산(연봉 쪼개기)으로 넘어간다.
  예: 사건 "어제 끝내기 홈런" → 제목 "OO 어제 끝내기 홈런, 그 한 방 연봉으로 얼마일까?", 첫 문단 "어제 끝낸 그 손끝 한 방이 연봉으로 치면 1,458만원이에요." (사건 + 계산 결론 숫자를 첫 문단에 같이).
- 사건은 사실만 한 줄로 (점수·기록·이적설 등 뉴스에 나온 것). 기사 문장을 복제하지 않고, 사건을 길게 설명하지 않는다 (우리 글은 결과 중계가 아니라 계산이다).
- 사건으로 끌고 왔으니 본문은 평소처럼 연봉 쪼개기·표·계산 방법으로 채운다 (정보 이득은 계산에서 나온다).

네이버 AI 브리핑 (검색 결과 맨 위 AI 요약이 인용하는 건 글과 네이버 표다. 카드 이미지는 인용되지 않는다, 2026-10-01)
- 표: 숫자표의 '표 자리' 줄을 따옴표 안 모양 그대로 한 줄로 넣는다. 그 자리에 코드가 만든 표(네이버 표)가 들어간다. 표 바로 앞 문장에서 표가 무엇인지 한 줄로 말한다.
- 검색 질문 꼴 소제목 2~3개: 사람들이 검색창에 치는 질문을 한 줄로 쓰고(예: "이정후 연봉은 1경기에 얼마일까?"), 바로 다음 문장이 숫자로 된 답이다. 소제목 줄은 기호 없이 질문 한 문장.
- 숫자는 기준과 단위를 붙여 문장 안에 쓴다 (예: "2026시즌 연봉 약 298억원을 정규시즌 162경기로 나누면 1경기에 약 1억 8,424만원").
- "계산 방법" 문단 하나: 무엇을 무엇으로 나눴는지 한두 문장 (이 블로그가 직접 계산한 숫자라는 것을 정직하게. 경험을 꾸미지 않는다).

금지
- 기사 문장·표현 복사, 경쟁 글 흉내. 요약된 사실만 네 말로.
- 가짜 경험("직접 봤다", "경기장에서"), 사생활·연애·가족·논란·개인 재산, 도박(배당·토토), 투자 권유.
- "알아보겠습니다", "결론적으로", "다양한", "것입니다" 같은 AI 티 표현 (voice 검사에서 걸린다).
- 마크다운 기호(#, **, 표). 네이버 에디터에 그대로 붙여 넣을 일반 텍스트로 쓴다.

출력
- gate_pass: 숫자표로 '새로 계산한 숫자'라는 정보 이득을 만들 수 있으면 true. info_gain에 한 줄.
- titles 5개, 모두 질문이고 묻는 각도는 다르게(얼마·몇 년치·누가 더·왜·다 받을까 등). type은 그 질문의 결(숫자형·대비형·순위형·반전형·질문형)을 모두 다르게.
  recommended는 추천 제목 번호(1~5). 대표는 추천 제목 하나만 보고 발행한다. 나머지 4개는 예비다.

제목 (홈판에서는 썸네일 + 제목만 보고 누를지 정한다. 가장 공들일 것)
- 추천 제목은 썸네일과 한 쌍이다. 썸네일(숫자표 '썸네일' 줄)이 보여 주는 숫자·비교 대상을 그대로 이어받아, 그 숫자를 보고 생길
  다음 궁금증을 던진다. 썸네일에 물건(차·아파트·유니폼·여행)이나 세금이 있으면 제목에도 그 말을 넣는다. 썸네일과 다른 숫자·다른 비교
  대상을 주제로 삼지 않는다. 예: 썸네일 "이정후 / 올해 연봉이면 / 테슬라 모델Y 597대" → 제목 "이정후 연봉이면 모델Y 몇 대 살까?"
  (단, 퀴즈 카드가 묻는 단위는 피한다). 본문 첫 문단은 이 제목의 답이다.
- 5개 모두 숫자표의 '제목용 짧은 이름'으로 시작한다 (검색 유입 + 스타 이름으로 눈길). 성+이름 전체를 쓰지 않는다.
- 제목은 검색하는 사람이 검색창에 물어볼 질문 그대로 (대표 지시 2026-10-02). 키워드 나열·괄호·가운뎃점(·)·슬래시 금지, 물음표로 끝.
  추천 제목에는 사람들이 치는 말 '짧은 이름 + 연봉'(골프는 상금)을 자연스럽게 (예: "이정후 연봉, 1경기에 얼마일까?",
  "오타니 연봉, 9,496억 계약인데 올해는 얼마?"). 같은 말을 두 번 넣지 않는다.
- 썸네일 금액(숫자표 '썸네일' 줄)은 추천 제목에 되풀이하지 않는다. 썸네일은 "얼마", 제목은 "왜?".
- 25자 이하 (띄어쓰기 포함). 던진 질문은 본문 첫 줄에서 답한다. 선수 이름은 태그에도 넣는다.
- 추천 제목은 퀴즈 카드의 정답(누가 더 비싼지, 몇 대인지, 얼마짜리인지)을 묻지 않는다. 퀴즈 정답은 퀴즈 카드 뒤에서만 공개되므로
  제목이 그걸 물으면 첫 화면에서 답할 수 없다. 제목의 궁금증은 첫 화면에서 풀고, 퀴즈는 그다음 궁금증으로 쓴다.
- 물음표는 1개까지. "충격", "경악", "헉", "소름", "역대급" 같은 과장어 금지.
- tags: 10개 안팎, 이 글에만 맞는 말(테마의 물건·세금·도시, 기록 단위, 비교 상대 등). 선수·팀·리그 태그는 코드가 앞에 붙인다. 띄어쓰기 없이, 한글·영문·숫자만 (점·%·가운뎃점·하이픈 같은 특수문자 금지: 네이버가 태그로 받지 않는다).
- cross_compare: 본문에 쓴 교차 비교 한 줄 요약.

설계 (brief: 본문보다 먼저 채운다. 스킬 0단계의 9가지 질문을 이 글에 적용한 답)
- reader: 홈피드에서 이 글을 누를 사람 한 줄 (예: "야구는 보는데 연봉 구조는 잘 모르는 30~40대").
- reader_question / promise / payoff / only_here / takeaway / why_naver: 각 한 줄. payoff는 본문 몇 번째 문단인지까지.
- ad_fit: 이 글 옆에 붙길 기대하는 광고 묶음(스포츠 용품·유니폼 / 경기 관람 / 자동차 / 부동산 시세 / 연봉·세금 중)과,
  본문에서 그걸 자연스럽게 부르는 사실 문맥 한 줄 (예: "차값 비교에 모델명·가격이 나와 자동차 광고가 붙기 좋다").
  광고를 부르려고 단어를 억지로 넣거나 구매·투자를 권하지 않는다 (어뷰징·광고주 안전 위반). 도박·대출 권유는 절대 금지.
- 본문은 brief대로 쓴다. brief와 본문이 어긋나면 본문을 고친다.

클립 (네이버 클립: 홈피드에서 그 자리에서 보는 영상. 영상에 퀴즈·정답·표가 이미 있다)
- clip_caption: 클립 설명 2~3줄. 첫 줄은 추천 제목과 같은 궁금증이고, 사람들이 클립 검색창에 치는 말 '짧은 이름 + 연봉'(골프는 '상금', 예: "이정후 연봉")을 띄어쓰기 그대로 넣는다. 둘째 줄은 댓글로 이어질 물음. 해시태그·링크는 쓰지 않는다 (코드가 붙인다).
- clip_question: 영상 마지막 화면에 크게 띄울 질문 18자 이하 (예: "누구 몸값이 궁금해요?", "이 돈이면 뭐 살래요?"). 숫자는 숫자표에 있는 것만.
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
            kind = it.get("kind")
            rule, word = ((PRODUCT_RULES, "제품") if kind == "product" else
                          (REGION_RULES, "지역") if kind == "region_avg" else (PRICE_RULES, "단지"))
            r = llm.ask_json([rule], f"{word}: {it['label']}\n오늘: {today}\n\n기사\n{news_prompt(news)}",
                             PRICE_SCHEMA, max_tokens=1000, stage="가격 기사", **extract_opts())
            src = news[r["source"] - 1] if 1 <= r["source"] <= len(news) else None
            text = (src["title"] + " " + src["description"]).replace(" ", "") if src else ""
            if not r["found"] or not src:
                why = f"기사에서 {it['short']} 가격을 찾지 못함"
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
            notes.append(f"{it['short']} 가격 못 씀 ({why})" + (" → 서울 아파트 평균으로 대신" if fallback else ""))
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


ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"  # 유럽중앙은행 공개 기준환율 (키 없음, 허용된 통로)
_ECB: dict = {}


def ecb_fx(cur: str) -> dict | None:
    """1 외화당 원 (EUR·USD·GBP). ECB는 1유로 기준이라 원/유로 ÷ 외화/유로. 실패하면 None."""
    if "rates" not in _ECB:
        try:
            import urllib.request
            with urllib.request.urlopen(ECB_URL, timeout=15) as r:
                x = r.read().decode("utf-8")
            _ECB["rates"] = {m.group(1): float(m.group(2)) for m in re.finditer(r"currency=['\"](\w+)['\"]\s+rate=['\"]([\d.]+)", x)}
            _ECB["date"] = (re.search(r"time=['\"]([\d-]+)", x) or [None, ""])[1]
        except Exception:
            _ECB["rates"], _ECB["date"] = {}, ""
    rates = _ECB["rates"]
    if "KRW" not in rates or (cur != "EUR" and cur not in rates):
        return None
    v = rates["KRW"] / (1.0 if cur == "EUR" else rates[cur])
    return {"value": round(v, 1), "date": f"{_ECB['date']}, 유럽중앙은행 기준환율"}


def build_data(topic: dict, ex: dict, facts: dict, cfg: dict) -> tuple[dict | None, str]:
    """receipt.py 입력을 만든다. 모자라거나 말이 안 되는 숫자면 (None, 이유)."""
    sal = facts.get("salary")
    if not sal:
        return None, "올해 연봉을 찾지 못함"
    cur = ex["salary_currency"]
    usd = cur in FX  # 외화 연봉 (키 이름은 예전 그대로 salary_usd / fx_krw_per_usd 에 담는다: 금액·환율)
    lo, hi = FX[cur]["salary"] if usd else (3e7, 1e11)
    if not lo <= sal["value"] <= hi:
        return None, f"연봉 숫자가 이상함 ({sal['value']:,} {cur})"
    d = {"player": topic["player"], "short_name": topic.get("short_name") or topic["player"].split(" ")[0],
         "team": topic.get("team", ""), "season": ex["season"], "event": topic.get("event", ""),
         "salary_label": f"연봉 {won(sal['value'])} · {ex['salary_basis']}" if not usd else None}
    if usd:
        c = FX[cur]
        fx = facts.get(c["key"])
        if not fx or not c["range"][0] <= fx["value"] <= c["range"][1]:
            fx = ecb_fx(cur)  # 뉴스에 환율이 없으면 유럽중앙은행 기준환율 (2026-10-02, 야말 유로 환율 실패)
        if not fx or not c["range"][0] <= fx["value"] <= c["range"][1]:
            return None, f"{c['word']} 환율을 찾지 못함"
        d |= {"salary_usd": sal["value"], "fx_krw_per_usd": fx["value"], "salary_currency": cur,
              "fx_label": f"1{c['word']} = {fx['value']:,}원 ({fx['date']})"}
    else:
        d["salary_krw"] = sal["value"]
    # 나눌 기록 점검 (2026-10-03, 김민솔 글: '대회 순번 25'·'한 대회 2라운드까지'를 시즌 기록으로 뽑음)
    for k in [k for k in ("events", "rounds") if k in facts]:
        lab = str(facts[k].get("label", ""))
        if any(w in lab for w in ("순번", "까지 소화", "번째 대회")) or re.search(r"(챔피언십|오픈|대회)\s*\d+라운드", lab):
            facts.pop(k)  # 표·숫자표에서도 빠지게 그 자리에서 뺀다
    if "events" in facts and "rounds" in facts and facts["rounds"]["value"] < 2 * facts["events"]["value"]:
        facts.pop("rounds")  # 시즌 라운드는 대회 수의 2배 이상 (컷 탈락도 2라운드)
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
    cur = d.get("salary_currency", "USD")
    L.append(f"올해 연봉: {won(n['salary_krw'])}" + (f" ({FX[cur]['word']} 연봉을 {d['fx_label']} 환율로 환산)" if fx else ""))
    L.append(f"연봉 근거: {ex['salary_basis']}")
    for u in receipt.units(d):
        L.append(f"{u['label']}당: {won(n['per'][u['key']])} (올 시즌 {u['count']:,}, 버림 표기 {won(n['per'][u['key']]).split(' ')[0]})")
        if n.get("min_wage_years_per"):
            L.append(f"  = 최저임금 연봉 {n['min_wage_years_per'][u['key']]:.1f}년치")
    if n.get("min_wage_yearly_krw"):
        L.append(f"최저임금 1년: {won(n['min_wage_yearly_krw'])} ({cfg['constants']['min_wage_label']})")
    L.append("기록·사실 (기사 날짜 · 정한 규칙):")
    for k, f in facts.items():
        if k == "salary" or k.startswith("fx_krw_per_"):
            continue
        if f["unit"] in FX:  # 외화 금액은 원화로만 보여준다 (대표 결정: 통화는 원화로). 연봉과 같은 통화만 환산
            if not fx or f["unit"] != cur:
                continue
            L.append(f"- {f['label']}: 약 {won(f['value'] * fx)} (지금 환율로 환산 · {f['date']})")
            continue
        if f["unit"] == "KRW":
            L.append(f"- {f['label']}: {won(f['value'])} ({f['date']} · {f['rule']})")
            continue
        v = f"{f['value']:,}" if float(f["value"]).is_integer() else f"{f['value']}"
        diff = f" · 출처끼리 차이 {f['differs']} → 본문에 '보도에 따라 약간 차이' 표기" if f["differs"] else ""
        L.append(f"- {f['label']}: {v}{f['unit'] if f['unit'] != 'KRW' and f['unit'] not in FX else ''} ({f['date']} · {f['rule']}){diff}")
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
TYPE_LINE = re.compile(r"^추천 제목 유형: (\S+)", re.M)


def title_type(today: str, n: int) -> str:
    """오늘 이 후보의 추천 제목 유형 (날짜·후보 순서로 돌린다 → 주간 점검에서 유형별 비교, 대표 결정 2026-09-30)."""
    return TITLE_TYPES[(date.fromisoformat(today).toordinal() + n) % len(TITLE_TYPES)]
SHORT = re.compile(r"^제목용 짧은 이름: (\S+)", re.M)
TITLE_BANNED = ["충격", "경악", "헉", "소름", "역대급"]
THUMB = re.compile(r"^썸네일: (.+?) / (.+?) / (.+?) \(", re.M)


def check_titles(p: dict, sheet: str) -> list[str]:
    """제목 규칙: 짧은 이름으로 시작, 25자 이하, 과장어 금지, 모두 질문(키워드 나열 금지, 2026-10-02),
    추천 제목은 검색어(이름+연봉) 포함 + 썸네일 금액 되풀이 금지 + 썸네일과 짝(같은 비교 대상)."""
    m = THUMB.search(sheet)
    if not m or not p["titles"]:
        return []
    name, big = m.group(1), m.group(3).split()
    money = big[-1].removesuffix("원")  # "8,400만원" · "597대" · "5,386만"
    subject = [w for w in big[:-1] if len(w) >= 2 and w not in ("최대", "약")]  # "테슬라 모델Y" · "세금"
    s = SHORT.search(sheet)
    core = s.group(1) if s else name.split(" ")[0]  # '오타니 쇼헤이' → '오타니'
    out = []
    for i, t in enumerate(p["titles"], 1):
        text = t["text"].strip()
        if not text.startswith(core):
            out.append(f"제목{i}이 짧은 이름({core})으로 시작하지 않음")
        elif name != core and " vs " not in name and text.startswith(name):
            out.append(f"제목{i}에 긴 이름 → '{core}'로")
        if len(text) > TITLE_MAX:
            out.append(f"제목{i}이 {TITLE_MAX}자 넘음 ({len(text)}자)")
        if text.count("?") > 1 or any(w in text for w in TITLE_BANNED):
            out.append(f"제목{i}에 물음표 여러 개 또는 과장어")
    rec = p["titles"][p["recommended"] - 1]["text"] if 1 <= p["recommended"] <= len(p["titles"]) else ""
    if money in rec.replace(" ", ""):
        out.append(f"추천 제목이 썸네일 숫자({money})를 되풀이함 → 반전·궁금증 한 마디로")
    if rec and subject and not any(w in rec for w in subject):
        out.append(f"추천 제목이 썸네일과 다른 이야기 → 썸네일 말('{' '.join(subject)}')을 제목에도 (짝으로)")
    # 태그의 선수 이름은 코드가 붙인다 (base_tags, 2026-09-30)
    return out


VAGUE = ["많이", "많은", "대부분", "상당히", "상당수", "엄청", "수많은", "적지 않", "꽤 많"]
DASHES = ("—", "–", "―")


def title_style(p: dict, sheet: str) -> list[str]:
    """제목은 검색하는 사람이 물어볼 질문 그대로 (대표 지시 2026-10-02): 키워드 나열·괄호·가운뎃점 금지, 물음표로 끝."""
    s = SHORT.search(sheet)
    core = s.group(1) if s else ""
    out = []
    for i, t in enumerate(p["titles"], 1):
        text = t["text"].strip()
        if not text.endswith("?"):
            out.append(f"제목{i}이 질문이 아님 → 검색하는 사람이 물을 질문 그대로 (예: '{core} 연봉, 1경기에 얼마일까?')")
        if any(ch in text for ch in "·()[]|/"):
            out.append(f"제목{i}에 키워드 나열 기호(· 괄호 / |) → 질문 한 문장으로")
    rec = p["titles"][p["recommended"] - 1]["text"] if 1 <= p.get("recommended", 0) <= len(p["titles"]) else ""
    if rec and not any(w in rec for w in ("연봉", "상금", "몸값", "세금", "월급")):
        out.append(f"추천 제목에 '{core} {'상금' if '상금' in sheet else '연봉'}'처럼 사람들이 검색하는 말이 없음")
    return out


def check_style(p: dict, sheet: str) -> list[str]:
    """말투·형식 검사 (비용 효율 2026-10-02): 이것만 걸렸을 때는 다시 쓰지 않는다. 사실·안전 문제(check_post)로
    다시 쓸 때, 또는 편집장이 고쳐 쓰라고 할 때 같이 고친다. 남은 것은 발행 패키지에 '참고'로 (✅는 유지)."""
    out = list(check_draft(p["body"])) + title_style(p, sheet) + style_rules(p, sheet)
    gaps = human_gaps(p["body"])
    if gaps:
        out.append(f"글쓴이의 생각·느낌·의견이 안 보이는 문단 {len(gaps)}개 (문단마다 하나씩, 꾸민 경험은 금지): "
                   + " / ".join(f"'{g}…'" for g in gaps))
    return out


def code_fixes(p: dict) -> dict:
    """코드로 고칠 수 있는 형식은 Claude 없이 고친다: 긴 대시 → 쉼표. (옛 [대표 한마디] 줄이 있으면 뺀다)"""
    body = "\n\n".join(x for x in undash(p["body"]).split("\n\n") if x.strip() != "[대표 한마디]")
    return {**p, "titles": [{**t, "text": undash(t["text"])} for t in p["titles"]],
            "body": body, "clip_caption": undash(p.get("clip_caption", ""))}


def undash(text: str) -> str:
    return re.sub(r"\s*[—–―]\s*", ", ", text)


def style_rules(p: dict, sheet: str) -> list[str]:
    """대표 지시 9가지 (2026-10-02) 중 코드로 보는 것: 첫 줄 결론, 같은 키워드 되풀이, 막연한 양 대신 숫자,
    질문형 소제목 2~3개, 긴 대시 금지."""
    out, body = [], p["body"]
    paras = [x.strip() for x in body.strip().split("\n\n") if x.strip()]
    if paras and not re.search(r"\d", paras[0]):
        out.append("첫 줄에 결론(숫자 답)이 없음 → 배경 설명은 뒤로, 첫 줄은 제목 질문의 답")
    s = SHORT.search(sheet)
    if s:
        for w in ("연봉", "상금"):
            k = f"{s.group(1)} {w}"
            c = body.count(k) + body.count(k.replace(" ", ""))
            if c > 3:
                out.append(f"'{k}'를 본문에 {c}번 → 3번까지 (같은 키워드 되풀이 금지, 대명사·다른 말로)")
    hit = [w for w in VAGUE if w in body]
    if hit:
        out.append(f"막연한 양 표현 {', '.join(hit)} → 숫자로 (예: '열 명 중 일곱', 숫자표에 있는 숫자만). 숫자가 없으면 그 말을 빼기")
    qs = [x for x in paras if "\n" not in x and x.endswith("?") and len(x) <= 40 and not x.startswith("[")]
    if len(qs) < 2:
        out.append(f"질문형 소제목이 {len(qs)}개 → 2~3개 (검색 질문 한 줄 + 바로 다음 문장이 숫자 답)")
    texts = [("본문", body), ("클립 설명", p.get("clip_caption", ""))] + [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]
    for label, text in texts:
        if any(d in text for d in DASHES):
            out.append(f"{label}에 긴 대시(—) → 쉼표나 마침표로 (AI 티)")
    return out


def check_post(p: dict, sheet: str) -> list[str]:
    """사실·안전·구조 검사: 걸리면 고쳐 쓴다 (말투·형식은 check_style)."""
    problems = []
    if len(p.get("clip_question", "")) > 18:
        problems.append(f"클립 질문이 18자를 넘음 ({len(p['clip_question'])}자)")
    s = SHORT.search(sheet)
    if s and p.get("clip_caption") and not re.search(rf"{re.escape(s.group(1))}\s?(연봉|상금)", p["clip_caption"]):
        problems.append(f"클립 설명 첫 줄에 검색어 '{s.group(1)} 연봉'(골프는 상금)이 없음")
    for label, text in ([("본문", p["body"])] + [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]
                        + [("클립 설명", p.get("clip_caption", "")), ("클립 질문", p.get("clip_question", ""))]):
        bad = unknown_numbers(text, sheet)
        if bad:
            problems.append(f"{label}에 숫자표에 없는 숫자: {', '.join(bad)}")
    if "표 자리" in sheet and not TABLE_LINE.search(p["body"]):
        problems.append("표 자리 '[표 1: …]' 줄이 없음 (네이버 표가 들어갈 자리)")
    m_img = re.search(r"^이미지 파일: (.+)$", sheet, re.M)
    for img in ([x.strip() for x in m_img.group(1).split(",")] if m_img else IMAGES):
        if img not in p["body"]:
            problems.append(f"이미지 자리 {img} 없음")
    teaser = [m.group(0) for m in TEASER.finditer(p["body"] + "\n" + p.get("clip_caption", ""))]
    if teaser:
        problems.append(f"다음 글 예고 문장 (쓰지 않는다): {', '.join(teaser)}")
    hit = [w for w in BANNED if w in p["body"]]
    if hit:
        problems.append(f"금지 주제 단어: {', '.join(hit)}")
    problems += check_titles(p, sheet)
    if len(p["titles"]) != 5 or not 1 <= p["recommended"] <= len(p["titles"]):
        problems.append("제목 5개와 추천 번호(1~5)가 필요")
    for label, text in [("본문", "\n".join(l for l in p["body"].splitlines() if not l.startswith("기준")))] + \
            [(f"제목{i}", t["text"]) for i, t in enumerate(p["titles"], 1)]:
        for w in ("달러", "유로", "파운드"):
            if w in text:
                problems.append(f"{label}에 '{w}' → 원화로 (환율은 '기준:' 문단에만)")
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
    return [t for t in docs + [example, persona_text(), WRITE_RULES] if t.strip()]


def persona_text() -> str:
    """글쓴이 설정 (config/persona.yaml, 2026-10-02): 모든 글이 같은 한 사람의 의도·가치관·말버릇으로 읽히게."""
    f = ROOT / "config" / "persona.yaml"
    if not f.exists():
        return ""
    return ("# 글쓴이 설정 (모든 글의 '저'는 이 사람이다. 생각·의견·가치관은 이 설정과 어긋나지 않게. "
            "never 목록과 true_actions에 없는 경험은 쓰지 않는다)\n\n" + f.read_text(encoding="utf-8"))


def llm_cfg() -> dict:
    return load_yaml("global.yaml").get("llm", {})


def extract_opts() -> dict:
    e = llm_cfg().get("extract", {})
    return {"model": e.get("model", "claude-sonnet-5-5"), "effort": e.get("effort", "low")}


def write_post(llm, topic: dict, sheet: str, max_revisions: int) -> tuple[dict, list[str], int]:
    w = llm_cfg().get("write", {})
    cap = llm_cfg().get("cost_cap_usd_per_post", 1.0) + llm.cost_usd()  # 이 글에서 쓴 비용만 센다 (여러 번 시도할 때)
    opts = {"model": w.get("model", "claude-sonnet-5-5"), "effort": w.get("effort", "medium")}
    system = writer_system()
    prompt = (f"카테고리: {topic['category']}\n글 방향: {topic['angle']}\n\n숫자표\n{sheet}\n\n"
              "이 숫자표로 발행 패키지를 JSON으로 만들어라.")
    # 다시 쓰기를 줄인다 (대표 지시 2026-10-02, 비용 증가 막기): 사실·안전·구조 문제(check_post)만 고쳐 쓰기를 부르고,
    # 말투·형식(check_style)은 그때 같이 고친다. 대시·[대표 한마디] 자리는 코드가 고친다. 검사 고쳐 쓰기는 1번까지.
    post = code_fixes(llm.ask_json(system, prompt, POST_SCHEMA, stage="글쓰기", **opts))
    problems = check_post(post, sheet)
    rounds = 0
    while problems and rounds < min(max_revisions, 1) and llm.cost_usd() < cap:
        rounds += 1
        style = check_style(post, sheet)
        fix = (prompt + "\n\n아래는 네가 쓴 초안이다. 검사에서 걸린 문제만 고치고, 나머지는 유지해서 같은 JSON 형식으로 다시 내라.\n"
               "문제:\n" + "\n".join(f"- {x}" for x in problems + style) + "\n\n초안:\n" + json.dumps(post, ensure_ascii=False))
        post = code_fixes(llm.ask_json(system, fix, POST_SCHEMA, stage="고쳐쓰기(검사)", **opts))
        problems = check_post(post, sheet)
    # 편집장 검토 (스킬 0단계 기준): 4점 미만이 있으면 한 번 고쳐 쓰고, 고친 글이 코드 검사를 통과할 때만 바꾼다
    review = review_post(llm, sheet, post)
    for _ in range(1):  # 편집장 고쳐 쓰기는 1번만 (비용 효율, 2026-10-01)
        low = [x for x in review["scores"] if x["score"] < REVIEW_PASS]
        if review_ok(review["scores"]) or problems or llm.cost_usd() >= cap:  # 통과 기준이면 고쳐 쓰지 않는다 (비용 효율)
            break
        fix = (prompt + "\n\n아래는 네가 쓴 초안과 편집장 검토다. 검토의 수정 지시를 반영해 같은 JSON 형식으로 다시 내라. "
               "숫자는 숫자표에 있는 것만.\n검토:\n" + "\n".join(f"- {x['criterion']} {x['score']}점: {x['reason']}" for x in low)
               + "\n수정 지시:\n" + "\n".join(f"- {f}" for f in review["fixes"] + check_style(post, sheet))
               + "\n\n초안:\n" + json.dumps(post, ensure_ascii=False))
        again = code_fixes(llm.ask_json(system, fix, POST_SCHEMA, stage="고쳐쓰기(편집장)", **opts))
        if check_post(again, sheet):
            break
        post, rounds = again, rounds + 1
        review = review_post(llm, sheet, post)
    post["review"] = review
    post["style_notes"] = check_style(post, sheet)  # 다시 쓰지 않은 말투·형식 문제 (패키지에 참고로, ✅는 유지)
    if not review_ok(review["scores"]):  # 고쳐 써도 기준 미달이면 발행 가능으로 두지 않는다 (도우미에서 ⚠️, 다시 뽑기 권장)
        low = [x["criterion"] for x in review["scores"] if x["score"] < REVIEW_PASS]
        problems = problems + [f"편집장 기준 미달 ({', '.join(low)}) — 다시 뽑기 권장"]
    return post, problems, rounds


def review_post(llm, sheet: str, post: dict) -> dict:
    docs = [t for t in [(SKILLS / "money-content-writer" / "SKILL.md").read_text(encoding="utf-8"), persona_text(), REVIEW_RULES] if t]
    draft = {k: post[k] for k in ("brief", "titles", "recommended", "body", "clip_caption", "clip_question")}
    return llm.ask_json(docs, f"숫자표\n{sheet}\n\n초안\n{json.dumps(draft, ensure_ascii=False)}", REVIEW_SCHEMA,
                        max_tokens=3000, stage="편집장", **extract_opts())


# ---------------------------------------------------------------- 패키지

def package_md(title: str, theme: str, category: str, facts: dict, post: dict, problems: list[str], rounds: int,
               cfg: dict, news_count: int, cost: float | None, extra_sources: list[str] = (), marketer: str = "") -> str:
    rec = post["recommended"]
    status = "✅ 자동 검사 통과" if not problems and post["gate_pass"] else "⚠️ 검사 미통과 — 발행하지 말고 Claude에게 알려주세요"
    out = [f"# 발행 패키지 · {title}", "",
           f"**상태:** {status}  ", f"**게이트:** {'통과' if post['gate_pass'] else '미통과'} — 정보 이득: {post['info_gain']}  ",
           f"**자동 작성:** Claude 초안 → 코드 검사 (고쳐 쓰기 {rounds}회)" + (f" · API 비용 약 ${cost:.2f}" if cost else "")
           + ("  " if marketer else ""), *([f"**마케터:** {marketer}"] if marketer else []), ""]
    if problems:
        out += ["**남은 문제:**", ""] + [f"- {p}" for p in problems] + [""]
    if post.get("style_notes"):  # 비용 효율로 다시 쓰지 않은 말투·형식 (2026-10-02). 대표가 도우미에서 고쳐도 되고, 주간 점검에서 규칙에 반영
        out += ["**참고 (말투·형식, 발행은 가능):**", ""] + [f"- {p}" for p in post["style_notes"]] + [""]
    if post.get("brief"):
        out += ["## 이 글의 설계 (독자·네이버 관점, 스킬 0단계)", ""]
        out += [f"- {BRIEF_KEYS[k]}: {v}" for k, v in post["brief"].items() if k in BRIEF_KEYS] + [""]
    if post.get("review"):
        sc = post["review"]["scores"]
        low = [f"- {x['criterion']}: {x['reason']}" for x in sc if x["score"] < REVIEW_PASS]
        out += ["## 편집장 검토 (5점 만점)", "", " · ".join(f"{x['criterion']} {x['score']}" for x in sc), ""]
        out += low + ([""] if low else [])
    out += ["## 제목 (추천 ★)", ""]
    out += [f"{i}. {'★ ' if i == rec else ''}{t['text']} — {t['type']}" for i, t in enumerate(post["titles"], 1)]
    plan = themes.image_plan(theme)
    out += ["", "## 이미지 (본문 [이미지] 자리에 넣기)", "", "| 순서 | 파일 | 위치 | 대표이미지 |", "| --- | --- | --- | --- |"]
    out += [f"| {i} | {f} | {lab} | {'✅ 대표이미지로 지정' if i == 1 else ''} |" for i, (lab, f, _) in enumerate(plan, 1)]
    out += ["", "## 카테고리 · 태그", "", f"- 카테고리: **{category}**", f"- 태그: {', '.join(clean_tags(post['tags']))}", "",
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
            f" · 이미지 {len(plan)} · 참고 기사 {news_count}건"
            + (f" · 검토 평균 {sum(x['score'] for x in post['review']['scores']) / max(1, len(post['review']['scores'])):.1f}"
               if post.get("review") else ""), ""]
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


def known_salary(player: str, today: str) -> dict | None:
    """config/salaries.yaml의 확인된 올해 연봉 (시즌이 맞을 때만)."""
    f = ROOT / "config" / "salaries.yaml"
    if not f.exists():
        return None
    t = load_yaml("salaries.yaml")
    k = (t.get("players") or {}).get(player)
    return {**k, "season": t["season"]} if k and int(t.get("season", 0)) == int(today[:4]) else None


def with_known_salary(facts: dict, ex: dict, known: dict) -> tuple[dict, dict]:
    """뉴스에 올해 연봉이 없으면 확인 연봉표 값을 쓴다. 뉴스 값이 있으면 뉴스 우선, 다르면 차이를 남긴다."""
    news_sal = facts.get("salary")
    if news_sal and ex.get("salary_currency") == known["currency"]:
        if news_sal["value"] != known["amount"]:
            news_sal["differs"] = sorted({news_sal["value"], known["amount"]})
        return facts, ex
    facts = {**facts, "salary": {"value": known["amount"], "label": "올해 연봉", "unit": known["currency"],
                                 "date": str(known["as_of"]), "sources": [known["source"]], "rule": "확인 연봉표",
                                 "differs": None}}
    return facts, {**ex, "salary_currency": known["currency"], "salary_basis": known["basis"], "season": known["season"]}


MONEY = re.compile(r"\d[\d,.]*\s*(억|만\s*(달러|유로|파운드|원)|달러|유로|파운드)")
MONEY_WORDS = ("연봉", "주급", "상금", "계약", "몸값", "salary")


def money_in_news(topic: dict, news: list[dict]) -> bool:
    """정보가 없는 선수는 빼고 주제를 잡는다 (대표 지시 2026-10-02): Claude에게 넘기기 전에, 이 선수 이름과
    돈 숫자(억·만 달러·유로·파운드)와 연봉·상금·계약 같은 말이 한 기사에 같이 있는지 코드로 먼저 본다."""
    names = {topic["player"], topic.get("short_name") or topic["player"]}
    for it in news:
        t = f"{it.get('title', '')} {it.get('description', '')}"
        if any(n and n in t for n in names) and MONEY.search(t) and any(w in t for w in MONEY_WORDS):
            return True
    return False


def collect(hub, llm, topic: dict, today: str, cfg: dict) -> dict | str:
    """한 선수의 뉴스 → 숫자 뽑기 → 충돌 정리 → 계산 입력. 모자라면 이유(str)를 돌려준다."""
    news = gather_news(hub, topic["queries"] + cfg.get("fx_queries", [cfg["fx_query"]]))
    hint = f"\n종목 안내: {topic['hint']}" if topic.get("hint") else ""
    known = known_salary(topic["player"], today)
    if not known and not money_in_news(topic, news):
        return "뉴스에 연봉·상금 숫자가 안 보임 (코드 확인, Claude 비용 없음)"
    if known:
        hint += (f"\n확인된 올해 연봉이 따로 있다 ({known['currency']}, 코드가 넣는다). 요약문에 올해 연봉이 없어도 "
                 "나눌 기록이 있으면 usable=true. " + (f"외화 연봉이니 환율({FX[known['currency']]['key']})은 꼭 뽑는다." if known["currency"] in FX else ""))
    ex = llm.ask_json([EXTRACT_RULES], f"선수: {topic['player']} ({topic.get('team', '')}, {topic.get('sport', '')}){hint}\n"
                      f"오늘: {today}\n\n뉴스 요약 (번호 = source):\n{news_prompt(news)}",
                      EXTRACT_SCHEMA, max_tokens=8000, stage="숫자 뽑기", **extract_opts())
    if not ex["usable"]:
        return ex["reason"]
    facts = resolve(ex["facts"], news)
    if known:
        facts, ex = with_known_salary(facts, ex, known)
    d, why = build_data(topic, ex, facts, cfg)
    if d is None:
        return why
    remember_ready(topic, today)
    return {"d": d, "facts": facts, "ex": ex, "news": news}


READY = ROOT / "config" / "ready_players.yaml"
READY_DAYS = 120


def ready_players(today: str) -> set[str]:
    """정보가 확인된 선수: 확인 연봉표(salaries.yaml) + 최근 120일 안에 뉴스에서 연봉·기록을 뽑아 글을 만든 선수."""
    book = (yaml.safe_load(READY.read_text(encoding="utf-8")) or {}) if READY.exists() else {}
    cut = str(date.fromisoformat(today) - timedelta(days=READY_DAYS))
    sal = ((load_yaml("salaries.yaml") or {}).get("players") or {}) if (ROOT / "config" / "salaries.yaml").exists() else {}
    return set(sal) | {n for n, v in book.items() if str(v.get("date", "")) >= cut}


def remember_ready(topic: dict, today: str) -> None:
    book = (yaml.safe_load(READY.read_text(encoding="utf-8")) or {}) if READY.exists() else {}
    book[topic["player"]] = {"date": today}
    READY.write_text("# 정보(올해 연봉·기록)를 뉴스에서 찾아 글을 만든 선수 (content/autopost.py가 채움, 2026-10-02)\n"
                     "# 주제를 잡을 때 이 선수들을 3배 먼저 뽑는다. 연봉·기록을 못 찾은 선수는 skip_players.yaml에 30일.\n"
                     + yaml.safe_dump(book, allow_unicode=True, sort_keys=True), encoding="utf-8")


USED_DAYS = 120  # 같은 테마·같은 선수(조합)는 이 기간 안에 다시 쓰지 않는다 (콘텐츠가 마르지 않게 고르게 쓴다)


def used_combos(today: str, days: int = USED_DAYS) -> tuple[set, dict[str, set[str]]]:
    """최근 쓴 (테마, 선수들) 조합과, 선수별로 이미 비교한 물건 key. 버린 글(rejected)은 세지 않는다."""
    combos, items = set(), {}
    day = date.fromisoformat(today)
    for f in (x for x in POSTS.iterdir() if (x / "data.yaml").exists()) if POSTS.exists() else []:
        try:
            if (day - date.fromisoformat(f.name[:10])).days > days or mark.status(f).get("status") == "rejected":
                continue
        except ValueError:
            continue
        d = yaml.safe_load((f / "data.yaml").read_text(encoding="utf-8")) or {}
        names = tuple(sorted(themes.names_in(d)))
        combos.add((d.get("theme", "receipt"), names))
        for pr in d.get("prices", []):
            items.setdefault(d.get("player", ""), set()).add(pr.get("key"))
    return combos, items


CITY_QUERY = {"광주": "광주광역시"}  # 같은 이름 지역(경기 광주)과 헷갈리지 않게


def places_for(pool: dict, player: dict) -> list[dict]:
    """선수와 이어진 장소: 지금 소속팀 연고지(players.yaml cities) + 출신지·예전 소속팀(places.yaml). 공개된 사실만."""
    cfg = load_yaml("places.yaml") if (ROOT / "config" / "places.yaml").exists() else {}
    domestic = set((cfg.get("cities") or {}).get("국내", []))
    out = []
    city = (pool.get("cities") or {}).get(player.get("team", ""))
    if city:
        out.append({"city": city, "relation": f"지금 소속팀({player['team']}) 연고지"})
    out += [dict(x) for x in (cfg.get("players") or {}).get(player["name"], [])]
    seen, uniq = set(), []
    for x in out:
        if x["city"] not in seen:
            seen.add(x["city"])
            uniq.append({**x, "domestic": x["city"] in domestic})
    return uniq


def place_item(place: dict, theme: str) -> dict:
    """연고지 아파트(국내 도시, 글 쓰는 날 뉴스에서 평균 매매가) 또는 여행(국민여행조사 평균 경비) 비교 물건."""
    city = place["city"]
    if theme == "place":
        q = CITY_QUERY.get(city, city)
        return {"key": f"apt_{city}", "group": "place", "label": f"{q} 아파트 평균 매매가격", "short": f"{city} 아파트",
                "unit": "채", "fetch": "news", "kind": "region_avg", "query": f"{q} 아파트 평균 매매가격",
                "min_krw": 100_000_000, "max_krw": 3_000_000_000}
    t = load_yaml("places.yaml")["travel"]["domestic" if place["domestic"] else "overseas"]
    return {"key": f"trip_{city}", "group": "trip", "label": t["label"], "short": f"{city} 여행", "unit": "번",
            "price_krw": t["price_krw"], "as_of": t["as_of"], "source": t["source"]}


NO_DATA = ROOT / "config" / "skip_players.yaml"
NO_DATA_DAYS = 30  # 정보 없는 선수는 빼고 주제를 잡는다 (대표 지시 2026-10-02, 7일 → 30일)
READY_BOOST = 3   # 정보가 확인된 선수는 3배 먼저


def no_data_players(today: str) -> list[str]:
    """최근 30일 안에 뉴스에서 올해 연봉·기록을 못 찾은 선수. 다시 모으면 숫자 뽑기 비용만 든다 (실측: 하루 약 11명, 비용의 약 30%)."""
    book = (yaml.safe_load(NO_DATA.read_text(encoding="utf-8")) or {}) if NO_DATA.exists() else {}
    return [n for n, v in book.items() if str(v.get("until", "")) >= today]


def remember_no_data(failed: dict[str, str], today: str) -> None:
    if not failed:
        return
    book = (yaml.safe_load(NO_DATA.read_text(encoding="utf-8")) or {}) if NO_DATA.exists() else {}
    until = str(date.fromisoformat(today) + timedelta(days=NO_DATA_DAYS))
    book = {n: v for n, v in book.items() if str(v.get("until", "")) >= today}
    book |= {n: {"until": until, "why": why[:120]} for n, why in failed.items()}
    NO_DATA.write_text("# 연봉·기록을 못 찾은 선수 (이 날짜까지 다시 모으지 않음, content/autopost.py가 채움)\n"
                       + yaml.safe_dump(book, allow_unicode=True, sort_keys=True), encoding="utf-8")


def reset_drafts(today: str) -> list[str]:
    """초안 목록 매일 리셋 (대표 결정 2026-09-30): 오늘 이전 날짜의 글 중 발행 완료(used)가 아닌 것은 지운다.
    발행한 글은 성과 기록·중복 방지(used_combos)를 위해 남긴다. 발행 안 한 후보는 재고를 쓰지 않은 것으로 본다."""
    import shutil
    gone = []
    for f in (x for x in POSTS.iterdir() if x.is_dir()) if POSTS.exists() else []:
        if re.match(r"\d{4}-\d{2}-\d{2}-", f.name) and f.name[:10] < today and mark.status(f).get("status") != "used":
            shutil.rmtree(f)
            gone.append(f.name)
        elif mark.status(f).get("status") == "used" and str(mark.status(f).get("at", ""))[:10] < today:
            for v in ("clip.mp4", "bg.mp4"):  # 발행한 글의 클립은 올렸으니 폐기 (대표 결정 2026-09-30)
                (f / v).unlink(missing_ok=True)
    if gone:
        write_index()
    return gone


def eligible(pool: dict) -> dict[str, set[str]]:
    """테마별로 쓸 수 있는 선수: 세금은 국내 리그(사업소득·원화), 유니폼은 가격을 확인한 팀,
    연고지 아파트는 국내 장소가 있는 선수, 여행은 이어진 장소가 있는 선수."""
    goods = load_yaml("goods.yaml").get("teams", {}) if (ROOT / "config" / "goods.yaml").exists() else {}
    pl = {p["name"]: places_for(pool, p) for p in pool["players"]}
    return {"tax": {p["name"] for p in pool["players"] if p["sport"] == "kbo"},
            "jersey": {p["name"] for p in pool["players"] if p.get("team") in goods},
            "place": {n for n, xs in pl.items() if any(x["domestic"] for x in xs)},
            "trip": {n for n, xs in pl.items() if xs}}


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
    if th == "tax":
        name = d.get("short_name") or d["player"]
        tax = load_yaml("tax.yaml")
        L = [strip_lines(number_sheet(d, n, got[0]["facts"], got[0]["ex"], cfg), "썸네일:", "퀴즈 카드:"),
             f"썸네일: {name} / 연봉 {won(n['salary_krw'])}이면 / 세금 최대 {receipt.short_won(n['tax_max'])}"
             " (추천 제목에는 이 금액을 다시 쓰지 않는다)",
             "세금 (코드 계산, 국세청 종합소득세 세율표):",
             f"- 월급날 떼는 세금 (사업소득 원천징수 3.3% = 소득세 3% + 지방소득세 0.3%): {won(n['withhold'])}",
             f"- 세금 최대 (필요경비·공제를 하나도 안 뺐다고 치고 세율표만 적용, 지방소득세 포함): {won(n['tax_max'])}"
             f" = 연봉의 {themes.ratio(n['tax_rate'] * 100)}%",
             f"- 최대로 떼면 남는 돈: {won(n['after_max'])}, {n['tax_label']}당 {won(n['after_per'])}",
             "- 쓰는 법: 선수 연봉은 사업소득이라 구단이 3.3%를 떼고, 5월에 종합소득세를 신고한다. 실제 세금은 필요경비·공제에 따라"
             " 상한보다 적고 정확한 금액은 공개되지 않는다. '실제로 낸 세금'이라고 쓰지 말고 '최대'·'많아야'로만 쓴다. 절세·투자 권유 금지.",
             f"- 세율 출처: {tax['source']}",
             f"퀴즈 카드: 월급날 떼는 세금 맞히기 (정답 {won(n['withhold'])})"]
        return "\n".join(L)
    q = n["item"]
    link = []
    if d.get("place"):
        pl = d["place"]
        link = [f"장소 연결 (공개된 경력·출생지): {pl['city']}는 {d.get('short_name') or d['player']}의 {pl['relation']}"]
        if th == "trip":
            link.append(f"- 여행 경비는 {pl['city']}만의 비용이 아니라 {q['label']}다 (국민여행조사 2025). "
                        f"'{pl['city']} 여행 경비'라고 단정하지 말고 '여행 한 번 평균 경비로 치면'처럼 쓴다. 특정 항공권·호텔 가격은 쓰지 않는다.")
        else:
            link.append("- 지역 평균 매매가(통계 보도)다. 특정 단지 값처럼 쓰지 않고, 사라·오른다 같은 투자 권유는 하지 않는다.")
    L = link + [strip_lines(number_sheet(d, n, got[0]["facts"], got[0]["ex"], cfg), "썸네일:", "퀴즈 카드:"),
         f"썸네일: {d.get('short_name') or d['player']} / 올해 연봉이면 / {q['short']} {themes.count(q['salary_count'])}{q['unit']}"
         " (추천 제목에는 이 숫자를 다시 쓰지 않는다)",
         f"비교 물건 (글 전체에서 이것 하나만 쓴다): {q['label']} {won(q['price_krw'])} ({q['as_of']} 기준)",
         f"{q['short']}로 바꾸면 (개수는 버림):"]
    L += [f"- {r['label']} {won(r['value'])} → {themes.count(r['count'])}{q['unit']}" for r in n["rows"]]
    if n["inverse"]:
        L.append(f"{q['short']} 한 {q['unit']} 사려면 (버림):")
        L += [f"- {themes.count(q['price_krw'] / r['value'])}{cards.word(r['label'])}에 1{q['unit']}"
              for r in n["rows"] if r["key"] != "salary" and r["count"] < 1]
    if n["inverse"]:
        L.append(f"{q['short']} 한 {q['unit']} 사려면: {n['life_label']} 몸값 {won(n['life_per'])}로 {themes.count(n['inverse_count'])}{n['inverse_word']}")
        L.append(f"퀴즈 카드: {q['short']} 한 {q['unit']} 사려면 몇 {n['inverse_word']} 맞히기 (정답 {themes.count(n['inverse_count'])}{n['inverse_word']})")
    else:
        L.append(f"퀴즈 카드: {n['life_label']} 몸값으로 {q['short']} 몇 {q['unit']} 맞히기 (정답 {themes.count(q['unit_count'])}{q['unit']})")
    return "\n".join(L)


DAILY_CAP_USD = 5.0  # 한 번 실행에서 쓸 Claude 비용 상한 (후보 4편 + 재시도 포함)
MARKETER_CAP_USD = 0.8  # 마케터 한 명의 하루 상한 (비용 효율, 2026-10-01): 넘으면 그날은 더 안 쓴다
NEWS_DAYS = 3        # 최근 며칠 기사 수로 "지금 궁금한 선수"를 잰다
NEWS_PER_BOOST = 15  # 기사 15건마다 가중치 +1배 (최대 3배)


def weighted_pool(hub, pool: dict, today: str) -> tuple[dict, str]:
    """적시성(대표 결정 2026-09-30): 최근 뉴스가 많은 선수, 댓글로 요청받은 선수를 더 자주 뽑는다.
    뉴스는 네이버 뉴스 검색 API(허용된 통로)로 기사 수만 센다. 실패하면 원래 가중치."""
    day = date.fromisoformat(today)
    req = load_yaml("requests.yaml") if (ROOT / "config" / "requests.yaml").exists() else {}
    asked = {r["name"] for r in (req.get("requests") or [])
             if 0 <= (day - date.fromisoformat(str(r["date"]))).days <= req.get("days", 21)}
    out, hot = [], []
    # 화제 선수 (content/trending.py): TTL 안의 선수는 확률 3배, 풀에 없던 선수는 이 기간만 후보로 들어온다
    ev = load_yaml("events.yaml") if (ROOT / "config" / "events.yaml").exists() else {}
    tf = ROOT / "config" / "trending.yaml"
    trend = {t["name"]: t for t in ((yaml.safe_load(tf.read_text(encoding="utf-8")) or {}).get("players", []) if tf.exists() else [])
             if 0 <= (day - date.fromisoformat(str(t["date"]))).days <= ev.get("ttl_days", 14)}
    names = {p["name"] for p in pool["players"]} | {p.get("short") for p in pool["players"]}
    extra = [{"name": t["name"], "short": t.get("short") or t["name"], "sport": t["sport"], "team": t.get("team", ""),
              "weight": 1, "trending": True} for t in trend.values() if t["name"] not in names and t.get("short") not in names]
    vf = ROOT / "config" / "search_volume.yaml"
    volume = (yaml.safe_load(vf.read_text(encoding="utf-8")) or {}).get("volume", {}) if vf.exists() else {}
    from .trending import volume_factor
    ready = ready_players(today)
    for p in pool["players"] + extra:
        try:
            n = sum(1 for it in hub.news(p["name"], display=100)
                    if 0 <= (day - date.fromisoformat(it["date"])).days <= NEWS_DAYS)
        except Exception:
            n = 0
        hot_now = p["name"] in trend or p.get("short") in trend
        f = ((1 + min(2.0, n / NEWS_PER_BOOST)) * (req.get("boost", 3) if p["name"] in asked else 1)
             * (ev.get("boost", 3) if hot_now else 1) * volume_factor(volume.get(p["name"], 0)))
        f *= READY_BOOST if p["name"] in ready else 1
        # 오늘의 사건 훅 (대표 결정 2026-10-03): 화제 선수가 왜 떴는지(trending의 why)를 글 첫 문단 훅으로 넘긴다
        event = (trend.get(p["name"]) or trend.get(p.get("short")) or {}).get("why", "")
        out.append({**p, "weight": p.get("weight", 1) * f, "news": n, "event": event})  # news: 화제형이 선수를 가를 때
        if n or p["name"] in asked or hot_now:
            hot.append((f, f"{short_name(p)} 기사 {n}건" + (" · 댓글 요청" if p["name"] in asked else "")
                        + (" · 화제" if hot_now else "")))
    missing = asked - {p["name"] for p in pool["players"]}
    why = ", ".join(t for _, t in sorted(hot, reverse=True)[:5])
    if missing:
        why += f" (댓글 요청 중 풀에 없는 선수: {', '.join(sorted(missing))} → players.yaml에 추가 필요)"
    return {**pool, "players": out}, why


def short_name(p: dict) -> str:
    return p.get("short") or p["name"]


TAGS_MAX = 15  # 대표 결정 2026-09-30 (양찬군주 벤치마크: 글당 30개 → 억지 태그 없이 15개 안팎부터)


def _people(d: dict) -> list[dict]:
    return [d["a"], d["b"]] if d.get("theme") in ("same", "cross") else [d]


def _money_word(x: dict) -> str:
    return "상금" if "골프" in str(x.get("sport", "")) else "연봉"


def _league(x: dict) -> str:
    m = re.search(r"\((.+?)\)", str(x.get("sport", "")))  # "야구 (메이저리그)" → 메이저리그
    return m.group(1) if m else str(x.get("sport", "")).split(" ")[0]


def base_tags(d: dict) -> list[str]:
    """코드가 붙이는 기본 태그: 선수(짧은·전체 이름)·팀·리그·'이름+연봉'·'리그+연봉'·'연도+리그'. 글쓴이 태그 앞에 둔다."""
    if d.get("theme") == "rank":
        return ranking.tags(d)
    out = []
    for x in _people(d):
        nm, lg, mw = x.get("short_name") or x["player"], _league(x), _money_word(x)
        out += [nm, x["player"], f"{nm}{mw}", x.get("team", ""), lg, f"{lg}{mw}", f"{d.get('season', '')}{lg}"]
    return [t for t in out if t]


def search_suffix(d: dict, title: str) -> str:
    """추천 제목 뒤에 붙이는 검색어 괄호 (대표 결정 2026-09-30, 1주 시험): 사람들이 치는 '이름 연봉'을 제목에 그대로.
    예: "(이정후 연봉 2026 · 샌프란시스코 자이언츠)". 제목에 이미 있는 말은 빼고, 붙일 게 없으면 빈 문자열."""
    if d.get("theme") == "rank":
        return ranking.suffix(d, title)
    ppl = _people(d)
    flat = title.replace(" ", "")
    words = [f"{x.get('short_name') or x['player']} {_money_word(x)}" for x in ppl]
    words = [w for w in words if w.replace(" ", "") not in flat]
    if not words:
        return ""
    tail = [str(d.get("season", ""))] if str(d.get("season", "")) not in title else []
    team = ppl[0].get("team", "") if len(ppl) == 1 else ""
    words[-1] = " ".join([words[-1]] + tail)
    return "(" + " · ".join(words + ([team] if team and team not in title else [])) + ")"



TABLE_LINE = re.compile(r"^\[표 (\d+):\s*([^\]]+)\]$", re.M)


def table_of(folder: Path) -> dict | None:
    """블로그 본문에 넣을 표 1개: 선수 실제 데이터 표(table.json, 2026-10-01), 없으면 클립 표. {title, header, rows}."""
    tf, f = folder / "table.json", folder / "clip.json"
    t = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else \
        (json.loads(f.read_text(encoding="utf-8")).get("table") if f.exists() else None)
    return t if t and t.get("header") and t.get("rows") else None


def table_lines(folder: Path) -> str:
    """숫자표에 붙이는 '표 자리' 안내 + 표 내용 (AI 브리핑은 글과 네이버 표를 인용한다, 2026-10-01)."""
    t = table_of(folder)
    if not t:
        return ""
    rows = "\n".join("  " + " | ".join(map(str, r)) for r in [t["header"]] + t["rows"])
    return (f'\n표 자리 (한 줄로, 이미지 자리와 겹치지 않게 본문 중간쯤): "[표 1: {t["title"]}]"'
            f"\n표 내용 (코드가 넣는다, 본문에 숫자를 옮길 때는 이 값만):\n{rows}")


def shop_line(d: dict) -> str:
    """쇼핑커넥트 상품 자리 (2026-10-01): 체감 비교가 끝난 바로 다음 한 줄. 글은 상품을 권하지 않는다."""
    from .commerce import info
    sh = info(d)
    if not sh:
        return ""
    return (f'\n상품 자리: 비교 물건 이야기가 끝난 문단 바로 다음(표·첫 화면보다 뒤)에 "[상품 자리]" 한 줄. '
            f"대표가 {sh['name']} 상품 카드를 넣는다. 상품을 권하거나 소개하는 문장은 쓰지 않는다.")


def finish(llm, *, cfg: dict, pool: dict, notes: list[str], start_cost: float, today: str, made_today: list[str],
           out_root: Path, th: str, d: dict, facts: dict, title: str, slug: str, make_sheet, news_count: int,
           marketer: int | None = None) -> tuple[str, Path]:
    """숫자가 모인 뒤 공통: 폴더·사진·카드 → 숫자표 → 글쓰기(Claude)·검사 → 발행 패키지 → 클립."""
    tinfo = pool["themes"][th]
    if marketer:
        d["marketer"] = marketer
    folder = out_root / f"{today}-{th}-{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    photos.fetch_all(folder, d.get("sport", "야구"), folder.name)  # 키가 없으면 사진 없이
    n = ranking.build(folder, d) if th == "rank" else themes.build(folder, d)
    try:  # 블로그 표 = 선수 실제 데이터 (AI 브리핑은 '이름 연봉' 검색에 답하는 표를 인용한다, 대표 결정 2026-10-01)
        from .datatable import build as data_table
        t = data_table(d, n, facts)
        if t:
            (folder / "table.json").write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    except (KeyError, TypeError, ZeroDivisionError) as ex:
        notes.append(f"데이터 표 건너뜀 ({ex})")
    sheet = (make_sheet(n) + "\n" + "\n".join(themes.image_lines(th)) + table_lines(folder) + shop_line(d)
             + (f"\n오늘의 사건: {d['event']} (뉴스에서 확인된 오늘 화제. 제목·첫 문단을 여기에 걸고 바로 계산으로. 기사 문장 복제 금지)" if d.get("event") else "")
             + f"\n추천 제목 유형: {title_type(today, marketer or len(made_today))} (코드가 날마다 돌린다)")
    category = pool["categories"].get(d.get("sport", "야구").split()[0], "야구")  # sport = "야구 (프로야구)"
    post, problems, rounds = write_post(llm, {"category": category, "angle": tinfo["angle"]}, sheet,
                                        cfg.get("max_revisions", 2))
    cost = llm.cost_usd() - start_cost
    post["tags"] = clean_tags(base_tags(d) + list(post.get("tags", [])), TAGS_MAX)
    # 제목 뒤 검색어 괄호('(이름 연봉 2026 · 팀)')는 붙이지 않는다: 제목은 검색하는 사람의 질문 그대로 (대표 지시 2026-10-02)
    for t in post["titles"]:  # 긴 대시는 검사에서 걸러지지만, 남았으면 쉼표로 (가장 티 나는 AI 흔적)
        t["text"] = undash(t["text"])
    post["body"], post["clip_caption"] = undash(post["body"]), undash(post.get("clip_caption", ""))
    (folder / "data.yaml").write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (folder / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    if photos.credit(folder):  # Pexels 이용 조건: 작가·Pexels 표시 (숫자 검사 뒤에 붙인다)
        post["body"] = post["body"].strip() + "\n\n" + photos.credit(folder)
    (folder / "body.txt").write_text(post["body"].strip() + "\n", encoding="utf-8")
    extra = [f"{i['label']}: {i['source']}" for i in d.get("prices", [])]
    if th == "rank" and d.get("fx_label"):
        extra.append(f"환율: {d['fx_label']} (오늘 자동 글쓰기에서 뽑은 값)")
    if th == "tax":
        tx = load_yaml("tax.yaml")
        extra += [f"종합소득세 세율: {tx['source']}", f"원천징수 3.3%: {tx['withholding_source']}"]
    (folder / "post.md").write_text(package_md(f"{title} · {tinfo['name']}", th, category, facts, post,
                                               problems, rounds, cfg, news_count, cost, extra,
                                               marketers.label(marketer)),
                                    encoding="utf-8")
    for key in ("clip_caption", "clip_question"):  # 클립 설명·마지막 화면 질문 (content/clip.py가 읽는다)
        if post.get(key):
            (folder / f"{key}.txt").write_text(post[key].strip() + "\n", encoding="utf-8")
    try:  # 네이버 클립용 세로 영상 (실패해도 글은 그대로)
        notes.append(clip.make(folder))
    except Exception as ex:
        notes.append(f"클립: 오류로 건너뜀 ({ex})")
    if out_root == POSTS:
        write_index()
    head = "✅ 발행 가능" if not problems and post["gate_pass"] else "⚠️ 확인 필요: " + "; ".join(problems or ["게이트 미통과"])
    return "\n".join(notes + [f"{title} ({tinfo['name']}) 글 완성 — {head}"]), folder


def marketer_of(folder: str) -> int | None:
    f = POSTS / folder / "data.yaml"
    return ((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("marketer") if f.exists() else None)


SPORT_WORDS = {  # 소속·종목 힌트 → 종목 (대표가 지정 글에서 적은 소속, 2026-10-03)
    "mlb": ["mlb", "메이저리그", "빅리그", "마이너리그"], "kbo": ["kbo", "프로야구", "국내야구", "케이비오"],
    "epl": ["epl", "프리미어", "잉글랜드"], "laliga": ["라리가", "스페인"],
    "soccer": ["축구", "분데스", "세리에", "리그앙", "해외축구", "k리그", "케이리그"],
    "nba": ["nba", "농구", "엔비에이"], "golf": ["골프", "pga", "lpga", "상금"]}


def sport_from_hint(hint: str, pool: dict) -> str | None:
    """소속·종목 힌트에서 종목 키를 찾는다. 종목어 → 그 종목, 아니면 풀에 있는 팀 이름과 맞춰 본다."""
    h = hint.replace(" ", "").lower()
    for sp, ws in SPORT_WORDS.items():
        if any(w in h for w in ws):
            return sp
    for p in pool["players"]:   # 팀 이름(토트넘·다저스 등)으로 종목 추정
        team = (p.get("team") or "").replace(" ", "").lower()
        if team and (team in h or h in team):
            return p["sport"]
    return None


def resolve_player(pool: dict, name: str, hint: str) -> tuple[dict, str]:
    """지정 선수 이름(+소속 힌트) → (선수 dict, 안내 메모). 목록에 있으면 종목·팀 자동, 동명이인은 소속으로 가린다."""
    everyone = pool["players"]
    matches = [p for p in everyone if name in (p["name"], p.get("short"))]
    if hint and len(matches) > 1:
        h = hint.replace(" ", "")
        narrowed = [p for p in matches if h in (p.get("team", "") + p["sport"]).replace(" ", "")
                    or sport_from_hint(hint, pool) == p["sport"]]
        matches = narrowed or matches
    if len(matches) == 1:
        return matches[0], ""
    if len(matches) > 1:
        return matches[0], f"동명이인일 수 있어요: '{name}'이 목록에 여럿 — 소속팀을 적어 주시면 정확해져요 (지금은 {matches[0].get('team', '')}로 썼어요)"
    sp = sport_from_hint(hint, pool) if hint else None
    # 소속 힌트가 종목어(축구·NBA 등)면 팀은 비우고, 팀 이름이면 뉴스 검색에 쓰게 남긴다
    is_word = any(w in hint.replace(" ", "").lower() for ws in SPORT_WORDS.values() for w in ws) if hint else False
    if sp:
        return {"name": name, "short": name, "team": "" if is_word else hint, "sport": sp, "weight": 1}, ""
    return ({"name": name, "short": name, "team": hint, "sport": "kbo", "weight": 1},
            f"'{name}'은 목록에 없고 종목을 몰라 야구로 가정했어요 — 축구·농구·골프면 소속/종목을 적어 주세요 (예: {name} / 토트넘)")


def run(hub, llm, *, today: str, topic_override: str | None = None, theme: str | None = None, event_hook: str = "", trend: bool = False, team_hint: str = "",
        out_root: Path = POSTS, again: bool = False, marketer: int | None = None) -> tuple[str, Path | None]:
    """again: 발행 도우미 '다시 뽑기' — 하루 한도를 건너뛰고 다른 조합으로 쓴다 (버린 글의 선수는 최근 목록에 있어 제외된다).
    marketer: 마케터 번호 (config/marketers.yaml, 2026-10-01). 그 마케터의 선수·테마로만, 하루 1편."""
    cfg = load_yaml("post_queue.yaml")
    pool = load_yaml("players.yaml")
    made_today = [p for p in done_ids() if p.startswith(today)] if out_root == POSTS else []
    if marketer:
        made_today = [p for p in made_today if marketer_of(p) == marketer]
        cfg = {**cfg, "daily_limit": 1}
    if not topic_override and not theme and out_root == POSTS and not again:
        today_made = [p for p in made_today if (POSTS / p / "post.md").exists()
                      and "**자동 작성:**" in (POSTS / p / "post.md").read_text(encoding="utf-8", errors="ignore")
                      and mark.status(POSTS / p).get("status") != "rejected"]
        if len(today_made) >= cfg.get("daily_limit", 1):
            return f"오늘 이미 {len(today_made)}편을 만들었습니다 (하루 한도 {cfg.get('daily_limit', 1)}편).", None
    notes: list[str] = []
    start_cost = llm.cost_usd()  # 이 글에 든 비용만 (한 번 실행에서 여러 편 쓸 때 누적되지 않게)
    cache: dict[str, dict | str] = {}
    seed = (today if not made_today else f"{today}-{len(made_today)}") + (f"-m{marketer}" if marketer else "")  # 다시 뽑으면 테마도 새로
    rc = ranking.cfg()
    rank_ok = not marketer or marketers.info(marketer).get("rank")  # 마케터가 있으면 순위 글은 비교형만
    if theme == "rank" or (not theme and not topic_override and not again and not made_today and out_root == POSTS
                           and rank_ok and ranking.due(today, rc)):
        # 순위·총정리형 (대표 결정 2026-09-30): 정한 요일의 첫 후보. 못 쓰면 평소 글로 넘어간다
        from .shorts import latest_fx
        for lst in ranking.pick(today, rc):
            if marketer and not marketers.sport_ok(lst.get("league", ""), marketer, today):
                continue  # 하루 야구 1편 (2026-10-02): 오늘 이 마케터 종목이 아닌 순위 목록은 건너뜀
            got = ranking.data(lst, today, latest_fx(today))
            if isinstance(got, str):
                notes.append(f"순위 글 건너뜀 — {got}")
                continue
            d, facts = got
            return finish(llm, cfg=cfg, pool=pool, notes=notes, start_cost=start_cost, today=today,
                          made_today=made_today, out_root=out_root, th="rank", d=d, facts=facts, title=d["title"], marketer=marketer,
                          slug=d["key"], make_sheet=lambda n, d=d: ranking.sheet(d, n, cfg["constants"]), news_count=0)
        if theme == "rank":
            return "\n".join(notes + ["순위 글: 오늘 쓸 수 있는 목록이 없음 (config/rankings.yaml, 21일 안에 다 씀)"]), None
    pool, why = weighted_pool(hub, pool, today)
    if marketer and not topic_override:  # 마케터의 선수·테마만 (같은 날 다른 마케터와 선수가 겹치지 않게)
        # 하루 야구 1편 (2026-10-02): 종목으로 먼저 거르고 나서 화제형·반씩 나누기 (같은 종목 묶음 안에서 겹치지 않게)
        mine = [p for p in pool["players"] if marketers.sport_ok(p.get("sport", ""), marketer, today)]
        pool = {**pool, "players": marketers.players(mine, marketer)}
        notes.append("종목: " + ("야구 차례" if marketers.baseball_marketer(today) == marketer else "야구 말고 (축구·농구·골프)"))
        if not theme:
            pool = {**pool, "themes": {**marketers.themes(pool["themes"], marketer),
                                       **({"rank": pool["themes"]["rank"]} if "rank" in pool["themes"] else {})}}
    skip_file = Path(os.environ["AUTOPOST_SKIP"]) if os.environ.get("AUTOPOST_SKIP") else None
    skipped = set(json.loads(skip_file.read_text(encoding="utf-8"))) if skip_file and skip_file.exists() else set()
    skipped |= set(no_data_players(today))  # 최근 7일 안에 연봉·기록을 못 찾은 선수 (비용 줄이기, 2026-09-30)
    if why:
        notes.append("가중치: " + why)
    used, used_items = used_combos(today)
    pool = {**pool, "_eligible": eligible(pool)}
    override_player = None
    if topic_override:   # 지정 선수: 소속으로 종목·동명이인을 가린다 (2026-10-03)
        override_player, note = resolve_player(pool, topic_override, team_hint)
        if note:
            notes.append(note)
    for plan in themes.plans(pool, recent_players(pool.get("recent_posts", 5)) | skipped, seed, n=10,
                             override=topic_override, theme=theme, used=used, override_player=override_player):
        got = []
        for p in plan["players"]:
            if p["name"] not in cache:
                cache[p["name"]] = collect(hub, llm, themes.topic(pool, p), today, cfg)
            got.append(cache[p["name"]])
        bad = [f"{p['name']}: {g}" for p, g in zip(plan["players"], got) if isinstance(g, str)]
        if skip_file:  # 같은 날 여러 편을 쓸 때 이미 실패한 선수는 다시 모으지 않는다
            skipped |= {p["name"] for p, g in zip(plan["players"], got) if isinstance(g, str)}
            skip_file.write_text(json.dumps(sorted(skipped), ensure_ascii=False), encoding="utf-8")
        if out_root == POSTS and not topic_override:
            remember_no_data({p["name"]: g for p, g in zip(plan["players"], got) if isinstance(g, str)}, today)
        if bad:
            notes += [f"건너뜀 — {b}" for b in bad if b not in notes]
            continue
        th = plan["theme"]
        if th in ("same", "cross"):
            d = {"theme": th, "season": got[0]["d"]["season"], "sport": got[0]["d"].get("sport", "야구"),
                 "a": got[0]["d"], "b": got[1]["d"]}
            facts = {f"{k}.{key}": {**f, "label": f"{x['d'].get('short_name') or x['d']['player']} {f['label']}"}
                     for k, x in zip("ab", got) for key, f in x["facts"].items()}
        else:
            d = {**got[0]["d"], "theme": th}
            if topic_override and event_hook:  # 대표가 지정한 선수 + 사건 한 줄 (2026-10-03): 그 사건을 첫 문단 훅으로
                d["event"] = event_hook
            facts = got[0]["facts"]
            if th == "life":
                prices = load_yaml("prices.yaml")
                fallback = next((i for i in prices["items"] if i["key"] == "seoul_apt"), None)
                used_it = used_items.get(d["player"], set())
                # 당일 검색량 상위 트렌드 상품 (대표 지시 2026-10-03): 지정 글/트렌드면 검색량 1위 물건부터
                picks = themes.top_trend(prices, used_it) if trend else themes.pick_prices(prices, f"{today}-{d['player']}", used_it)
                d["prices"], pn = fill_prices(hub, llm, picks, today, fallback)
                d["prices"] = d["prices"][:1]
                notes += pn
            if th in ("place", "trip"):  # 연고지·출신지·예전 소속팀 도시 (이 선수와 아직 안 쓴 장소부터)
                me = next(p for p in pool["players"] if p["name"] == d["player"])
                cands = [x for x in places_for(pool, me) if th == "trip" or x["domestic"]]
                fresh = [x for x in cands if place_item(x, th)["key"] not in used_items.get(d["player"], set())] or cands
                if not fresh:  # 해외 선수는 국내 연고지가 없을 수 있다 (종목 돌리기, 2026-10-02)
                    notes.append(f"건너뜀 — {d['player']}: {th} 테마에 쓸 장소 없음")
                    continue
                place = random.Random(f"{seed}-{d['player']}-{th}").choice(fresh)
                d["place"] = place
                d["prices"], pn = fill_prices(hub, llm, [place_item(place, th)], today, None)
                notes += pn
                if not d["prices"]:
                    continue
            if th == "jersey":  # 유니폼 테마: 물건 = 그 팀 유니폼 (config/goods.yaml)
                g = load_yaml("goods.yaml")["teams"].get(d.get("team", ""))
                if not g:
                    notes.append(f"건너뜀 — {d['player']}: 유니폼 가격 없음 ({d.get('team', '')})")
                    continue
                d["prices"] = [{**g, "group": "goods"}]
            if th in ("life", "jersey", "place", "trip"):
                old = [i["short"] for i in d["prices"] if (date.fromisoformat(today) - date.fromisoformat(str(i["as_of"]))).days > 180]
                if old:
                    notes.append(f"가격 확인 필요 (6개월 넘음): {', '.join(old)} → config/prices.yaml·goods.yaml")
            if th == "tax" and d.get("salary_usd"):  # 외화 연봉 (해외 리그)
                notes.append(f"건너뜀 — {d['player']}: 세금 테마는 국내(원화) 연봉만")
                continue
        title = themes.title_name(d)
        slug = "-".join(x["d"].get("short_name", x["d"]["player"]).replace(" ", "") for x in got)
        return finish(llm, cfg=cfg, pool=pool, notes=notes, start_cost=start_cost, today=today, made_today=made_today,
                      out_root=out_root, th=th, d=d, facts=facts, title=title, slug=slug, marketer=marketer,
                      make_sheet=lambda n, plan=plan, d=d, got=got: theme_sheet(plan, d, n, got, cfg),
                      news_count=sum(len(x["news"]) for x in got))
    return "\n".join(notes + ["쓸 수 있는 조합을 찾지 못했습니다 (연봉 보도가 있는 선수 부족). config/players.yaml 확인 필요."]), None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="키 없이 가짜 뉴스·가짜 응답으로 모양만 확인")
    ap.add_argument("--topic", default=None, help="선수 이름 (비우면 선수 풀에서 무작위)")
    ap.add_argument("--theme", default=None, choices=["receipt", "same", "cross", "life", "tax", "jersey", "place", "trip", "rank"], help="테마 고정 (비우면 무작위)")
    ap.add_argument("--out", default=None, help="결과 폴더 (기본 posts/)")
    ap.add_argument("--again", action="store_true", help="다시 뽑기: 하루 한도를 건너뛰고 새 조합으로")
    ap.add_argument("--target", type=int, default=1, help="발행 가능한(✅) 글을 몇 편 만들지")
    ap.add_argument("--tries", type=int, default=1, help="최대 몇 번 쓸지 (⚠️ 글은 목록에서 빼고 다시 쓴다)")
    ap.add_argument("--marketer", type=int, default=None, help="마케터 번호 (config/marketers.yaml). 동시에 여러 마케터가 쓸 때")
    ap.add_argument("--event", default=None, help="대표가 지정한 선수의 오늘 사건 한 줄 (첫 문단 훅). --topic과 함께")
    ap.add_argument("--trend", action="store_true", help="생활 물가 비교를 당일 검색량 상위 상품으로 (지정 글)")
    ap.add_argument("--team", default=None, help="지정 선수 소속·종목 (동명이인·목록에 없는 선수 종목 판별). --topic과 함께")
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
    if out_root == POSTS and not a.again and not a.topic and not a.theme and not a.marketer:  # 마케터 동시 실행은 모으는 단계에서 정리
        gone = reset_drafts(today)  # 대표 결정 2026-09-30: 초안 목록은 매일 리셋
        if gone:
            print(f"지난 초안 {len(gone)}편 정리 (발행한 글은 남김)")
    made, lines, folder = 0, [], None
    for attempt in range(max(a.tries, a.target)):
        try:
            msg, folder = run(hub, llm, today=today, topic_override=a.topic, theme=a.theme, event_hook=a.event or "", trend=a.trend, team_hint=a.team or "", out_root=out_root,
                              again=a.again or made > 0, marketer=a.marketer)
        except Exception as e:  # 키·요금·API 오류: 메시지만 남기고 실패로 끝낸다 (키 값은 메시지에 없음)
            _summary(f"❌ 글쓰기 실패: {type(e).__name__}: {str(e)[:300]}\n\nClaude에게 이 화면을 알려주세요.")
            raise
        ok = bool(folder) and "✅ 자동 검사 통과" in (folder / "post.md").read_text(encoding="utf-8")
        if folder and not ok and out_root == POSTS:  # 기준 미달은 목록에서 빼고 다른 조합으로 다시 (대표 결정 2026-09-30)
            mark.mark(folder.name, "rejected")
            msg += "\n→ 기준 미달이라 목록에서 빼고 다시 씁니다."
        lines.append(f"[{attempt + 1}번째] {msg}")
        made += ok
        if made >= a.target or (not folder and "오늘 이미" in msg):
            break
        cap_usd = MARKETER_CAP_USD if a.marketer else DAILY_CAP_USD
        if llm.cost_usd() >= cap_usd:
            lines.append(f"비용 상한 ${cap_usd:.1f}에 닿아 멈춥니다.")
            break
    msg = "\n\n".join(lines) + f"\n\n결과: 발행 가능 {made}편 / 목표 {a.target}편"
    if made < a.target:
        msg += " ⚠️ 목표를 못 채웠어요 (내일 다시 시도, 계속되면 Claude가 확인)"
    if hasattr(llm, "usage"):
        u = llm.usage
        msg += (f"\nClaude 호출 {u['calls']}회 · 입력 {u['input']:,} · 출력 {u['output']:,} · 캐시 읽기 {u['cache_read']:,} 토큰"
                f" · 약 ${llm.cost_usd():.2f}")
    if getattr(llm, "by_stage", None):
        msg += "\n단계별 비용: " + ", ".join(f"{k} ${v:.2f}" for k, v in sorted(llm.by_stage.items(), key=lambda x: -x[1]))
        if out_root == POSTS:
            from .llm import log_cost
            log_cost(("다시 뽑기" if a.again else "글쓰기") + (f"·마케터{a.marketer}" if a.marketer else ""), llm, made, a.target)
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
