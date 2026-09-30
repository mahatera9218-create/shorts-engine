"""자동 글쓰기 예시 모드: 키 없이 가짜 뉴스·가짜 Claude 응답으로 전체 흐름을 돌려 본다.

숫자는 모두 가짜다. 결과를 발행하거나 판단에 쓰면 안 된다.
"""
from __future__ import annotations

import re

from .autopost import BRIEF_KEYS, EXTRACT_SCHEMA, POST_SCHEMA, PRICE_SCHEMA, REVIEW_CRITERIA, REVIEW_SCHEMA


class FakeNewsHub:
    def news(self, query: str, display: int = 30) -> list[dict]:
        if "평균 매매" in query:  # 예시 지역 아파트 평균 매매가 기사 (가짜 가격)
            return [{"title": f"[예시] {query} 기사", "description": "8월 기준 아파트 평균 매매가격은 3억 2,450만원으로 집계됐다",
                     "link": "https://example.com/region/1", "date": "2026-09-20"}]
        if "실거래" in query:  # 예시 아파트 실거래 기사 (가짜 가격)
            return [{"title": f"[예시] {query} 기사", "description": "전용 84㎡가 지난달 12억3000만원에 거래됐다",
                     "link": "https://example.com/apt/1", "date": "2026-09-20"}]
        base = [
            ("2026-09-28", "시즌 결산 기사", "올 시즌 30경기 150이닝 10승 140탈삼진"),
            ("2026-09-20", "중간 기사", "29경기 145이닝 9승 135탈삼진"),
            ("2026-09-25", "계약 기사", "올해 연봉 20억원"),
            ("2026-09-29", "환율 기사", "원달러 환율 1,350.0원 마감"),
        ]
        return [{"title": f"[예시] {query} {t}", "description": desc, "link": f"https://example.com/{abs(hash(query)) % 999}/{i}",
                 "date": day} for i, (day, t, desc) in enumerate(base)]


class FakeClaude:
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}

    def cost_usd(self) -> float:
        return 0.0

    def ask_json(self, system, prompt, schema, **_):
        self.usage["calls"] += 1
        if schema == EXTRACT_SCHEMA:
            src = {k: int(n) for n, k in re.findall(r"\[(\d+)\] \([^)]*\) \[예시\] \S+ \S+ (\S+) 기사", prompt)}
            s_end, s_mid, s_pay = src.get("결산", 1), src.get("중간", 2), src.get("계약", 3)
            return {"usable": True, "reason": "", "season": 2026, "salary_currency": "KRW",
                    "salary_basis": "예시 계약 중 2026년 연봉, 보도 기준",
                    "facts": [{"key": "salary", "label": "올해 연봉", "value": 2_000_000_000, "unit": "KRW", "source": s_pay},
                              {"key": "games", "label": "경기", "value": 30, "unit": "경기", "source": s_end},
                              {"key": "games", "label": "경기", "value": 29, "unit": "경기", "source": s_mid},
                              {"key": "innings", "label": "이닝", "value": 150, "unit": "이닝", "source": s_end},
                              {"key": "innings", "label": "이닝", "value": 145, "unit": "이닝", "source": s_mid},
                              {"key": "wins", "label": "승", "value": 10, "unit": "승", "source": s_end},
                              {"key": "strikeouts", "label": "탈삼진", "value": 140, "unit": "개", "source": s_end}],
                    "units": [{"key": "games", "label": "1경기"}, {"key": "innings", "label": "1이닝"},
                              {"key": "wins", "label": "1승"}, {"key": "strikeouts", "label": "1탈삼진"}],
                    "headline_unit": "wins",
                    "story": [{"point": "올 시즌을 선발로 마쳤다", "source": s_end}]}
        if schema == PRICE_SCHEMA:
            if "지역:" in prompt:
                return {"found": True, "price_krw": 324_500_000, "deal_date": "2026-08", "source": 1}
            return {"found": True, "price_krw": 1_230_000_000, "deal_date": "2026-08", "source": 1}
        if schema == REVIEW_SCHEMA:
            return {"scores": [{"criterion": c, "score": 4, "reason": "예시"} for c in REVIEW_CRITERIA], "fixes": []}
        if schema == POST_SCHEMA:
            per = dict(re.findall(r"^(1\S+)당: (\S+)", prompt, re.M))
            win = per.get("1승", "?")
            marks = re.findall(r'"(\[이미지 \d+_[^\]]+\])"', prompt)  # 테마별 이미지 자리 (숫자표의 안내 그대로)
            lines = ["이 글은 예시예요. 숫자는 모두 가짜고, 모양만 확인하는 용도죠.", "먼저 맞혀 보세요.", "정답은 이래요.",
                     "\n".join(f"{k}에 {v}." for k, v in per.items()) or "비교해 보면 이래요.", "올 시즌은 이랬어요."]
            body = f"1승에 {win}.\n\n예시선수가 올해 거둔 승리 하나의 값이에요.\n\n" + "\n\n".join(
                f"{m}\n\n{lines[i] if i < len(lines) else '생각보다 크죠?'}" for i, m in enumerate(marks))
            body += "\n\n생각보다 크죠? 내년에는 어떨까요?\n\n기준: 예시 데이터예요. 실제 선수·실제 숫자가 아니에요."
            return {"brief": {k: f"예시 {v}" for k, v in BRIEF_KEYS.items()},
                    "clip_caption": "예시선수 1승 값, 얼마일까요?\n여러분 생각은?", "clip_question": "다음은 누구 몸값?",
                    "gate_pass": True, "info_gain": "예시: 새로 계산한 숫자",
                    "titles": [{"text": f"예시선수 1승에 {win} (예시)", "type": "숫자형"},
                               {"text": "예시선수 한 경기에 얼마? (예시)", "type": "질문형"},
                               {"text": "예시선수 최저임금과 비교 (예시)", "type": "대비형"},
                               {"text": "예시선수 몸값 순위 (예시)", "type": "순위형"},
                               {"text": "예시선수 올해 10승인데 얼마? (예시)", "type": "반전형"}],
                    "recommended": 5, "body": body, "tags": ["예시선수", "예시"], "cross_compare": "없음 (예시)"}
        raise ValueError("알 수 없는 스키마")
