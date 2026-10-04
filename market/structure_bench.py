"""경제 블로그 글 구조 분석 (2026-10-04, 대표 지시): 인플루언서·상위 블로그의 '글 쓰는 틀'을 숫자로 뽑아 우리 양식의 재료로 쓴다.

통로: 공개 RSS(rss.blog.naver.com/<아이디>.xml). 본문 페이지는 열지 않는다.
RSS 요약문에 본문이 얼마나 들어 있는지부터 재고(요약문 길이), 그 안에서 구조를 잰다.
남의 제목·문장은 옮기지 않고 숫자·비율만 남긴다. 결과: reports/블로그-벤치마크/경제-글구조-<날짜>.md
"""
from __future__ import annotations

import html
import re
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

from content.voice import style_metrics
from .blog_bench import KST
from .common import ROOT, load_yaml

TAG = re.compile(r"<[^>]+>")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌✔✖]")
BULLET = re.compile(r"^\s*(\d+[.)]|[-•▶▷✔✅◆◇■□●○※★☆➡→]|[①-⑩])")
CTA = re.compile(r"댓글|공감|이웃|구독|좋아요|추가해|알림")
SUMMARY = re.compile(r"요약|결론|한\s?줄|정리하면|핵심|3줄|세 줄")
AD = re.compile(r"소정의|원고료|제휴|수수료|협찬|광고|파트너스|쇼핑커넥트|지원받")
SOURCE = re.compile(r"출처|자료|참고|기준일|기준:")


def lines_of(raw: str) -> list[str]:
    text = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>", "\n", raw, flags=re.I)
    text = html.unescape(TAG.sub(" ", text))
    return [re.sub(r"\s+", " ", x).strip() for x in text.split("\n") if x.strip()]


def fetch(bid: str) -> list[dict]:
    try:
        r = requests.get(f"https://rss.blog.naver.com/{bid}.xml", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; eoksori-bench/1.0)"})
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        raw = it.findtext("description") or ""
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(KST)
        except (TypeError, ValueError):
            at = None
        out.append({"title": (it.findtext("title") or "").strip(), "raw": raw, "at": at})
    return out


def post_metrics(p: dict) -> dict:
    ls = lines_of(p["raw"])
    text = " ".join(ls)
    first = ls[0] if ls else ""
    last = " ".join(ls[-3:]) if ls else ""
    short = [x for x in ls if len(x) <= 25 and not x.endswith(("다.", "요.", "죠.", "다", "요"))]
    return {
        "chars": len(text), "lines": len(ls), "imgs": len(re.findall(r"<img", p["raw"], re.I)),
        "line_len": statistics.mean(len(x) for x in ls) if ls else 0,
        "short_heads": len(short), "q_lines": sum(x.endswith("?") for x in ls),
        "bullets": sum(bool(BULLET.match(x)) for x in ls), "emoji": len(EMOJI.findall(text)),
        "first_q": first.endswith("?") or "?" in first[:60], "first_num": bool(re.search(r"\d", first)),
        "first_len": len(first), "cta": bool(CTA.search(last)), "summary": bool(SUMMARY.search(text)),
        "ad": bool(AD.search(text)), "source": bool(SOURCE.search(text)),
        "title_q": "?" in p["title"], "title_len": len(p["title"]), "text": text,
    }


def pct(xs) -> int:
    xs = list(xs)
    return round(100 * sum(1 for x in xs if x) / len(xs)) if xs else 0


def med(xs) -> float:
    xs = list(xs)
    return round(statistics.median(xs), 1) if xs else 0


def main() -> None:
    cfg = load_yaml("structure_bench.yaml")
    kst = datetime.now(KST)
    rows = []
    for t in cfg["targets"]:
        posts = fetch(t["id"])
        ms = [post_metrics(p) for p in posts]
        if not ms:
            rows.append({**t, "n": 0})
            continue
        voice = style_metrics([m["text"] for m in ms if m["text"]])
        rows.append({**t, "n": len(ms), "chars": med(m["chars"] for m in ms), "maxchars": max(m["chars"] for m in ms),
                     "lines": med(m["lines"] for m in ms), "imgs": med(m["imgs"] for m in ms),
                     "line_len": med(m["line_len"] for m in ms), "heads": med(m["short_heads"] for m in ms),
                     "q_lines": med(m["q_lines"] for m in ms), "bullets": med(m["bullets"] for m in ms),
                     "emoji": med(m["emoji"] for m in ms), "first_q": pct(m["first_q"] for m in ms),
                     "first_num": pct(m["first_num"] for m in ms), "first_len": med(m["first_len"] for m in ms),
                     "cta": pct(m["cta"] for m in ms), "summary": pct(m["summary"] for m in ms),
                     "ad": pct(m["ad"] for m in ms), "source": pct(m["source"] for m in ms),
                     "title_q": pct(m["title_q"] for m in ms), "title_len": med(m["title_len"] for m in ms),
                     "voice": voice})
    ok = [r for r in rows if r["n"]]
    L = [f"# 경제 블로그 글 구조 분석 ({kst:%Y-%m-%d})", "",
         "공개 RSS의 최근 글(블로그당 약 50개)로 잰 숫자예요. 남의 제목·문장은 옮기지 않았어요.",
         "⚠️ RSS 요약문은 본문 일부만 담길 수 있어요 → 아래 '요약문 길이'가 짧으면 구조 숫자도 앞부분 기준이에요.", "",
         "## 1. RSS에 본문이 얼마나 담기나", "", "| 블로그 | 분류 | 글 수 | 요약문 길이(중간값) | 가장 긴 것 | 줄 수 | 이미지 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if not r["n"]:
            L.append(f"| {r['name']} | {r['group']} | RSS 못 받음 | - | - | - | - |")
            continue
        L.append(f"| {r['name']} | {r['group']} | {r['n']} | {r['chars']}자 | {r['maxchars']}자 | {r['lines']} | {r['imgs']} |")
    L += ["", "## 2. 글 모양", "",
          "| 블로그 | 한 줄 길이 | 짧은 소제목줄 | 질문줄 | 목록줄 | 이모지 | 첫줄 질문% | 첫줄 숫자% | 첫줄 길이 | 끝에 댓글·이웃 유도% | 요약·결론% | 출처·기준% | 광고·제휴 표기% |",
          "| --- " * 14 + "|"]
    for r in ok:
        L.append(f"| {r['name']} | {r['line_len']} | {r['heads']} | {r['q_lines']} | {r['bullets']} | {r['emoji']} | {r['first_q']} | {r['first_num']} | {r['first_len']} | {r['cta']} | {r['summary']} | {r['source']} | {r['ad']} |")
    L += ["", "## 3. 제목과 말투", "", "| 블로그 | 제목 물음표% | 제목 길이 | " + " | ".join(ok[0]["voice"].keys() if ok else []) + " |",
          "| --- " * (3 + (len(ok[0]["voice"]) if ok else 0)) + "|"]
    for r in ok:
        v = " | ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in r["voice"].values())
        L.append(f"| {r['name']} | {r['title_q']} | {r['title_len']} | {v} |")
    out = ROOT / "reports" / "블로그-벤치마크" / f"경제-글구조-{kst:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
