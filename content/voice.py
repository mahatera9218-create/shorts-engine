"""문체 분석과 AI 티 검사 (blog-voice 스킬).

- style_metrics: 문장 끝맺음·물음표·문장 길이 등 말투 특징을 숫자로 뽑는다. 남의 문장은 저장하지 않고 수치만 쓴다.
- check_draft: 초안에서 AI 티 나는 표현과 너무 고른 문장 길이를 잡아낸다.

사용법: python -m content.voice 초안.md
"""
from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

SENT_SPLIT = re.compile(r"(?<=[.!?…~])\s+|\n+")
ENDINGS = {
    "요": re.compile(r"요[.!?~…]*$"),
    "다": re.compile(r"다[.!?~…]*$"),
    "죠": re.compile(r"죠[.!?~…]*$"),
    "음/함": re.compile(r"(음|함|임)[.!?~…]*$"),
    "질문": re.compile(r"\?$"),
}

# AI 티 나는 표현 (발견되면 고친다). 운영하며 추가한다.
AI_PHRASES = [
    "알아보겠습니다", "알아보도록 하겠습니다", "살펴보겠습니다", "살펴보도록", "정리해 보겠습니다",
    "결론적으로", "요약하자면", "종합해 보면", "다양한", "중요한 역할", "주목할 만한", "눈여겨볼",
    "~에 대해", "에 대해 이야기", "이번 글에서는", "오늘은 ", "도움이 되셨길", "도움이 되었으면",
    "마무리하며", "마치며", "궁금하셨죠", "한눈에 정리", "완벽 정리", "총정리해 드리",
    "것입니다", "할 수 있습니다", "라고 할 수 있", "에 해당합니다",
]


def sentences(text: str) -> list[str]:
    text = re.sub(r"[#>*|`\-]+", " ", text)
    return [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) >= 4]


def style_metrics(texts: list[str]) -> dict:
    sents = [s for t in texts for s in sentences(t)]
    n = len(sents) or 1
    lengths = [len(s) for s in sents] or [0]
    out = {"sentences": len(sents)}
    for name, pat in ENDINGS.items():
        out[name] = sum(1 for s in sents if pat.search(s)) / n
    out["느낌표"] = sum(1 for s in sents if "!" in s) / n
    out["평균길이"] = statistics.mean(lengths)
    out["길이편차"] = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
    return out


def check_draft(text: str) -> list[str]:
    problems = []
    for p in AI_PHRASES:
        c = text.count(p.replace("~", ""))
        if c:
            problems.append(f"AI 티 표현 '{p.replace('~', '')}' {c}회")
    m = style_metrics([text])
    cv = m["길이편차"] / m["평균길이"] if m["평균길이"] else 0
    if m["sentences"] >= 8 and cv < 0.25:
        problems.append(f"문장 길이가 너무 고름 (편차/평균 {cv:.2f}) → 짧은 문장·긴 문장을 섞기")
    if m["sentences"] >= 8 and m["다"] > 0.6:
        problems.append(f"'~다'로 끝나는 문장 {m['다']:.0%} → 보고서 말투. '~요'·'~죠'·질문을 섞기")
    if m["sentences"] >= 8 and m["질문"] == 0:
        problems.append("질문이 하나도 없음 → 독자에게 묻는 문장 1~2개")
    return problems


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m content.voice 초안.md")
        sys.exit(2)
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    problems = check_draft(text)
    m = style_metrics([text])
    print(f"문장 {m['sentences']}개 · 평균 {m['평균길이']:.0f}자 · 편차 {m['길이편차']:.1f} · "
          f"~요 {m['요']:.0%} · ~다 {m['다']:.0%} · ~죠 {m['죠']:.0%} · 질문 {m['질문']:.0%}")
    print("\n".join(f"- {p}" for p in problems) or "문제 없음")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
