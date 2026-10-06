"""참고 블로거 조사 (대표 지시 2026-10-05): 공개 RSS로, 대표 개입 없음.

매일(기본): 새 글 제목만 모은다 (AI 없음, 0원) → econ/ref/rss/<날짜>.yaml·.md → 키워드 점수(content/econ_score.py)
--analyze : 아래 '틀' 분석을 한 번 더 (2026-10-05에 한 번 함, 대표: "틀은 됐고 새 글 키워드만") → econ/ref/참고-블로거-틀.md

대표가 정한 참고 블로거(config/econ_refs.yaml)의 공개 RSS(rss.blog.naver.com/<아이디>.xml, 네이버가 허용한 통로)를 읽어
  - 어제·오늘 무슨 주제로 썼나 (제목·카테고리·태그·시각)
  - 제목은 어떻게 썼나 (길이·숫자·물음표·괄호 같은 모양)
  - 썸네일은 어떻게 구성됐나 (RSS에 실린 대표 그림을 Claude가 보고 구성만 글로 적음, 그림 파일은 저장하지 않음)
  - 글 구성은 RSS에 보이는 만큼만 (요약 글자 수·그림 수). 표·글꼴·정렬·인용·구분선은 RSS에 없어 Aside 몫
을 정리해 econ/ref/rss/<날짜>.md(읽기용)·.yaml(키워드 점수 content/econ_score.py가 읽음)로 남긴다.
최우선 블로거(config main, zkfldb888)는 썸네일 최근 8장을 따로 보고 '썸네일·이미지 방식'을 규칙으로 정리한다.
남의 제목·문장은 참고 자료로만 두고 글에는 옮기지 않는다(글쓰기 규칙). 글 본문 페이지는 긁지 않는다.

사용법: python -m content.econ_refs [--analyze]
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

from market.common import ROOT
from . import econ_flow as F

CFG = ROOT / "config" / "econ_refs.yaml"
OUT = ROOT / "econ" / "ref" / "rss"
TAG = re.compile(r"<[^>]+>")
IMG = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
UA = {"User-Agent": "Mozilla/5.0 (eok-econ ref reader; RSS)", "Referer": "https://blog.naver.com/"}

SUMMARY = {"type": "object", "additionalProperties": False,
           "required": ["bloggers", "common", "hot_topics", "main_profile"],
           "properties": {
               "main_profile": {"type": "string", "description": (
                   "최우선 블로거의 썸네일·이미지 방식을 우리가 따라 할 수 있게 규칙으로 (5~8줄): 무엇을 주인공으로 고르나"
                   "(인물·건물·제품·차트·현장), 실사/AI/캡처, 구도·클로즈업, 글자 유무·위치, 색감, 주제와 그림을 잇는 방식")},
               "bloggers": {"type": "array", "items": {
                   "type": "object", "additionalProperties": False,
                   "required": ["id", "recent_topics", "title_style", "thumbnail_style", "structure"],
                   "properties": {
                       "id": {"type": "string"},
                       "recent_topics": {"type": "string", "description": "어제·오늘 쓴 주제 (없으면 '어제·오늘 글 없음')"},
                       "title_style": {"type": "string", "description": "제목 쓰는 방식 (길이·숫자·물음·괄호·말투, 예시는 짧게 바꿔 말하기)"},
                       "thumbnail_style": {"type": "string", "description": "썸네일 구성: 사진/그림/캡처, 글자 유무·위치·색·크기, 인물·차트 등"},
                       "structure": {"type": "string", "description": "RSS로 보이는 글 구성(요약 길이·그림 수 등). 표·글꼴·정렬·인용·구분선은 RSS로 알 수 없다고 적기"}}}},
               "common": {"type": "string", "description": "8명에게 공통으로 보이는 패턴과 우리 글에 쓸 만한 점 3~5개"},
               "hot_topics": {"type": "array", "description": "어제·오늘 여러 명이 겹쳐 쓴 주제 (우리 키워드 후보)",
                              "items": {"type": "object", "additionalProperties": False, "required": ["kw", "why"],
                                        "properties": {"kw": {"type": "string"}, "why": {"type": "string"}}}}}}


def feed(blog_id: str) -> list[dict]:
    r = requests.get(f"https://rss.blog.naver.com/{blog_id}.xml", headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(F.KST)
        except (TypeError, ValueError):
            continue
        desc = it.findtext("description") or ""
        out.append({"title": (it.findtext("title") or "").strip(), "at": at,
                    "category": (it.findtext("category") or "").strip(),
                    "tags": [t.strip() for t in (it.findtext("tag") or "").split(",") if t.strip()][:8],
                    "text_len": len(TAG.sub("", desc).strip()), "imgs": IMG.findall(desc),
                    "summary": re.sub(r"\s+", " ", TAG.sub(" ", desc)).strip()[:220],  # RSS 요약 앞부분 (사실만 뽑는 용도, 2026-10-06)
                    "html_tags": sorted({t.lower() for t in re.findall(r"<([a-zA-Z0-9]+)", desc)})})
    return out


def _image(url: str) -> dict | None:
    try:
        g = requests.get(url, headers=UA, timeout=20)
        ct = g.headers.get("content-type", "")
        if g.ok and ct.startswith("image/") and len(g.content) < 4_000_000 and ct.split(";")[0] in (
                "image/jpeg", "image/png", "image/gif", "image/webp"):
            return {"type": "image", "source": {"type": "base64", "media_type": ct.split(";")[0],
                                                "data": base64.b64encode(g.content).decode()}}
    except requests.RequestException:
        pass
    return None


FRAME = ROOT / "econ" / "ref" / "참고-블로거-틀.md"


def names() -> dict[str, str]:
    b = F.load(CFG, {}).get("bloggers", {})
    return b if isinstance(b, dict) else {x: x for x in b}


def titles() -> Path:
    """매일: 어제·오늘 새 글 제목만 (AI 없음)."""
    cfg, nm = F.load(CFG, {}), names()
    main = cfg.get("main", "")
    since = (datetime.now(F.KST) - timedelta(days=1)).strftime("%Y-%m-%d")
    out, missing, md = [], [], [f"# 참고 블로거 새 글 ({F.today()}, 어제·오늘, 공개 RSS)", ""]
    for bid in sorted(nm, key=lambda b: b != main):
        try:
            recent = [i for i in feed(bid) if i["at"].strftime("%Y-%m-%d") >= since]
        except Exception as e:  # noqa: BLE001
            missing.append(nm[bid])
            print(f"{bid} RSS 실패: {type(e).__name__}")
            continue
        out.append({"id": bid, "name": nm[bid], "recent": [i["title"] for i in recent]})
        md += [f"## {'⭐ ' if bid == main else ''}{nm[bid]}", ""] + (
            [f"- {i['at']:%m-%d %H:%M} {i['title']}" for i in recent] or ["- 새 글 없음"]) + [""]
    if missing:
        md.append(f"⚠️ RSS를 못 읽음: {', '.join(missing)}")
    OUT.mkdir(parents=True, exist_ok=True)
    F.save(OUT / f"{F.today()}.yaml", {"main": main, "bloggers": out})
    (OUT / f"{F.today()}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"참고 블로거 새 글 {sum(len(b['recent']) for b in out)}편 (못 읽음 {len(missing)})")
    return OUT / f"{F.today()}.md"


def collect() -> Path:
    """틀 분석 (한 번): 주제·제목·썸네일·보이는 글 구성 + 최우선 블로거 썸네일 방식."""
    cfg = F.load(CFG, {})
    ids = list(names())
    since = (datetime.now(F.KST) - timedelta(days=1)).strftime("%Y-%m-%d")  # 어제 0시부터
    main = cfg.get("main", "")
    rows, content, missing = [], [], []
    for bid in sorted(ids, key=lambda b: b != main):  # 최우선 블로거 먼저
        try:
            items = feed(bid)
        except Exception as e:  # noqa: BLE001
            missing.append(f"{bid}({type(e).__name__})")
            continue
        recent = [i for i in items if i["at"].strftime("%Y-%m-%d") >= since]
        rows.append({"id": bid, "recent": recent, "last10": items[:10]})
        lines = [f"## {bid} (최근 글 {len(items)}개 중 어제·오늘 {len(recent)}개)"]
        for i in items[:10]:
            mark = "★어제·오늘" if i in recent else ""
            lines.append(f"- {mark} {i['at']:%m-%d %H:%M} [{i['category']}] {i['title']} · 요약 {i['text_len']}자 · "
                         f"그림 {len(i['imgs'])} · 태그 {', '.join(i['tags'][:5])} · html {','.join(i['html_tags'])}")
        content.append({"type": "text", "text": "\n".join(lines)})
        for i in (items[:8] if bid == main else recent[:2]):  # 썸네일만 (최우선 블로거는 최근 8편)
            if i["imgs"]:
                img = _image(i["imgs"][0])
                if img:
                    content += [{"type": "text", "text": f"↓ {bid}의 '{i['title']}' 썸네일"}, img]
    if not rows:
        raise SystemExit(f"RSS를 하나도 못 읽었어요: {', '.join(missing)}")
    import anthropic
    c = anthropic.Anthropic()
    content.append({"type": "text", "text": (
        f"오늘은 {F.today()}(한국 시간). 위는 경제 블로거 {len(rows)}명의 공개 RSS 최근 글과 어제·오늘 글 썸네일입니다. "
        "우리 경제 블로그(억선생의 경제판)가 참고할 수 있게 블로거마다 ① 어제·오늘 주제 ② 제목 쓰는 방식 ③ 썸네일 구성 "
        "④ 보이는 글 구성을 정리하고, 공통 패턴과 여러 명이 겹쳐 쓴 주제를 뽑아 주세요. 보이는 것만 쓰고 추측하지 마세요. "
        f"특히 {main}은 대표가 강의를 듣는 최우선 블로거입니다. 그의 썸네일 최근 8장을 보고 우리가 화풍만 바꿔 따라 할 수 있게 "
        "썸네일·이미지 방식을 규칙으로 정리해 주세요(main_profile). "
        "남의 제목 문장은 길게 옮기지 말고 모양만 설명하세요.")})
    with c.messages.stream(model="claude-sonnet-5-5", max_tokens=16000, messages=[{"role": "user", "content": content}],
                           output_config={"format": {"type": "json_schema", "schema": SUMMARY}}) as st:
        msg = st.get_final_message()
    u = msg.usage
    F.SPENT["claude"] += (u.input_tokens * 2.0 + u.output_tokens * 10.0) / 1_000_000
    if msg.stop_reason != "end_turn":
        F.log_cost("refs", "실패")
        raise SystemExit(f"정리가 끝까지 안 됨 (stop_reason={msg.stop_reason}, 출력 {u.output_tokens}토큰)")
    res = json.loads("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))
    OUT.mkdir(parents=True, exist_ok=True)
    out = FRAME
    md = [f"# 참고 블로거 틀 ({F.today()} 분석, 공개 RSS)", "",
          "표·글꼴·정렬·인용·구분선은 RSS에 없어서 Aside 조사(📄 붙여넣기)로 채워요.", "",
          f"## ⭐ {main} 썸네일·이미지 방식 (최우선)", "", res["main_profile"], "",
          "## 공통 패턴", "", res["common"], "", "## 여러 명이 겹쳐 쓴 주제", ""]
    md += [f"- **{t['kw']}** — {t['why']}" for t in res["hot_topics"]] or ["- 없음"]
    for b in res["bloggers"]:
        md += ["", f"## {b['id']}", "", f"- 어제·오늘: {b['recent_topics']}", f"- 제목: {b['title_style']}",
               f"- 썸네일: {b['thumbnail_style']}", f"- 글 구성: {b['structure']}"]
    if missing:
        md += ["", f"⚠️ RSS를 못 읽은 블로거: {', '.join(missing)}"]
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    F.save(FRAME.with_suffix(".yaml"), {"at": F.today(), "main": main, "main_profile": res["main_profile"]})
    F.log_cost("refs", f"{len(rows)}명")
    print(f"참고 블로거 {len(rows)}명 정리 → {out} (못 읽음 {len(missing)})")
    return out


if __name__ == "__main__":
    import sys
    if "--analyze" in sys.argv:
        F.guard()
        collect()
    else:
        titles()
