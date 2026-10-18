"""구글(워드프레스) 블로그 글 자동 작성기.

- 주제 큐(config/google_topics.yaml)에서 아직 안 쓴 slug를 위에서부터 골라,
  구글용 글 프롬프트(prompts/project/클로드-경제-글-구글.md)로 Claude에게 본문을 생성시켜
  reports/구글글-초안/NN-slug.md 로 저장한다. 드립 발행기가 이 큐를 소진한다.
- YMYL(세무): 숫자는 2026 공식 기준, 불확실하면 '확인 권고', 끝에 출처·면책. 가짜 자격 금지.
- 키는 ANTHROPIC_API_KEY(GitHub Secrets)로만. 계산·수집은 코드, 창작은 LLM(원칙 14장).

사용법:
    python -m content.wp_write --count 2       # 다음 주제 2편 생성
    python -m content.wp_write --list          # 큐 상태만 출력(생성 안 함)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from market.common import ROOT, missing_secrets
from content import wp

QUEUE = ROOT / "reports" / "구글글-초안"
TOPICS = ROOT / "config" / "google_topics.yaml"
PROMPT = ROOT / "prompts" / "project" / "클로드-경제-글-구글.md"

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "행동형 제목(독자가 지금 겪는 상황·질문을 집는 꼴, 한글 24~32자, 낚시 금지)"},
        "body_markdown": {"type": "string", "description": "마크다운 본문(## H2·표·FAQ·'함께 보면 좋은 글'·끝에 출처/면책)"},
    },
    "required": ["title", "body_markdown"],
    "additionalProperties": False,
}


def load_topics() -> list[dict]:
    data = yaml.safe_load(TOPICS.read_text(encoding="utf-8")) or {}
    return [t for t in data.get("topics", []) if t.get("slug") and t.get("topic")]


def queue_slugs() -> set[str]:
    if not QUEUE.exists():
        return set()
    out = set()
    for f in QUEUE.glob("*.md"):
        s = wp.draft_slug(f)
        if s:
            out.add(s)
    return out


def next_index() -> int:
    mx = 0
    for f in QUEUE.glob("*.md"):
        m = re.match(r"(\d+)-", f.name)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def _system(existing_slugs: list[str]) -> list[str]:
    guide = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else ""
    links = "\n".join(f"- /{s}" for s in existing_slugs[:8]) or "- (아직 없음)"
    rules = (
        "너는 위 지침을 따르는 구글(워드프레스) 블로그 글 작성기다. 출력은 JSON 스키마에 맞춘다.\n"
        "- body_markdown 형식: 첫 문단에 핵심 직답(전문용어 없이 1~2문장, 이 글로 뭘 해결하는지)"
        " → '> 핵심 3줄' 인용 박스 → '## 쉽게 이해하기: OO씨 이야기'(아래 쉬운 풀이 규칙) → 질문형 ## H2"
        " 섹션들(필요하면 마크다운 표)과 '## 자주 묻는 질문' → '## 함께 보면 좋은 글'(아래 기존 글 중 1~2개를"
        " [제목](/slug)로) → 맨 끝 '---' 다음 줄에 출처와 면책(2026년 기준·최종 수정일·국세청 126 확인 권고).\n"
        "- 쉬운 풀이(비전문가 기준·체류 유도): 글 앞부분에 독자가 공감할 '가상의 예시 상황'을 설정해"
        " 스토리텔링으로 개념을 풀어라. 예) '연봉 5,000만원 직장인 A씨가 ~라면'처럼 가상의 인물·상황에"
        " 어려운 숫자·제도를 대입해 '내 얘기'처럼 이해되게. 이후 섹션에서도 이 사례를 이어 설명하면 좋다.\n"
        "  ★ 반드시 '예를 들어/가정하면/가상의 사례'로 가상임을 분명히 한다. 실존 인물·실제 경험·후기로"
        " 꾸미지 말 것(지어낸 진짜 경험담은 금지, 명시적 예시는 허용). 예시 속 숫자도 공식 기준으로 정확히.\n"
        "- 제목(title)은 '행동형'으로: 독자가 지금 겪는 상황·막힌 질문을 집어 검색창에 칠 말로 쓴다. 트리거 예:\n""  넘겼으면/탈락/거절/초과/놓쳤을 때/통보 왔는데/얼마/어떻게/해당되나. 연도·핵심 키워드는 넣되,\n""  '총정리/정리/완벽' 같은 설명형 상투어는 피한다. 단, 본문에서 못 지킬 약속·공포·물음표 낚시는 금지.\n"
        "- YMYL: 세율·공제 한도 등 숫자는 2026년 공식 기준으로 정확히. 불확실하면 단정 말고 '확인 권고'."
        " 가짜 자격·세무사 사칭·투자권유·절세 과장 금지.\n"
        "- 사람이 쓴 글처럼: 편집자의 관점·판단·견해를 담아라. 예) '개인적으로는 이 제도에서 ~가 가장"
        " 아쉽다', '실무에서 가장 많이 놓치는 건 ~', '이 글을 보는 분은 아마 ~한 상황일 것이다'처럼"
        " 독자 공감·의견·우선순위를 드러내고, 어조와 문장 길이에 리듬을 줘라(판박이 도입부·'결론적으로'·"
        "과한 목록화·기계적 헤지 표현 피하기).\n"
        "  단, 지어낸 개인 경험·후기·사례('내가 작년에 환급받았다' 류)·가짜 인물·가짜 자격은 절대 금지"
        "(규칙·구글 정책 위반). 경험담이 아니라 '전문가 에디터의 견해·분석·판단'으로 사람 냄새를 낸다.\n"
        "- 분량은 충실히(정보 이득). 표가 어울리면 마크다운 표로.\n"
        f"기존 글(내부링크용 slug):\n{links}"
    )
    return [guide, rules] if guide else [rules]


LOW_WATER = 10   # 대기 주제가 이 수 미만이면 새 주제를 자동 보충(큐 고갈 방지)
REFILL = 15      # 한 번에 보충할 주제 수
CATS = ("jaetech", "realty", "tax", "pension")

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topics": {"type": "array", "items": {
        "type": "object",
        "properties": {"slug": {"type": "string"}, "cat": {"type": "string", "enum": list(CATS)},
                       "topic": {"type": "string"}},
        "required": ["slug", "cat", "topic"], "additionalProperties": False}}},
    "required": ["topics"], "additionalProperties": False,
}


def valid_new_topics(raw: list[dict], known: set[str]) -> list[dict]:
    """LLM이 준 주제 중 형식·중복 검사를 통과한 것만(slug 영소문자-하이픈, 기존과 겹치지 않음)."""
    out, seen = [], set(known)
    for t in raw:
        slug = str(t.get("slug", "")).strip()
        topic = str(t.get("topic", "")).strip()
        if (re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) and t.get("cat") in CATS
                and len(topic) >= 10 and slug not in seen):
            out.append({"slug": slug, "cat": t["cat"], "topic": topic})
            seen.add(slug)
    return out


def replenish_topics(llm, topics: list[dict], n: int = REFILL) -> int:
    """주제 큐가 줄면 Claude로 거래의도형(비교·비용·신청·요건) 세무·절세·연금·재테크 주제를 n개 보충해
    config/google_topics.yaml 맨 아래에 덧붙인다. 반환: 실제로 추가한 개수."""
    known = {t["slug"] for t in topics}
    sample = "\n".join(f"- {t['slug']}: {t['topic']}" for t in topics[-40:])
    system = [
        "너는 한국 세무·절세·연금·재테크 정보 블로그의 주제 기획자다. 검색 수요가 있고 거래의도"
        "(요건·한도·비용·신청 방법·비교·기한)가 있는 evergreen 주제만 제안한다. 투자 권유·종목 추천·"
        "단정 전망 주제, 시사 뉴스성 주제는 제외. slug는 영문 소문자-하이픈. cat은 "
        f"{', '.join(CATS)} 중 하나. topic은 한글 한 줄(핵심 키워드와 다룰 범위)."]
    prompt = (f"새 주제 {n}개를 제안하라. 아래 기존 주제와 겹치거나 비슷하면 안 된다.\n"
              f"기존 주제(최근 일부):\n{sample}")
    out = llm.ask_json(system, prompt, TOPIC_SCHEMA, model="claude-sonnet-5-5",
                       effort="medium", max_tokens=4000, stage="주제보충")
    new = valid_new_topics(out.get("topics", []), known)
    if not new:
        return 0
    lines = ["  # 자동 보충 " + __import__("datetime").date.today().isoformat()]
    for t in new:
        lines += [f"  - slug: {t['slug']}", f"    cat: {t['cat']}",
                  f"    topic: {t['topic']}"]
    text = TOPICS.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    TOPICS.write_text(text, encoding="utf-8")
    return len(new)


def generate_one(llm, topic: dict, existing_slugs: list[str], idx: int) -> Path:
    system = _system(existing_slugs)
    prompt = (f"주제: {topic['topic']}\n슬러그(참고): {topic['slug']}\n"
              "이 주제로 구글 블로그 글 1편을 써라. body_markdown과 title만 채운다.")
    out = llm.ask_json(system, prompt, SCHEMA, model="claude-opus-4-8",
                       effort="high", max_tokens=12000, stage="구글글")
    title = out["title"].strip()
    body = out["body_markdown"].strip()
    cat = topic.get("cat", "")
    cat_line = f"분류: {cat}\n" if cat else ""
    path = QUEUE / f"{idx:02d}-{topic['slug']}.md"
    path.write_text(f"제목: {title}\n슬러그: {topic['slug']}\n{cat_line}\n---\n\n{body}\n",
                    encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="구글 블로그 글 자동 작성기")
    ap.add_argument("--count", type=int, default=2, help="생성할 편수(기본 2)")
    ap.add_argument("--list", action="store_true", help="큐 상태만 출력")
    args = ap.parse_args(argv)

    topics = load_topics()
    done = queue_slugs()
    pending = [t for t in topics if t["slug"] not in done]

    if args.list:
        print(f"주제 {len(topics)}개 · 작성됨 {len(topics) - len(pending)}개 · 대기 {len(pending)}개")
        for t in pending[:10]:
            print(f"  - {t['slug']}: {t['topic']}")
        return 0

    missing = missing_secrets("anthropic")
    if missing:
        print("ANTHROPIC_API_KEY가 없습니다(글 생성 불가).", file=sys.stderr)
        return 3

    from content.llm import Claude, log_cost
    llm = Claude()
    if len(pending) < LOW_WATER:
        try:
            added = replenish_topics(llm, topics)
            print(f"[주제 보충] 대기 {len(pending)}개 < {LOW_WATER} → {added}개 추가")
            if added:
                topics = load_topics()
                pending = [t for t in topics if t["slug"] not in done]
        except Exception as e:  # noqa: BLE001  (보충 실패해도 남은 주제로 계속)
            print(f"[주제 보충 실패] {type(e).__name__}: {e}", file=sys.stderr)
    if not pending:
        print("큐의 모든 주제를 다 썼고 보충도 못 했어요. config/google_topics.yaml에 주제를 추가하세요.")
        return 1
    QUEUE.mkdir(parents=True, exist_ok=True)
    idx = next_index()
    made = 0
    for t in pending[: args.count]:
        try:
            p = generate_one(llm, t, sorted(done), idx)
        except Exception as e:  # noqa: BLE001  (한 편 실패해도 다음 편 시도)
            print(f"[실패] {t['slug']}: {e}", file=sys.stderr)
            continue
        print(f"[작성] {p.name}")
        done.add(t["slug"])
        idx += 1
        made += 1
    log_cost("구글글", llm, made=made, target=args.count)
    print(f"완료: {made}편 생성 (비용 ${llm.cost_usd():.3f})")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
