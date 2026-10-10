"""해시태그 다듬기 (대표 지적 2026-10-10: 네이버 검색에서 '#애플주가'와 '애플 주가'로 노출이 다르다).

네이버 해시태그는 띄어쓰기에서 끊긴다('#애플 주가' → 태그는 '#애플'만). 그래서 태그는 붙여 쓰고,
핵심 키워드는 붙인 형태(애플주가)와 낱말(애플·주가)을 둘 다 넣어 두 가지 검색 모두에 걸리게 한다.
띄어 쓴 형태('애플 주가')는 제목·본문 문장에 자연스럽게 들어가게 프롬프트에서 맡긴다.
"""
from __future__ import annotations

import re

NUM = re.compile(r"[\d,.]+(만|억|조)?(원|달러|%)?|\d+[가-힣]{0,2}")  # 1520만원·3분기 같은 숫자 낱말은 태그로 안 씀


def core_tags(kw: str) -> list[str]:
    """키워드 앞 두 낱말 → [붙인 형태, 낱말1, 낱말2]. 숫자 낱말은 뺀다."""
    words = [w for w in kw.split() if not NUM.fullmatch(w)][:2]
    if len(words) < 2:
        return words
    return ["".join(words)] + words


def fix(tags: list[str], kw: str, n: int) -> list[str]:
    """띄어쓰기·# 없애고, 핵심 키워드 태그를 맨 앞에 보장, 중복 빼고 n개까지."""
    clean = [re.sub(r"[#\s]", "", t) for t in tags if t and t.strip()]
    out = list(dict.fromkeys(core_tags(kw) + clean))
    return out[:n]
