"""제목 고수 조사 (대표 지시 2026-10-05: "제목을 진짜 잘 짓는다함. 어떤 제목을 써왔고 쓰고 있는지 조사 후 제목 후보에서 보이게").

1) 모으기 (AI 없음, 0원): config/title_masters.yaml 블로거의 공개 RSS(rss.blog.naver.com/<아이디>.xml, 네이버가 허용한 통로)에서
   제목·날짜·카테고리를 econ/ref/titles/<아이디>.yaml 에 쌓는다. RSS는 최근 글(약 50개)만 주므로, 돌릴 때마다 새 제목이 더해져 기록이 길어진다.
   글 본문 페이지는 긁지 않는다.
2) 분석 (Claude 1번, 약 100원): 제목의 '구조'(길이·숫자·물음·괄호·말투·자주 쓰는 틀)만 뽑아 econ/ref/titles/제목-공식.md 에 남긴다.
   → 발행 도우미 ② 제목 고르기 칸에 보이고, 쿠니네(content/kunine.py)·연예패션(content/celeb.py) 제목 만들 때 참고로 들어간다.
   남의 제목 문장을 그대로 옮기지 않는다(구조만 참고).

사용법: python -m content.title_refs
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from market.common import ROOT

CFG = ROOT / "config" / "title_masters.yaml"
OUT = ROOT / "econ" / "ref" / "titles"
GUIDE = OUT / "제목-공식.md"

PATTERN = {"type": "object", "additionalProperties": False, "required": ["masters", "formulas", "use_tips"],
           "properties": {
               "masters": {"type": "array", "items": {
                   "type": "object", "additionalProperties": False,
                   "required": ["id", "topics", "style", "strong_points"],
                   "properties": {
                       "id": {"type": "string"},
                       "topics": {"type": "string", "description": "주로 어떤 주제·카테고리로 쓰나 (1~2줄)"},
                       "style": {"type": "string", "description": "제목 모양: 평균 길이, 숫자·물음표·괄호·따옴표·느낌표 쓰는 비율, 말투, 앞/뒤에 무엇을 두나 (4~6줄)"},
                       "strong_points": {"type": "string", "description": "클릭하게 만드는 장치 3~5개 (호기심·손익·비교·시점·대상 지목 등)"}}}},
               "formulas": {"type": "array", "description": "우리가 그대로 쓸 수 있는 제목 틀 6~10개. 빈칸은 [키워드] [숫자] [대상] 처럼",
                            "items": {"type": "object", "additionalProperties": False, "required": ["frame", "when", "who"],
                                      "properties": {"frame": {"type": "string"},
                                                     "when": {"type": "string", "description": "어떤 주제에 맞나"},
                                                     "who": {"type": "string", "description": "누구에게서 본 틀인가 (이름)"}}}},
               "use_tips": {"type": "string", "description": "경제·연예·패션 블로그 제목에 쓸 때 주의점 3~5줄 (과장·낚시·투자 권유 금지 지키면서)"}}}


def masters() -> dict[str, str]:
    return (yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}).get("masters") or {}


def history(bid: str) -> list[dict]:
    p = OUT / f"{bid}.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("posts", []) if p.exists() else []


def collect() -> dict[str, list[dict]]:
    from .econ_refs import feed
    OUT.mkdir(parents=True, exist_ok=True)
    got = {}
    for bid, name in masters().items():
        old = history(bid)
        seen = {p["title"] for p in old}
        try:
            new = [{"title": x["title"], "at": x["at"].strftime("%Y-%m-%d %H:%M"), "category": x["category"]}
                   for x in feed(bid) if x["title"] and x["title"] not in seen]
        except Exception as ex:  # 하나가 막혀도 나머지는 계속
            print(f"{name}({bid}) RSS 실패: {ex}")
            new = []
        posts = sorted(old + new, key=lambda p: p["at"], reverse=True)
        (OUT / f"{bid}.yaml").write_text(yaml.safe_dump(
            {"id": bid, "name": name, "updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "posts": posts},
            allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"{name}({bid}): 새 제목 {len(new)}개, 모두 {len(posts)}개")
        got[bid] = posts
    return got


def analyze(got: dict[str, list[dict]]) -> None:
    from . import econ_flow as F
    F.guard()
    names = masters()
    data = "\n\n".join(f"## {names[b]} ({b}) — 제목 {len(ps)}개\n" + "\n".join(f"- [{p['category']}] {p['title']}" for p in ps[:80])
                       for b, ps in got.items() if ps)
    if not data:
        print("모은 제목이 없어 분석을 건너뜀")
        return
    r = F.claude_json(
        ["너는 네이버 블로그 제목을 분석하는 편집자다. 문장을 베끼지 않고, 따라 쓸 수 있는 '구조'만 뽑는다. "
         "틀(frame)에는 원래 제목의 고유한 문구를 남기지 말고 [키워드]·[숫자]·[대상] 같은 빈칸으로 바꾼다."],
        f"제목을 잘 짓는다고 알려진 블로거들의 최근 제목입니다.\n\n{data}\n\n"
        "블로거별 특징, 우리가 쓸 수 있는 제목 틀, 주의점을 JSON으로 주세요.", PATTERN, stage="제목 고수 분석")
    lines = [f"# 제목 고수 공식 ({F.today()})", "",
             "대표 지정 제목 고수의 공개 RSS 제목을 모아 '구조'만 뽑았다. 문장은 베끼지 않는다.", ""]
    for m in r["masters"]:
        bid = next((b for b in names if b in m["id"]), m["id"])  # Claude가 '이름 (아이디)'로 줄 때도 있음
        lines += [f"## {names.get(bid, bid)} ({bid})", f"- 주제: {m['topics']}", f"- 모양: {m['style']}",
                  f"- 클릭 장치: {m['strong_points']}", ""]
    lines += ["## 따라 쓸 제목 틀"] + [f"- {f['frame']} — {f['when']} ({f['who']})" for f in r["formulas"]]
    lines += ["", "## 쓸 때 주의", r["use_tips"], ""]
    GUIDE.write_text("\n".join(lines), encoding="utf-8")
    F.log_cost("titlerefs", "제목 고수 분석")
    print(GUIDE.read_text(encoding="utf-8"))


def for_blog(bid: str | None = None) -> dict[str, str]:
    """이 블로그가 참고할 제목 고수 (config/blogs.yaml의 title_masters, 없으면 전부). 경제 = 경제토르, 패션 = 유미 (2026-10-05)."""
    from .blogs import get
    allm = masters()
    pick = get(bid).get("title_masters") or list(allm)
    return {k: allm[k] for k in pick if k in allm}


def guide_text(bid: str | None = None) -> str:
    """제목 만들 때 Claude에 붙이는 참고 (없으면 빈칸). 이 블로그의 고수 부분만 남긴다."""
    if not GUIDE.exists():
        return ""
    names = set(for_blog(bid).values())
    keep, on = [], True
    for line in GUIDE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            head = line[3:].split(" (")[0].strip()
            on = head in names or head not in set(masters().values())  # 다른 블로그 고수 칸만 뺌
        elif on and line.startswith("- ") and line.rstrip().endswith(")"):  # 틀 줄 끝 "(누구)"가 다른 블로그 고수면 뺌
            who = line.rstrip()[:-1].rsplit("(", 1)[-1].strip()
            if who in set(masters().values()) and who not in names:
                continue
        if on:
            keep.append(line)
    return ("[참고: 제목 고수 공식 — 구조만 참고하고 문장은 베끼지 말 것. 위 원문 규칙과 부딪히면 원문 규칙이 우선]\n"
            + "\n".join(keep)[:5000])


def deep_doc(bid: str) -> Path:
    return OUT / f"{masters().get(bid, bid)}-심층.md"


VERSION_SCHEMA = {"type": "array", "description": "제목 고수 방식 제목 (고수마다 3개)",
                  "items": {"type": "object", "additionalProperties": False, "required": ["who", "titles"],
                            "properties": {"who": {"type": "string"}, "titles": {"type": "array", "items": {"type": "string"}}}}}


def versions_ask(bid: str | None = None) -> str:
    """제목 후보에 붙일 '고수 방식 3개씩' 요청 (대표 지시 2026-10-06: 토르 버전·유미 버전 3개씩)."""
    ms = for_blog(bid)
    if not ms:
        return ""
    parts = [f"그리고 versions 칸에 아래 제목 고수마다 그 사람 방식으로 제목 3개씩 주세요(who = {', '.join(ms.values())}). "
             "같은 키워드·조사 메모의 사실로만, 그 사람의 제목 구조·말투·결을 따르되 문구는 베끼지 말 것. "
             "투자 권유·단정 전망·외모 비하·과장된 거짓은 쓰지 않음."]
    for b, name in ms.items():
        parts.append(f"\n[{name} 최근 제목]\n" + "\n".join(f"- {p['title']}" for p in history(b)[:12]))
        if deep_doc(b).exists():
            parts.append(f"[{name} 심층 분석 요약]\n" + deep_doc(b).read_text(encoding="utf-8")[:2500])
    return "\n".join(parts)


DEEP = {"type": "object", "additionalProperties": False,
        "required": ["topics", "titles", "structure", "voice", "thumbnail", "tags_time", "rules"],
        "properties": {k: {"type": "string", "description": d} for k, d in {
            "topics": "주제를 어떻게 고르나 (인물·아이템·가격·시점, 분야 비중, 무엇이 반응 좋아 보이나)",
            "titles": "제목 공식 (유형별 틀과 비율, 길이·기호·말투, 첫 15자에 무엇을 두나)",
            "structure": "글 구성 (요약에서 보이는 도입·흐름·문단 길이·사진 수·글 길이)",
            "voice": "말투·어미·감탄·독자에게 말 거는 방식",
            "thumbnail": "썸네일 구성 (사진/합성/글자 유무·위치·색, 인물·제품 배치)",
            "tags_time": "태그 쓰는 법, 카테고리, 발행 시간대·하루 편수",
            "rules": "우리(캐시미어 다이어리·억선생의 경제판)가 따라 할 규칙 6~10개 — 문장 복사·외모 비하·가짜 경험은 빼고"}.items()}}


def deep(bid: str) -> None:
    """심층 조사: 공개 RSS 최근 글 전부(제목·카테고리·태그·요약·그림 수·시간) + 최근 썸네일 8장을 Claude가 보고 정리."""
    from . import econ_flow as F
    from .econ_refs import _image, feed
    name = masters().get(bid, bid)
    items = feed(bid)
    if not items:
        print(f"{name} RSS 없음")
        return
    lines = [f"{name}({bid}) 공개 RSS 최근 글 {len(items)}개"]
    for i in items:
        lines.append(f"- {i['at']:%m-%d %a %H:%M} [{i['category']}] {i['title']} · 그림 {len(i['imgs'])} · 요약 {i['text_len']}자 · "
                     f"태그 {', '.join(i['tags'][:8])}\n  요약: {i.get('summary', '')[:200]}")
    content = [{"type": "text", "text": "\n".join(lines)}]
    for i in [x for x in items if x["imgs"]][:8]:
        img = _image(i["imgs"][0])
        if img:
            content += [{"type": "text", "text": f"↓ '{i['title']}' 썸네일"}, img]
    content.append({"type": "text", "text": (
        f"위는 블로거 {name}의 공개 RSS 최근 글과 썸네일입니다. 이 블로거를 우리가 배울 수 있게 아주 자세히 분석해 주세요. "
        "보이는 것만 쓰고 추측은 '추측'이라고 표시. 남의 문장은 길게 옮기지 말고 모양만 설명.")})
    import anthropic
    import json as _json
    with anthropic.Anthropic().messages.stream(model="claude-sonnet-5-5", max_tokens=12000, messages=[{"role": "user", "content": content}],
                                               output_config={"format": {"type": "json_schema", "schema": DEEP}}) as st:
        msg = st.get_final_message()
    u = msg.usage
    F.SPENT["claude"] += (u.input_tokens * 2.0 + u.output_tokens * 10.0) / 1_000_000
    r = _json.loads("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))
    md = [f"# {name} 심층 분석 ({F.today()}, 공개 RSS 최근 {len(items)}개)", ""]
    for k, h in (("topics", "주제 고르는 법"), ("titles", "제목 공식"), ("structure", "글 구성"), ("voice", "말투"),
                 ("thumbnail", "썸네일"), ("tags_time", "태그·카테고리·발행 시간"), ("rules", "우리가 따라 할 규칙")):
        md += [f"## {h}", r[k], ""]
    deep_doc(bid).write_text("\n".join(md), encoding="utf-8")
    F.log_cost("titlerefs", f"{name} 심층")
    print(deep_doc(bid).read_text(encoding="utf-8")[:1500])


def main() -> None:
    analyze(collect())
    for b in (yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}).get("deep") or []:
        try:
            deep(b)
        except Exception as ex:  # noqa: BLE001 — 심층이 실패해도 제목 공식은 남김
            print(f"심층 실패 {b}: {ex}")


if __name__ == "__main__":
    main()
