"""반응 좋은 제목 규칙 (config/good_rules.yaml) — 도우미 '👍 반응굿' 표시 + 제목 만들 때 참고·1개 이상 보장 (대표 지시 2026-10-08).

어떤 제목이 반응굿 유형인지는 코드(정규식)로 판단한다 (14장: 계산·판별은 코드로). 근거는 어사이드 블로거 조사
(blogs/fashion/ref/2026-10-08-패션-글방식-조사.md 3장, econ/ref/2026-10-08-경제-글방식-조사.md 4장).
"""
from __future__ import annotations

import re

from market.common import load_yaml

# (이름, 정규식) — 조사에서 반응을 올린 제목 요소만 (블로거별 공감 중앙값 대비 1.2배 이상 또는 상위 글 비율 2배 안팎)
TYPES = {
    "fashion": [
        ("비교 구도", re.compile(r"이긴|보다 |같은 (옷|가방|코트|재킷|룩)|안 밀린|밀리지 않|\bvs\b|VS|대결|누가 더")),
        ("따옴표 반응", re.compile(r"^\s*[\"“'‘]")),
        ("논란·반응 단어", re.compile(r"난리|논란|레전드|역변|ㄷㄷ|반응 폭발|갑론을박")),
    ],
    "econ": [
        ("내 돈 기준", re.compile(r"순자산|연봉|중산층|생활비|소득|가난|월급|노후 ?자금|평균 ?자산|내 집|월 ?\d+만")),
        ("논란·충격", re.compile(r"논란|충격|폭락|경고|위기|난리|날벼락|비상")),
        ("세대·나이", re.compile(r"[2-7]0대|2030|3040|4050|\d{2}세")),
        ("쉼표 반전", re.compile(r"[,，]\s*[^,，]*(따로|함정|싸다고|대체 왜|진짜 이유|반전|\?)")),
    ],
}
NAME_HIDDEN = "이름 숨김"  # 패션 그룹 1(주인공 숨김) 제목
AVOID = {"econ": re.compile(r"총정리|신청 ?방법|신청 ?조건|자격 ?조건|뜻$|뜻,|뜻 ")}  # 반응 낮은 사전형 (0.91배)


def rules(bid: str) -> dict:
    try:
        return (load_yaml("good_rules.yaml") or {}).get(bid) or {}
    except FileNotFoundError:
        return {}


def good(title: str, bid: str, typ: str = "") -> list[str]:
    """이 제목이 해당하는 반응굿 유형 이름들. 없으면 []."""
    if bid in AVOID and AVOID[bid].search(title):
        return []
    hit = [name for name, rx in TYPES.get(bid, []) if rx.search(title)]
    if bid == "fashion" and typ.startswith("그룹 1"):
        hit.insert(0, NAME_HIDDEN)
    return hit


def title_hint(bid: str) -> str:
    """제목 만들 때 덧붙일 참고. 규칙이 없으면 빈칸."""
    r = rules(bid)
    if not r.get("title"):
        return ""
    return ("\n\n[같은 분야 블로그에서 반응 좋은 제목 규칙 — 후보 중 **최소 2개는 반드시** 이 유형으로, 사실과 맞을 때만. "
            "글쓴이의 경험·처지를 지어내는 제목(~했더니, 제 연봉)은 쓰지 않습니다]\n" + "\n".join(f"- {x}" for x in r["title"]))


EXTRA = {"type": "object", "additionalProperties": False, "required": ["titles"],
         "properties": {"titles": {"type": "array", "items": {"type": "string"}}}}


def ensure(items: list[dict], bid: str, kw: str, memo: str, system: list[str], max_len: int) -> list[str]:
    """반응굿 유형 제목이 하나도 없으면 3개 더 받아 돌려준다 (대표 지시 2026-10-08 '하나쯤은 반드시'). 있으면 []."""
    if any(good(t["title"], bid, t.get("type", "")) for t in items):
        return []
    from . import econ_flow as F
    names = ", ".join(n for n, _ in TYPES.get(bid, []))
    out = F.claude_json(system, (
        f"키워드: {kw}\n\n[조사 메모]\n{memo[:6000]}\n\n아래 반응 좋은 제목 유형({names}) 중 이 주제의 사실과 맞는 것으로 "
        f"제목 3개만 만들어 주세요. 공백 포함 {max_len}자 이내, 키워드 포함, 사실에 없는 내용·가짜 경험 금지.{title_hint(bid)}"),
        EXTRA, stage="제목(반응굿 보충)")
    return [t for t in out.get("titles", []) if t.strip()][:3]
