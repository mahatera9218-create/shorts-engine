"""경제 블로그 발행 도우미 (2026-10-05, 대표 지시: 스포츠처럼 홈 화면에 깔아 두고 쓰게. 같은 날 담백한 디자인으로 바꿈).

- econ/posts/<날짜-주제>/ 의 발행 패키지(post.md · body.txt · 사진 · short.mp4 · short.txt)를 휴대폰용 정적 사이트로 만든다.
- 글마다: 사진 한 번에 저장 → 제목 → 썸네일 → 본문 복사 → 태그 → 쇼츠·클립(영상 저장 + 설명·해시태그) → 발행 완료.
- 글 형식은 스포츠 도우미와 같다(content/desk.parse 재사용). 디자인은 심플하게: Claude 색(크림 바탕·테라코타 포인트)에 어두운 글자, 이모지 없음(대표 지시 2026-10-05). 억선생 자료는 클립용으로 따로 보관.
- 발행 완료: 이슈 "[경제발행완료] <글>" → .github/workflows/desk-button.yml → 이 파일 --mark → econ/posts/<글>/status.yaml
- 검색엔진 수집 금지(noindex·robots·X-Robots-Tag). Cloudflare Pages (.github/workflows/econ-desk.yml)

사용법: python -m content.econ_desk [출력 폴더, 기본 site-econ]
        python -m content.econ_desk --mark "[경제발행완료] 2026-10-05-금값-출렁"
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import urllib.parse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from market.common import ROOT
from . import desk

POSTS = ROOT / "econ" / "posts"
BRAND = ROOT / "assets" / "brand"
NAME = "경제 블로그"  # 블로그 이름은 대표가 정함 (2026-10-05)
KST = ZoneInfo("Asia/Seoul")
MARK = re.compile(r"^\[(경제|연예|패션)발행완료\]\s*(\d{4}-\d{2}-\d{2}-[\w가-힣-]+)\s*$")
from .econ_flow import MONTH_CAP_KRW as F_CAP  # 월 상한 (econ_flow와 같게)
BID, LABEL = "econ", "경제"  # 지금 그리는 블로그 (use()로 바꿈, 2026-10-05 경제·연예·패션 3개)


def use(b: dict) -> None:
    """도우미를 그릴 블로그를 바꾼다: 데이터 폴더·버튼 이름(라벨)."""
    global POSTS, FLOW, BID, LABEL
    POSTS, FLOW, BID, LABEL = b["base"] / "posts", b["base"] / "flow", b["id"], b["label"]

CSS = desk.CSS + """
:root{--bg:#f5f4ee;--card:#ffffff;--ink:#141413;--soft:#5e5d59;--line:#e5e3da;--accent:#c96442;--btn:#c96442;--btnink:#ffffff;--gold:#c96442;--pine:#5e7d4f;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#f5f4ee;--card:#ffffff;--ink:#141413;--soft:#5e5d59;--line:#e5e3da;--accent:#c96442;--btn:#c96442;--btnink:#ffffff}}  /* 늘 밝은 바탕·어두운 글자 (대표 지시) */
header.brand{display:flex;align-items:center;gap:12px;margin:6px 0 4px}
header.brand img{width:48px;height:48px;border-radius:12px}
header.brand h1{margin:0;font-size:21px}header.brand .muted{margin:0}
.step{background:var(--accent)}h2{border-left:5px solid var(--accent);padding-left:8px}
nav.tabs{display:flex;gap:4px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}
nav.tabs a{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;padding:11px 0;font-size:13px;letter-spacing:-.3px;border-radius:12px;border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:700}
nav.tabs a.on{background:var(--accent);color:#fff;border-color:var(--accent)}
/* 태블릿 (대표 주 작업 기기, 2026-10-05): 넓은 화면은 두 칸 — 왼쪽 할 일, 오른쪽 결과 */
@media (min-width:900px){main{max-width:1240px}.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}
.cols>div>.card:first-child,.cols>div>h2:first-child{margin-top:0}.stick{position:sticky;top:64px;max-height:calc(100vh - 80px);overflow:auto}nav.tabs{max-width:640px}}
details.fold{padding-top:10px}details.fold>summary{list-style:none;cursor:pointer}details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary h2{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
details.fold>summary h2::after{content:"접기 ▴";font-size:13px;color:var(--soft);font-weight:600}
details.fold:not([open])>summary h2::after{content:"펼치기 ▾"}
.seal{display:inline-block;background:var(--accent);color:#fff;border-radius:6px;padding:0 6px;font-weight:800}
"""


def head(title: str, depth: str = "") -> str:
    e = html.escape
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<meta name="theme-color" content="#c96442"><link rel="manifest" href="{depth}manifest.webmanifest">
<link rel="apple-touch-icon" href="{depth}icon-180.png"><meta name="apple-mobile-web-app-title" content="발행 도우미">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>{e(title)}</title><style>{CSS}</style></head><body><main>"""


def read_short(folder: Path) -> dict | None:
    """short.mp4 + short.txt(첫 줄 제목, 나머지 설명·해시태그)."""
    v, t = folder / "short.mp4", folder / "short.txt"
    if not v.exists():
        return None
    title, _, desc = (t.read_text(encoding="utf-8") if t.exists() else "").partition("\n")
    return {"title": title.strip(), "desc": desc.strip()}


def video_card(p: dict, src: str) -> str:
    e, s = html.escape, p["short"]
    return f"""<div class="card"><h2>🎬 쇼츠 · 클립 (같은 영상)</h2>
<video src="{e(src)}" controls playsinline preload="none" style="width:100%;max-width:320px;border-radius:10px;display:block;margin-top:8px"></video>
<button onclick="saveClip(this,{e(json.dumps(src), quote=True)})">🎬 영상 저장</button>
{desk.edit_box("st:" + p["folder"], s["title"], "제목 복사", one_line=True)}
{desk.copy_pair(s["desc"], "영상", p["folder"])}
<ol class="muted"><li><b>유튜브 쇼츠</b>: 유튜브 앱 + → 동영상 업로드 → 저장한 영상 → 제목·설명 붙여넣기 → 공개</li>
<li><b>네이버 클립</b>: 블로그 앱 + → 클립 만들기 → 같은 영상 → 설명·해시태그 붙여넣기 → 올리기</li></ol>
<div class="muted">영상에 'AI 그림·AI 음성' 표시가 들어 있고, 설명에도 적혀 있어요.</div></div>"""


ALL_HEAD = {  # 한 번에 붙여넣을 그림 요청 머리말 (원문 사진 기준, 대표 지시 2026-10-06 "한 번에 요청할 프롬프트")
    "econ": ("아래 {n}장의 블로그 사진을 만들어 주세요. 모든 사진은 정사각형 800×800. 반드시 번호 순서대로 한 장씩 따로따로 만들어 주세요(여러 장면을 한 장에 합치지 말 것, "
             "중간에 멈추면 이어서 계속). 공통: 실제 뉴스 현장 사진처럼 사실적인 사진, 자연광, 또렷한 초점. "
             "회사가 나오면 그 회사의 실제 건물과 진짜 로고·회사 이름 간판이 정확히 보이게. 그 밖의 글자·숫자·워터마크·차트는 넣지 말 것. "
             "실존 인물의 얼굴이 알아보이게 그리지 말 것(뒷모습·손·멀리 있는 사람은 괜찮음)."),
    "fashion": ("아래 {n}장의 패션 블로그 사진을 만들어 주세요. 모든 사진은 정사각형 800×800. 반드시 번호 순서대로 한 장씩 따로따로 만들어 주세요(여러 장면을 한 장에 합치지 말 것, "
                "중간에 멈추면 이어서 계속). 공통: 고급 패션 잡지 정물 사진, 부드러운 자연광, 크림색 리넨·따뜻한 돌 위, 조용한 럭셔리 분위기, "
                "원단·니트·가죽·금속 장식의 질감이 아주 선명하게, 실제 색감. 제품만(사람·손·얼굴 없음), 브랜드 로고·글자·워터마크 없음."),
}


def all_prompt(items: list[dict], title: str = "") -> str:
    """이 글 사진 전부를 한 번에 요청하는 프롬프트 하나 (대표 지시 2026-10-06: 구분 없이 '사진 프롬프트' 하나로)."""
    draw = [it for it in items if not it.get("person") and it.get("desc")]
    find = [it for it in items if it.get("person")]
    lines = [ALL_HEAD.get(BID, ALL_HEAD["econ"]).format(n=len(draw)), ""]
    for it in draw:
        shape = "800×800"  # 사진 크기 고정 (대표 결정 2026-10-08)
        brand = f" — {it['brand']} 실제 건물, 진짜 로고·간판" if it.get("brand") else ""
        hook = ((f" — 이 글의 대표사진. 글 제목 「{title}」을 보자마자 떠오르는 한 장면으로" if title else " — 이 글의 대표사진")
                + ", 홈피드에서 손이 멈추게 대상을 화면 가득·강한 명암·높은 채도. 다른 번호 사진과 겹치지 않게"
                if it["n"] == 1 and BID == "econ" else "")  # 경제 썸네일 = 제목 한 장 요약 (대표 지적 2026-10-07 "대표사진이 애매")
        lines.append(f"{it['n']}번 ({shape}, {it['label']}{brand}{hook}): {it['desc']}")
    if find:  # 실제 인물 사진은 그리지 않는다 — 발행 도우미의 '인물 사진 자리'에서 원본을 바로 받는다 (2026-10-06)
        lines += ["", "※ " + ", ".join(f"{it['n']}번" for it in find) + "은 실제 인물 사진을 따로 넣을 자리라 만들지 않습니다."]
    return "\n".join(lines)


def outfit_links(folder: str) -> str:
    """착장 글이면 대표가 붙인 인스타 게시물 주소 (사진은 여기서 대표가 직접, 2026-10-10)."""
    e = html.escape
    f = FLOW / folder[:10] / folder / "outfit.yaml"
    if not f.exists():
        return ""
    o = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    links = "".join(f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" '
                    f'href="{e(u, quote=True)}" target="_blank" rel="noopener">📷 {e(o.get("person", ""))} 게시물 {i}</a>'
                    for i, u in enumerate(o.get("insta", []), 1))
    shops = "".join(f'<a href="{e(u, quote=True)}" target="_blank" rel="noopener" style="display:block;font-size:13px;padding:3px 0;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">🛍 {e(u)}</a>' for u in o.get("shops", []))
    return f'<div class="card"><h2>착장 원본</h2>{links}{shops}</div>' if (links or shops) else ""


def prompts_card(p: dict) -> str:
    """사진: 프롬프트만 (대표 결정 2026-10-09: 실제 사진 후보는 글과 안 맞는 게 많아 안 보여 줌). 경제 = 그릴 사진 프롬프트,
    패션 = 찾을 실제 사진 목록(번호·검색어·설명)."""
    e = html.escape
    f = POSTS / p["folder"] / "prompts.json"
    if not f.exists():
        return ""
    items = json.loads(f.read_text(encoding="utf-8"))
    best = next((t["text"] for t in p.get("titles", []) if t.get("best")), "")
    draw = [it for it in items if not it.get("person") and it.get("desc")]
    find = [it for it in items if it.get("person")]
    parts = []
    if draw:
        parts.append(all_prompt(items, best))  # 대표사진이 제목을 담도록 제목을 같이 (2026-10-07)
    if find:
        parts.append("\n".join(f"{it['n']}번 · {it['label']}" + (f" — 검색어: {it['find']}" if it.get("find") else "") for it in find))
    px = POSTS / p["folder"] / "pixabay.txt"
    if px.exists():  # 경제 원문 '픽사베이 추천 검색어 5개' (2026-10-10)
        parts.append("픽사베이 검색어: " + ", ".join(l for l in px.read_text(encoding="utf-8").splitlines() if l.strip()))
    text = "\n\n".join(parts)
    if not text:
        return ""
    return (f'<div class="card"><h2>사진</h2>'
            f'<button onclick="copyText(this,{e(json.dumps(text), quote=True)})">📋 사진 프롬프트 복사</button>'
            f'<details><summary class="muted">프롬프트 보기</summary><div style="font-size:13px;white-space:pre-wrap;word-break:break-word;'
            f'background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-top:8px">{e(text)}</div></details>'
            f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="../../photo/">📐 사진 800×800 맞추기</a></div>')


def topic_titles(folder: str) -> dict:
    """글 폴더의 제목 후보 전체 (flow/<날짜>/<폴더>/titles.yaml)."""
    f = FLOW / folder[:10] / folder / "titles.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def title_groups(T: dict) -> list[tuple[str, list[tuple[int, dict]]]]:
    """프롬프트 기준 제목 묶음 [(묶음 이름, [(번호, 제목)])]. 제목 고수 방식(…식) 묶음은 빼고 (대표 결정 2026-10-09: 프롬프트 기준).
    경제 = 최종 BEST 5 + 6유형 × 5, 패션 = 최종 추천 1 + 그룹 1·2·3 × 5."""
    items = T.get("items", [])
    out = [("최종 추천", [(i, it) for i, it in enumerate(items, 1) if it.get("rank")])]
    for g in T.get("groups", []):
        if g["type"].endswith("식"):
            continue
        out.append((g["type"], [(j + 1, items[j]) for j in g["idx"] if j < len(items)]))
    return [(n, xs) for n, xs in out if xs]


def blog_links(kw: str, n: int = 3) -> str:
    """같은 키워드 네이버 블로그 글 3개 (공식 블로그 검색 API, 대표 요청 2026-10-09: 사진 후보 대신)."""
    e = html.escape
    from .econ_flow import top10
    try:
        rows = [r for r in top10(kw) if r.get("link")][:n] if kw else []
    except Exception:  # noqa: BLE001  (도우미는 링크 없이도 그린다)
        rows = []
    if not rows:
        return ""
    return ('<div style="margin-top:8px"><b style="font-size:13px">같은 키워드 블로그</b>'
            + "".join(f'<a href="{e(r["link"], quote=True)}" target="_blank" rel="noopener" style="display:block;font-size:13px;'
                      f'padding:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{e(r["title"])}</a>' for r in rows)
            + '</div>')


def page(p: dict) -> str:
    """글 화면: 제목 → 사진 → 본문 (대표 지시 2026-10-08: 설명 글·미리보기·발행 완료·태그 칸·사진 저장·출처 없앰).
    본문 복사 = 소제목 앞뒤 빈 줄 2칸(■ 없이) + 사진 자리 + 맨 끝 해시태그."""
    e = html.escape
    best = next((t for t in p["titles"] if t["best"]), p["titles"][0] if p["titles"] else {"text": p["folder"], "type": ""})
    probs = "".join(f"<li>{e(x)}</li>" for x in p["problems"])
    T = topic_titles(p["folder"])
    pick_btn = lambda t, typ: (f'<button class="ghost" onclick="setEd(\'title\',{e(json.dumps(t), quote=True)})">{e(t)}'  # noqa: E731
                               f'{badge(t, typ)}</button>')
    if T:  # 프롬프트대로 만든 제목 전부 (대표 지시 2026-10-09 "다른 제목이 너무 적다")
        groups = title_groups(T)
        n_all = sum(len(xs) for _, xs in groups)
        rest = "".join(f'<div class="muted" style="margin:8px 0 2px;font-size:13px">{e(name)}</div>'
                       + "".join(pick_btn(it["title"], it.get("type", "")) for _, it in xs) for name, xs in groups)
    else:
        n_all = len(p["titles"])
        rest = "".join(pick_btn(t["text"], t["type"]) for t in p["titles"] if t is not best)
    body = "".join(
        f'<textarea class="ed" data-k="b{i}" rows="3">{e(b["text"])}</textarea>' if "text" in b else
        f'<div class="muted" style="padding:6px 0">📷 사진 {b["n"]} · {e(b["label"])}</div>'
        for i, b in enumerate(p["blocks"]) if "text" in b or "img" in b)
    data = json.dumps({"blocks": p["blocks"], "images": [], "tags": p["tags"], "folder": p["folder"], "repo": desk.REPO,
                       "editTag": f"[{LABEL}수정]"}, ensure_ascii=False).replace("</", "<\\/")
    return head(best["text"], "../../") + f"""
<a href="../../" class="muted">← 목록</a>
<h1>{e(best["text"])}</h1>
{f'<div class="card" style="border:2px solid var(--warn)"><b>⚠️ 확인 필요</b><ul>{probs}</ul></div>' if not p["ok"] else ""}
<div class="card"><h2>제목{badge(best["text"], best.get("type", ""))}</h2>{desk.edit_box("title", best["text"], "제목 복사", one_line=True)}
{f'<details><summary class="muted">다른 제목 {n_all}개</summary>{rest}</details>' if rest else ''}{rules_html()}{blog_links(T.get("keyword", "")) if BID != "econ" and T else ""}</div>
{outfit_links(p["folder"])}{prompts_card(p)}
<div class="card"><h2>본문</h2>
<button onclick="copyBody(this)">📋 본문 복사</button>
<details><summary class="muted">본문 보기·고치기</summary>{body}</details></div>
</main><script>const POST={data};{desk.JS}</script></body></html>"""


def badge(title: str, typ: str = "") -> str:
    """👍 반응굿 단추 — 반응 좋은 제목 유형이면 (content/good_rules.py, 대표 지시 2026-10-08)."""
    from .good_rules import good
    g = good(title, BID, typ)
    return (f' <span style="display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:999px;'
            f'background:#e7f6ec;color:#17733a;white-space:nowrap">👍 반응굿 · {html.escape(" · ".join(g[:2]))}</span>' if g else "")


def rules_html() -> str:
    """👍 잘 된 제목 규칙 (어사이드 블로거 조사의 '반응 좋은 글에만 있는 것', 대표 지시 2026-10-08) — 제목 칸 안에 접어서."""
    from .good_rules import rules
    e, r = html.escape, rules(BID)
    li = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs)
    if not r.get("title"):  # 제목 규칙만 (글 작성은 쿠니네식으로만, 대표 원칙 2026-10-08)
        return ""
    return (f'<details style="margin-top:8px"><summary class="muted">👍 잘 된 제목 규칙</summary>'
            + f'<ul style="margin:4px 0;padding-left:18px">{li(r["title"])}</ul>'
            + '</details>')


def blog_section(b: dict, posts: list[dict]) -> str:
    """블로그 탭: 오늘 글 → 키워드 → 제목 (대표 지시 2026-10-08: 오늘 날짜 글만, 발행한 글 목록 없음)."""
    e = html.escape
    use(b)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    live = sorted((p for p in posts if p["date"] == today), key=lambda p: p["folder"], reverse=True)
    bid = b["id"]
    rows = "".join(
        f'<div class="today-{bid}" data-f="{e(p["folder"], quote=True)}" style="display:flex;gap:6px;align-items:stretch">'
        f'<a class="btn" style="flex:1;margin:4px 0;text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
        f'href="p/{bid}-{desk.slug(p["folder"])}/">{"" if p["ok"] else "⚠️ "}'
        f'{e(next((x["text"] for x in p["titles"] if x["best"]), p["folder"]))}</a>'
        f'<button class="ghost" style="width:44px;margin:4px 0;padding:0" onclick="hideToday(\'{bid}\',this)">✕</button></div>' for p in live)
    # 오늘 글 숨기기 (대표 요청 2026-10-09) — 이 휴대폰에만 기억 (localStorage), '숨긴 글 보기'로 다시
    js = ("function hideKey(b){return 'hide-'+b}"
          "function hidden_(b){try{return JSON.parse(localStorage.getItem(hideKey(b))||'[]')}catch(e){return []}}"
          "function hideToday(b,el){const f=el.parentNode.dataset.f;const h=hidden_(b);if(!h.includes(f))h.push(f);"
          "try{localStorage.setItem(hideKey(b),JSON.stringify(h))}catch(e){}applyHide(b)}"
          "function applyHide(b,show){const h=hidden_(b);let n=0;document.querySelectorAll('.today-'+b).forEach(d=>{"
          "const x=h.includes(d.dataset.f);if(x)n++;d.style.display=(x&&!show)?'none':'flex'});"
          "const s=document.getElementById('hid-'+b);if(s){s.style.display=n?'block':'none';s.textContent=show?'숨긴 글 다시 숨기기':'숨긴 글 '+n+'개 보기';"
          "s.onclick=()=>applyHide(b,!show)}}"
          "function showAllHidden(b){try{localStorage.removeItem(hideKey(b))}catch(e){}applyHide(b)}")
    return (f'<section class="tab" id="{bid}" hidden><div class="cols"><div>'
            f'<div class="card"><h2>오늘 글</h2>{rows or "<p class=muted>없음</p>"}'
            f'<a id="hid-{bid}" class="muted" style="display:none;margin-top:6px;font-size:13px;cursor:pointer"></a></div>'
            f'<script>{js}applyHide("{bid}")</script>'
            f'</div><div>{flow_html()}</div></div></section>')


def outfit_page(fb: dict, posts: list[dict]) -> str:
    """👗 착장 도우미 (대표 결정 2026-10-10): 오늘 뜨는 연예인 → 대표가 고르고 인스타 게시물 주소·상품 링크 붙이기 → 글.
    인스타는 대표가 직접 열어 주소만 복사한다(자동 수집 안 함). 사진은 대표가 넣는다."""
    e = html.escape
    today = datetime.now(KST).strftime("%Y-%m-%d")
    base = fb["base"]
    cel = (yaml.safe_load((base / "outfit" / today / "celebs.yaml").read_text(encoding="utf-8")) or {}) \
        if (base / "outfit" / today / "celebs.yaml").exists() else {}
    handles = {}
    hf = ROOT / "config" / "celeb_instagram.yaml"
    if hf.exists():
        handles = yaml.safe_load(hf.read_text(encoding="utf-8")) or {}
    issue = f"https://github.com/{desk.REPO}/issues/new?title="
    rows = []
    for c in cel.get("items", []):
        h = handles.get(c["name"])
        insta = f"https://www.instagram.com/{h}/" if h else \
            "https://www.google.com/search?q=" + urllib.parse.quote(f'{c["name"]} 인스타그램')
        rows.append(
            f'<div style="display:flex;gap:6px;align-items:stretch;margin:4px 0">'
            f'<button class="ghost" style="flex:1;margin:0;text-align:left" onclick="pickC({e(json.dumps(c["name"]), quote=True)})">'
            f'<b>{e(c["name"])}</b> <span class="seal">{c.get("score", "")}</span>'
            f'<div class="muted" style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{e(c.get("why", ""))}</div></button>'
            f'<a class="btn" style="width:64px;margin:0;padding:8px 4px;font-size:13px;display:flex;align-items:center;justify-content:center;background:transparent;color:var(--ink);'
            f'border:1px solid var(--line)" href="{e(insta, quote=True)}" target="_blank" rel="noopener">인스타</a></div>')
    keys = list(dict.fromkeys(k for c in cel.get("items", []) for k in (c.get("parts") or {})))
    table = ""
    if keys:
        table = ('<details style="margin-top:6px"><summary class="muted">점수표</summary><div style="overflow-x:auto">'
                 '<table style="font-size:12px;border-collapse:collapse;width:100%;text-align:center"><tr><th style="text-align:left">이름</th><th>합계</th>'
                 + "".join(f"<th>{e(k)}</th>" for k in keys) + "<th>월 검색</th></tr>"
                 + "".join(f'<tr><td style="text-align:left">{e(c["name"])}</td><td><b>{c.get("score", "")}</b></td>'
                           + "".join(f'<td>{(c.get("parts") or {}).get(k, "")}</td>' for k in keys)
                           + f'<td>{c.get("volume") or ""}</td></tr>' for c in cel.get("items", []))
                 + "</table></div></details>")
    again = desk.issue_link("착장새로", today, "오늘 뜨는 연예인을 다시 뽑아 주세요.")
    done = []
    for p in sorted((p for p in posts if p["date"] == today), key=lambda p: p["folder"], reverse=True):
        of = base / "flow" / p["folder"][:10] / p["folder"] / "outfit.yaml"
        if not of.exists():
            continue
        o = yaml.safe_load(of.read_text(encoding="utf-8")) or {}
        best = next((x["text"] for x in p["titles"] if x["best"]), p["folder"])
        links = "".join(f'<a href="{e(u, quote=True)}" target="_blank" rel="noopener" class="muted" style="font-size:13px;margin-right:8px">'
                        f'📷 게시물 {i}</a>' for i, u in enumerate(o.get("insta", []), 1))
        done.append(f'<div style="padding:6px 0;border-bottom:1px solid var(--line)">'
                    f'<a href="../p/fashion-{desk.slug(p["folder"])}/"><b>{e(o.get("person", ""))}</b> · {e(best)}</a>'
                    f'<div>{links}</div></div>')
    js = ("function pickC(n){const t=document.getElementById('oin');t.value=n+'\\n';"
          "t.scrollIntoView({behavior:'smooth',block:'center'});t.focus()}"
          "function goOutfit(){const v=document.getElementById('oin').value.trim();if(!v)return;"
          f"location.href='{issue}'+encodeURIComponent('[착장글] {today}')+'&body='+encodeURIComponent(v)}}")
    return head("착장 도우미", "../") + f"""
<a href="../" class="muted">← 발행 도우미</a>
<h1>👗 착장 도우미</h1>
<div class="card"><h2>오늘 뜨는 연예인</h2>{"".join(rows) or '<p class="muted">없음</p>'}{table}
<a class="btn" style="margin-top:8px;background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(again, quote=True)}">🔄 다시 뽑기</a></div>
<div class="card"><h2>글 만들기</h2>
<textarea id="oin" rows="5" style="{TA}" placeholder="첫 줄: 연예인 이름 (위에서 누르면 들어와요)&#10;인스타 게시물 주소&#10;상품 링크 (렌즈 결과, 한 줄에 하나)"></textarea>
<button onclick="goOutfit()">✍️ 착장 글 만들기</button></div>
<div class="card"><h2>오늘 착장 글</h2>{"".join(done) or '<p class="muted">없음</p>'}</div>
</main><script>{js}</script></body></html>"""


def photo_page() -> str:
    """📐 사진 800×800 맞추기 (대표 지시 2026-10-08: 업로드만, 설정·설명 없음). 휴대폰 브라우저 안에서만 처리, 어디에도 안 올림.
    꽉 채우기(넘치는 부분 자름) — 세로 사진은 위쪽(얼굴)을 살림."""
    return head("사진 800×800", "../") + """
<a href="../" class="muted">← 목록</a>
<h1>사진 800×800</h1>
<input type="file" id="pick" accept="image/*" multiple style="width:100%;padding:12px 0">
<div id="out" style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px"></div>
<button id="saveAll" style="display:none;position:sticky;bottom:10px">📥 전부 저장</button>
<script>
const S=800;let done=[];
function img(f){return new Promise((ok,no)=>{const i=new Image();i.onload=()=>ok(i);i.onerror=no;i.src=URL.createObjectURL(f)})}
async function fit(f,n){const i=await img(f),c=document.createElement('canvas');c.width=S;c.height=S;const x=c.getContext('2d');
  x.fillStyle='#fff';x.fillRect(0,0,S,S);x.imageSmoothingQuality='high';const k=Math.max(S/i.width,S/i.height),w=i.width*k,h=i.height*k;
  x.drawImage(i,(S-w)/2,h>S?0:(S-h)/2,w,h);const b=await new Promise(r=>c.toBlob(r,'image/jpeg',.9));
  return new File([b],'photo-'+String(n).padStart(2,'0')+'.jpg',{type:'image/jpeg'})}
document.getElementById('pick').onchange=async e=>{const fs=[...e.target.files],out=document.getElementById('out');out.innerHTML='';done=[];
  for(let k=0;k<fs.length;k++){try{const f=await fit(fs[k],k+1);done.push(f);const im=document.createElement('img');im.src=URL.createObjectURL(f);
    im.style.cssText='width:100%;border-radius:8px';out.appendChild(im)}catch(err){}}
  document.getElementById('saveAll').style.display=done.length?'block':'none'};
document.getElementById('saveAll').onclick=async()=>{if(navigator.canShare&&navigator.canShare({files:done})){try{await navigator.share({files:done})}catch(e){}}};
</script></main></body></html>"""


def error_banner() -> str:
    """마지막 버튼 실행이 실패했으면 맨 위 빨간 띠 (content/run_error.py, 대표 지적 2026-10-10). 클로드 실행이 성공하면 사라짐."""
    f = ROOT / "status" / "desk_error.yaml"
    if not f.exists():
        return ""
    E = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    e = html.escape
    what = f' · {e(E["kw"])}' if E.get("kw") else ""
    return (f'<div class="card" style="border:2px solid #d33;background:#fdecec;color:#7a1010">'
            f'<b>❌ 마지막 실행 실패 ({e(E.get("at", ""))}{what})</b>'
            f'<div style="margin-top:4px">{e(E.get("reason", ""))}</div></div>')


def index(by_blog: dict[str, list[dict]]) -> str:
    from .blogs import all_blogs
    blogs = all_blogs()
    now = datetime.now(KST).strftime("%m월 %d일 %H:%M")
    tabs = "".join(f'<a href="#{bid}" data-t="{bid}">{html.escape(b["label"])}</a>' for bid, b in blogs.items())
    secs = "".join(blog_section(b, by_blog.get(bid, [])) for bid, b in blogs.items())
    first = next(iter(blogs))
    return head(f"{NAME} 발행 도우미") + f"""
<header class="brand"><img src="icon-180.png" alt=""><div><h1>발행 도우미</h1><p class="muted">{" · ".join(html.escape(b["label"]) for b in blogs.values())} · {now} 업데이트</p></div></header>
{error_banner()}<nav class="tabs">{tabs}<a href="outfit/">착장</a><a href="#stats" data-t="stats">성과</a><a href="#aside" data-t="aside">어사이드</a><a href="photo/">사진</a></nav>
{secs}
<section class="tab" id="aside" hidden>{aside_tab(blogs)}</section>
<section class="tab" id="stats" hidden>{compare_html(blogs, by_blog)}</section>
</main><script>const POST={{"blocks":[],"images":[]}};{desk.JS}
function tab(){{const h=(location.hash||'#{first}').slice(1);document.querySelectorAll('section.tab').forEach(s=>s.hidden=s.id!==h);
document.querySelectorAll('nav.tabs a').forEach(a=>a.classList.toggle('on',a.dataset.t===h))}}addEventListener('hashchange',tab);tab();
document.querySelectorAll('details.fold').forEach(d=>{{try{{const v=localStorage.getItem('fold:'+d.dataset.k);if(v!==null)d.open=v==='1'}}catch(e){{}}
d.addEventListener('toggle',()=>{{try{{localStorage.setItem('fold:'+d.dataset.k,d.open?'1':'0')}}catch(e){{}}}})}});</script></body></html>"""


FLOW = ROOT / "econ" / "flow"
MIN_SCORE = 50  # 키워드 이 점수 미만은 도우미에 안 보여 줌 (대표 지시 2026-10-05)
_REFS = (yaml.safe_load((ROOT / "config" / "econ_refs.yaml").read_text(encoding="utf-8")) or {}) \
    if (ROOT / "config" / "econ_refs.yaml").exists() else {}
REF_MAIN = _REFS.get("main", "")
REF_NAMES = _REFS.get("bloggers", {}) if isinstance(_REFS.get("bloggers"), dict) else {}


def aside_html(kw: dict) -> str:  # 옛 이름 (status_html로 합침, 2026-10-08)
    return ""


def status_html(kw: dict, day: Path, today: str) -> str:
    """한 줄 상태: 어사이드 도착 · 오늘 자동 글 (대표 지시 2026-10-08: 설명 글 없이)."""
    e = html.escape
    a = kw.get("aside")
    chips = [f'🛰 어사이드 {e(a.get("at", ""))} · {a.get("n", 0)}개' if a else "🛰 어사이드 아직"]
    if BID != "econ":  # 패션은 자동 글 없음 (대표 결정 2026-10-08)
        return f'<div class="muted" style="margin:4px 0 10px">{chips[0]}</div>'
    st = (yaml.safe_load((day / "auto.yaml").read_text(encoding="utf-8")) or {}) if (day / "auto.yaml").exists() else {}
    again = desk.issue_link(f"{LABEL}자동", today, "오늘 자동 글을 다시 만들어 주세요.")
    retry = f' <a href="{e(again, quote=True)}">다시 돌리기</a>'
    done = len(st.get("done", []))
    if st.get("status") == "완료":
        chips.append(f"🤖 자동 글 {done}편")
    elif st.get("status") == "진행중":
        started = datetime.strptime(f"{today} {st.get('at', '00:00')}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        chips.append(f"⏳ 자동 글 {done}/3" if datetime.now(KST) - started < timedelta(minutes=90) else f"⚠️ 자동 글 멈춤{retry}")
    elif st.get("status") == "실패":
        chips.append(f"⚠️ 자동 글 실패{retry}")
    elif datetime.now(KST).hour >= 11:
        chips.append(f"⚠️ 자동 글 안 돎{retry}")
    else:
        chips.append("🕙 자동 글 10시")
    return f'<div class="muted" style="margin:4px 0 10px">{" · ".join(chips)}</div>'


TA = "width:100%;font:inherit;line-height:1.6;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0;background:var(--card);color:var(--ink);resize:vertical"


def has_info(it: dict) -> bool:
    """패션 키워드에 정확한 제품 정보(브랜드·제품·가격)가 있는지 (대표 지시 2026-10-08: 패션은 이런 것만 보여 줌)."""
    if (it.get("product") or "").strip() or re.search(r"\d[\d,.]*\s*(만|억)?\s*원", it.get("kw", "")):
        return True
    from .blogs import get as _bget
    cfg_f = ROOT / _bget(BID).get("keywords", "")
    brands = (yaml.safe_load(cfg_f.read_text(encoding="utf-8")) or {}).get("brands", []) if cfg_f.is_file() else []
    text = it.get("kw", "").replace(" ", "").lower()
    return any(b.replace(" ", "").lower() in text for b in brands)


def written_today(day: Path) -> dict[str, str]:
    """오늘 이미 글이 된 키워드 → 글 폴더 이름 (키워드 옆 ✅, 대표 지시 2026-10-08)."""
    out = {}
    for t in day.glob("*/titles.yaml") if day.exists() else []:
        T = yaml.safe_load(t.read_text(encoding="utf-8")) or {}
        if (t.parent / "chosen.yaml").exists() or (POSTS / t.parent.name).exists():
            out[T.get("keyword", "")] = t.parent.name
    return out


def score_table(items: list[dict]) -> str:
    """키워드 점수표 (대표 요청 2026-10-09 '점수표 살려 줘') — 접어서."""
    e = html.escape
    keys = list(dict.fromkeys(k for it in items for k in (it.get("parts") or {})))
    if not items or not keys:
        return ""
    th = "".join(f"<th>{e(k)}</th>" for k in keys)
    tr = "".join(f'<tr><td style="text-align:left">{e(it["kw"])}</td><td><b>{it.get("score", "")}</b></td>'
                 + "".join(f'<td>{(it.get("parts") or {}).get(k, "")}</td>' for k in keys) + "</tr>" for it in items)
    return (f'<details style="margin-top:6px"><summary class="muted">점수표</summary><div style="overflow-x:auto">'
            f'<table style="font-size:12px;border-collapse:collapse;width:100%;text-align:center"><tr><th style="text-align:left">키워드</th>'
            f'<th>합계</th>{th}</tr>{tr}</table></div></details>')


def rising_html(day: Path, today: str) -> str:
    """📈 네이버 급상승 (어사이드 없이 공식 API, 하루 3번 — content/rising.py, 대표 요청 2026-10-10).
    경제: 누르면 제목 후보 만들기 / 패션: 누르면 아래 '글 만들기' 칸에 들어감. 키워드 카드 안에 붙는다."""
    e = html.escape
    f = day / "rising.yaml"
    R = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    again = desk.issue_link(f"{LABEL}급상승", today, "네이버 급상승 키워드를 다시 찾아 주세요.")
    rows = []
    for it in R.get("items", []):
        meta = f'×{it.get("rise", "")}' + (f' · 새 글 {it["blog24h"]}' if it.get("blog24h") is not None else "") \
            + (f' · {it["section"]}' if it.get("section") else "")
        label = f'<b>{e(it["kw"])}</b> <span class="seal">{it.get("score", "")}</span>' \
                f'<div class="muted" style="font-size:12px">{e(meta)}</div>'
        if BID == "econ":
            link = desk.issue_link(f"{LABEL}키워드", it["kw"], "이 키워드로 제목 후보를 만들어 주세요.")
            rows.append(f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                        f'href="{e(link, quote=True)}">{label}</a>')
        else:
            rows.append(f'<button class="ghost" style="text-align:left;width:100%" '
                        f'onclick="pick_{BID}({e(json.dumps(it["kw"]), quote=True)})">{label}</button>')
    when = f'{R.get("updated", "")} 기준 · 최근 3일 검색 상승' if R else "아직 없음"
    return (f'<div style="margin-top:14px;padding-top:10px;border-top:1px solid var(--line)"><b>📈 네이버 급상승</b>'
            f'<div class="muted" style="margin:4px 0 6px;font-size:13px">{e(when)}</div>'
            f'{"".join(rows[:5])}'
            + (f'<details><summary class="muted">더 보기 {len(rows) - 5}개</summary>{"".join(rows[5:])}</details>' if len(rows) > 5 else "")
            + f'<a class="btn" style="margin-top:8px;background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(again, quote=True)}">🔄 급상승 다시 찾기</a></div>')


def kw_row(it: dict, done: dict[str, str]) -> str:
    """키워드 한 줄: 글이 됐으면 ✅ + 글로, 아니면 누르면 제목 후보 만들기 (대표 결정 2026-10-09: 키워드는 대표가 고름)."""
    e = html.escape
    slug = done.get(it["kw"])
    href = f"p/{BID}-{desk.slug(slug)}/" if slug and (POSTS / slug).exists() else \
        desk.issue_link(f"{LABEL}키워드", it["kw"], "이 키워드로 제목 후보를 만들어 주세요.")
    sc = f' <span class="seal">{it["score"]}</span>' if "score" in it else ""
    return (f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
            f'href="{e(href, quote=True)}">{"✅ " if slug else ""}<b>{e(it["kw"])}</b>{sc}</a>')


def flow_html() -> str:
    """키워드(대표가 고름) → 제목 후보(프롬프트 기준) → 대표가 제목 고름(패션은 상품 링크도) → 글 (대표 결정 2026-10-09 역할 정리).
    경제 키워드 = 국내주식·해외주식·금·비트코인·부동산·환율·생활경제 섹션마다 3개 (config sections) / 패션 = 점수 상위 5개."""
    from .econ_sections import pick
    e = html.escape
    today = datetime.now(KST).strftime("%Y-%m-%d")
    day = FLOW / today
    kw = (yaml.safe_load((day / "keywords.yaml").read_text(encoding="utf-8")) or {}) if (day / "keywords.yaml").exists() else {}
    done = written_today(day)
    items = sorted(kw.get("items", []), key=lambda x: -x.get("score", 0))
    if BID == "econ":
        from .econ_score import CFG as _kcfg
        from .econ_flow import load as _load
        c = _load(_kcfg(), {}) or {}
        secs = pick(items, c.get("sections", ["국내주식", "해외주식", "금·비트코인"]), c.get("section_n", 3), c.get("min_show", 75))
        shown = [it for xs in secs.values() for it in xs]
        rows = "".join(f'<div class="muted" style="margin:10px 0 2px;font-weight:700">{e(name)}</div>'
                       + ("".join(kw_row(it, done) for it in xs) or '<div class="muted" style="font-size:13px">없음</div>')
                       for name, xs in secs.items())
    else:
        shown = items[:5]  # 패션: 점수 상위 5개 (대표 결정 2026-10-09: 렌즈로 대표가 찾으니 정보 없는 키워드도)
        def frow(it: dict) -> str:  # 패션 키워드를 누르면 깃헙이 아니라 아래 '글 만들기' 칸에 들어감 (대표 결정 2026-10-09: 어제 방식)
            slug = done.get(it["kw"])
            sc = f' <span class="seal">{it["score"]}</span>' if "score" in it else ""
            if slug and (POSTS / slug).exists():
                return (f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                        f'href="p/{BID}-{desk.slug(slug)}/">✅ <b>{e(it["kw"])}</b>{sc}</a>')
            return (f'<button class="ghost" style="text-align:left;width:100%" onclick="pick_{BID}({e(json.dumps(it["kw"]), quote=True)})">'
                    f'<b>{e(it["kw"])}</b>{sc}</button>')
        rows = "".join(frow(it) for it in shown) or "<p class=muted>없음</p>"
    add_js = (f"function addKw_{BID}(){{const v=document.getElementById('kwin-{BID}').value.split('\\n').filter(l=>!/^\\s*http/.test(l)).join('\\n').trim();if(!v)return;"
              f"location.href='https://github.com/{desk.REPO}/issues/new?title='+encodeURIComponent('[{LABEL}키워드추가] {today}')"
              "+'&body='+encodeURIComponent(v)}")
    if BID != "econ":  # 패션: 키워드를 누르면 아래 '글 만들기' 칸에 들어감 → 링크 붙여 ✍️ 글 만들기 (대표 요청 2026-10-10 탭 정리)
        add_js += (f"function pick_{BID}(k){{const t=document.getElementById('kwin-{BID}');t.value=k+'\\n';"
                   "t.scrollIntoView({behavior:'smooth',block:'center'});t.focus()}")
        add_js += (f"function pickT_{BID}(tok){{const f=tok.slice(0,tok.lastIndexOf(' '));const t=document.getElementById('lkt-'+f);"
                   "t.dataset.tok=tok;t.scrollIntoView({behavior:'smooth',block:'center'});t.focus();"
                   "t.placeholder='제목 선택됨 · 상품 링크를 넣으세요'}"
                   f"function writeT_{BID}(f){{const t=document.getElementById('lkt-'+f);const tok=t.dataset.tok;"
                   "if(!tok){alert('위에서 제목을 먼저 눌러 주세요');return}"
                   f"location.href='https://github.com/{desk.REPO}/issues/new?title='+encodeURIComponent('[{LABEL}제목] '+tok)"
                   "+'&body='+encodeURIComponent(t.value.trim()||'(링크 없음)')}")
    refresh = desk.issue_link(f"{LABEL}키워드새로", today, "키워드를 다시 모아 주세요.")
    # 직접 입력한 주제 (대표 요청 2026-10-09): 제목 뽑기 = 제목 후보만 / 바로 글 = 조사 → 제목 → ★제목으로 글
    issue = f"https://github.com/{desk.REPO}/issues/new?title="
    add_js += (f"function tpv_{BID}(){{return document.getElementById('kwin-{BID}').value.trim()}}"
               f"function tpTitles_{BID}(){{const v=tpv_{BID}().split('\\n')[0].trim();if(!v)return;"
               f"location.href='{issue}'+encodeURIComponent('[{LABEL}키워드] '+v)+'&body='+encodeURIComponent('이 주제로 조사해서 제목 후보를 만들어 주세요.')}}"
               f"function tpWrite_{BID}(){{const v=tpv_{BID}();if(!v)return;"
               f"location.href='{issue}'+encodeURIComponent('[{LABEL}주제글] {today}')+'&body='+encodeURIComponent(v)}}")
    # 글 만들기 칸 하나로 (대표 요청 2026-10-10 탭 정리: '상품 링크로 글'·'직접 주제' 두 칸 → 하나)
    small = 'class="ghost" style="margin:0;padding:10px 4px;font-size:14px"'
    if BID == "econ":
        tip = "주제 (예: 30대 순자산 평균)"
        main = f'<button onclick="tpTitles_{BID}()">📝 제목 뽑기</button>'
        subs = (f'<button {small} onclick="tpWrite_{BID}()">✍️ 제목 없이 바로 글</button>'
                f'<button {small} onclick="addKw_{BID}()">➕ 키워드 목록에</button>')
    else:
        tip = "첫 줄: 주제 (예: 카리나 공항 가방) — 위 키워드를 누르면 들어와요&#10;다음 줄: 상품 링크 (있으면, 한 줄에 하나)"
        main = f'<button onclick="tpWrite_{BID}()">✍️ 글 만들기</button>'
        subs = (f'<button {small} onclick="tpTitles_{BID}()">📝 제목만 먼저</button>'
                f'<button {small} onclick="addKw_{BID}()">➕ 키워드 목록에</button>')
    topic_box = (f'<div class="card"><h2>글 만들기</h2><textarea id="kwin-{BID}" rows="{2 if BID == "econ" else 4}" style="{TA}" placeholder="{tip}"></textarea>'
                 f'{main}<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px">{subs}</div>'
                 '<div class="muted" style="font-size:12px;margin-top:6px">누르면 깃허브 화면이 열려요 → 초록 Create 버튼만 누르면 접수돼요.</div></div>')
    a = kw.get("aside")
    aside = f'🛰 어사이드 {e(a.get("at", ""))} · {a.get("n", 0)}개' if a else "🛰 어사이드 아직"
    kw_html = (f'<div class="card"><h2>키워드</h2><div class="muted" style="margin:4px 0 6px">{aside}</div>{rows}'
               f'{score_table(shown)}'
               f'<a class="btn" style="margin-top:8px;background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(refresh, quote=True)}">🔄 다시 모으기</a>'
               f'{rising_html(day, today)}<script>{add_js}</script></div>{topic_box}')
    topics = []
    for t in sorted(day.glob("*/titles.yaml")) if day.exists() else []:
        T = yaml.safe_load(t.read_text(encoding="utf-8")) or {}
        if (t.parent / "chosen.yaml").exists():
            continue  # 글이 된 주제는 안 보임
        f = t.parent.name
        groups = title_groups(T)
        if BID == "econ":  # 경제: 제목을 누르면 글
            def btn(i: int, it: dict) -> str:
                link = desk.issue_link(f"{LABEL}제목", f"{f} {i}", "이 제목으로 글을 만들어 주세요.")
                return (f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                        f'href="{e(link, quote=True)}">{"★ " if it.get("rank") == 1 else ""}{e(it["title"])}{badge(it["title"], it.get("type", ""))}</a>')
        else:  # 패션(직접 주제로 제목만 뽑은 경우): 제목을 누르면 상품 링크 칸에 '폴더 번호'가 들어가고, 링크 붙여 글 쓰기
            def btn(i: int, it: dict) -> str:
                tok = f"{f} {i}"
                return (f'<button class="ghost" style="text-align:left;width:100%" onclick="pickT_{BID}({e(json.dumps(tok), quote=True)})">'
                        f'{"★ " if it.get("rank") == 1 else ""}{e(it["title"])}{badge(it["title"], it.get("type", ""))}</button>')
        head_g, rest_g = (groups[0], groups[1:]) if groups else (("", []), [])
        n_rest = sum(len(xs) for _, xs in rest_g)
        body = "".join(btn(i, it) for i, it in head_g[1])
        if rest_g:
            body += (f'<details><summary class="muted">다른 제목 {n_rest}개</summary>'
                     + "".join(f'<div class="muted" style="margin:8px 0 2px;font-size:13px">{e(name)}</div>'
                               + "".join(btn(i, it) for i, it in xs) for name, xs in rest_g) + '</details>')
        again = desk.issue_link(f"{LABEL}제목새로", T.get("keyword", ""), "다시 조사해서 새로 뽑아 주세요.")
        if BID != "econ":
            body += (f'<textarea id="lkt-{e(f, quote=True)}" rows="3" style="{TA};margin-top:10px" '
                     f'placeholder="위에서 제목을 누르고, 구글 렌즈로 찾은 상품 링크를 여기에 (한 줄에 하나)"></textarea>'
                     f'<button onclick="writeT_{BID}({e(json.dumps(f), quote=True)})">✍️ 이 제목 + 링크로 글 쓰기</button>'
                     + blog_links(T.get("keyword", "")))
        topics.append(f'<div class="card"><h2>제목 · {e(T.get("keyword", ""))}</h2>{body}'
                      f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(again, quote=True)}">🔄 다시 뽑기</a>{rules_html()}</div>')
    return kw_html + "".join(topics)


def masters_html() -> str:
    """제목 고수(경제토르·유미) 최근 제목과 공식 — ② 칸 안에 접어서 (대표 지시 2026-10-05, content/title_refs.py)."""
    from .title_refs import GUIDE, for_blog, guide_text, history
    e = html.escape
    parts = []
    mine = for_blog(BID)  # 경제 탭 = 경제토르, 패션 탭 = 유미 (2026-10-05)
    for bid, name in mine.items():
        ps = history(bid)
        if not ps:
            continue
        rows = "".join(f'<div style="padding:4px 0;border-bottom:1px solid var(--line)">{e(p["title"])}'
                       f'<br><span class="muted">{e(p["at"][:10])}{" · " + e(p["category"]) if p.get("category") else ""}</span></div>'
                       for p in ps[:15])
        parts.append(f'<details><summary class="muted">{e(name)} 최근 제목 {min(len(ps), 15)}개 (모은 것 {len(ps)}개)</summary>{rows}</details>')
    if GUIDE.exists():
        parts.append(f'<details><summary class="muted">제목 공식 ({e("·".join(mine.values()))} 제목에서 뽑은 틀)</summary>'
                     f'<pre style="white-space:pre-wrap;font-size:13px">{e(guide_text(BID).split(chr(10), 1)[-1][:6000])}</pre></details>')
    if not parts:
        return ""
    return ('<div style="margin-top:14px;padding-top:10px;border-top:1px solid var(--line)"><b>제목 고수 참고</b> '
            f'<span class="muted">{e("·".join(mine.values()))} · 제목 후보도 이 공식을 참고해 만들어요</span>' + "".join(parts) + "</div>")


def inbox_buttons(today: str) -> str:
    """캡처 올리기 · Aside 조사 붙여넣기 (대표 결정 2026-10-05). 둘 다 GitHub 이슈로 받아 workflow가 처리."""
    e = html.escape
    cap = desk.issue_link("경제캡처", today, "이 아래 빈 줄을 누르고, 아래쪽 📎(파일 첨부)로 어드바이저·통계 캡처를 골라 붙여 주세요. 여러 장 가능.")
    ref = desk.issue_link("경제참고", today, "(여기를 지우고 Aside 결과를 통째로 붙여 넣으세요)")
    ghost = "background:transparent;color:var(--ink);border:1px solid var(--line)"
    return (f'<a class="btn" style="{ghost}" href="{e(cap, quote=True)}">📷 어드바이저 캡처 올리기</a>'
            f'<a class="btn" style="{ghost}" href="{e(ref, quote=True)}">📄 Aside 조사 붙여넣기</a>'
            '<div class="muted">캡처는 Claude가 읽어 키워드는 위 목록에, 숫자는 📊 성과에 넣어요. '
            'Aside 조사는 글 구조 참고로만 써요(문장은 안 옮김).</div>')


BLOG = ROOT / "config" / "econ_blog.yaml"
COSTS = ROOT / "econ" / "costs.csv"
METRICS = ROOT / "econ" / "metrics"
CMD_NAME = {"keywords": "키워드 모으기", "titles": "제목 후보", "produce": "글 제작", "capture": "캡처 읽기", "learn": "주간 학습", "refs": "참고 블로거 조사"}


def blog_rss(url: str) -> list[dict]:
    """내 블로그 공개 RSS(공식 통로) → 최근 발행 글 제목·날짜. 실패하면 빈 목록."""
    import xml.etree.ElementTree as ET
    import requests
    m = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)", url or "")
    if not m:
        return []
    try:
        r = requests.get(f"https://rss.blog.naver.com/{m.group(1)}.xml", timeout=20)
        r.raise_for_status()
        return [{"title": (i.findtext("title") or "").strip(), "link": i.findtext("link") or "",
                 "date": i.findtext("pubDate") or ""} for i in ET.fromstring(r.content).iter("item")][:15]
    except Exception as ex:  # noqa: BLE001
        print(f"RSS 실패: {ex}")
        return []


def stats_html(posts: list[dict]) -> str:
    """📊 성과: 비용(월 상한)·발행 수·캡처에서 읽은 숫자·주간 학습 (대표 결정 2026-10-05: 비용은 성과 분석에 씀)."""
    import csv
    from collections import defaultdict
    e = html.escape
    now = datetime.now(KST)
    month, today = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
    rows = list(csv.DictReader(COSTS.open(encoding="utf-8"))) if COSTS.exists() else []
    krw = lambda usd: int(round(usd * 1400))  # noqa: E731  (econ_flow.KRW와 같게)
    mrows = [r for r in rows if r["date"].startswith(month)]
    total = krw(sum(float(r["total_usd"]) for r in mrows))
    by_cmd, by_day = defaultdict(float), defaultdict(float)
    for r in mrows:
        by_cmd[r["cmd"]] += float(r["total_usd"])
        by_day[r["date"]] += float(r["total_usd"])
    made = sum(1 for r in mrows if r["cmd"] == "produce")
    pct = min(100, total * 100 // F_CAP)
    cost = (f'<div class="card"><h2>💰 이번 달 AI 비용</h2><p style="font-size:26px;margin:4px 0"><b>{total:,}원</b> '
            f'<span class="muted">/ 상한 {F_CAP:,}원</span></p>'
            f'<div style="background:var(--line);border-radius:8px;height:12px"><div style="width:{pct}%;height:12px;border-radius:8px;'
            f'background:{"var(--accent)" if pct >= 80 else "var(--pine)"}"></div></div>'
            f'<div class="muted">상한에 닿으면 새 작업이 멈추고 알려 드려요. 글 1편 평균 '
            f'{(krw(sum(float(r["total_usd"]) for r in mrows)) // made) if made else 0:,}원 (키워드·제목 포함).</div>'
            + "".join(f'<div>{e(CMD_NAME.get(k, k))} · {krw(v):,}원</div>' for k, v in sorted(by_cmd.items(), key=lambda x: -x[1]))
            + "<details><summary class=\"muted\">날짜별</summary>"
            + "".join(f'<div>{d[5:]} · {krw(v):,}원</div>' for d, v in sorted(by_day.items(), reverse=True)) + "</details>"
            '<div class="muted">AI 회사 화면의 실제 청구액과 조금 다를 수 있어요(토큰으로 어림).</div></div>')
    used = [p for p in posts if p.get("status", {}).get("status") == "used"]
    today_n = sum(1 for p in used if str(p["status"].get("at", "")).startswith(today))
    month_n = sum(1 for p in used if str(p["status"].get("at", "")).startswith(month))
    pub = (f'<div class="card"><h2>📝 발행</h2><p style="font-size:22px;margin:4px 0">오늘 <b>{today_n}</b> / 2편 · '
           f'이번 달 <b>{month_n}</b>편</p><div class="muted">하루 3편으로 시작해 내 블로그가 홈판에 잘 뜨는 주제를 빨리 찾아요.</div></div>')
    cfg = (yaml.safe_load(BLOG.read_text(encoding="utf-8")) or {}) if BLOG.exists() else {}
    url = cfg.get("url") or ""
    feed = blog_rss(url)
    if url:
        blog = (f'<div class="card"><h2>🏠 내 블로그</h2><a class="btn" href="{e(url, quote=True)}">블로그 열기</a>'
                f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" '
                f'href="https://creator-advisor.naver.com/">크리에이터 어드바이저 열기</a>'
                + ("".join(f'<div>· <a href="{e(i["link"], quote=True)}">{e(i["title"])}</a> <span class="muted">{e(i["date"][5:16])}</span></div>'
                           for i in feed) or '<div class="muted">아직 올라온 글이 없거나 RSS를 못 읽었어요.</div>') + "</div>")
    else:
        blog = '<div class="card"><h2>🏠 내 블로그</h2><div class="muted">블로그 주소를 Claude에게 알려 주시면 여기에 연결돼요 (발행한 글 목록 자동 표시).</div></div>'
    caps = []
    for f in sorted(METRICS.glob("*.yaml"), reverse=True)[:6] if METRICS.exists() else []:
        m = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        tb = "".join(f'<tr><td>{e(x.get("title", ""))[:30]}</td><td>{e(x.get("views", ""))}</td><td>{e(x.get("ctr", ""))}</td></tr>'
                     for x in m.get("posts", [])[:10])
        inflow = " · ".join(f'{e(x[0])}{"(" + e(x[1]) + ")" if len(x) > 1 else ""}' for x in m.get("inflow", [])[:10] if x)
        caps.append(f'<div class="card"><b>📷 {e(m.get("kind", ""))}</b> <span class="muted">{e(m.get("at", ""))} · {e(m.get("note", ""))}</span>'
                    + (f'<table style="width:100%;font-size:14px"><tr><th>글</th><th>조회</th><th>클릭률</th></tr>{tb}</table>' if tb else "")
                    + (f'<div class="muted">유입 검색어: {inflow}</div>' if inflow else "") + "</div>")
    cap_html = "".join(caps) or '<div class="card muted">아직 올린 캡처가 없어요. 📝 블로그 탭의 <b>📷 어드바이저 캡처 올리기</b>로 올리면 여기에 쌓여요.</div>'
    learn = sorted((ROOT / "reports" / "경제-학습").glob("*.md"), reverse=True)[:1]
    learn_html = (f'<details class="card"><summary><b>🧠 이번 주 배운 것</b> <span class="muted">{e(learn[0].stem)}</span></summary>'
                  f'<pre style="white-space:pre-wrap;font-size:13px">{e(learn[0].read_text(encoding="utf-8")[:3000])}</pre></details>') if learn else ""
    rss = sorted((ROOT / "econ" / "ref" / "rss").glob("*.md"), reverse=True)[:1]
    frame = ROOT / "econ" / "ref" / "참고-블로거-틀.md"
    rss_html = ((f'<details class="card" open><summary><b>📚 참고 블로거 새 글</b> <span class="muted">{e(rss[0].stem)}</span></summary>'
                 f'<pre style="white-space:pre-wrap;font-size:13px">{e(rss[0].read_text(encoding="utf-8")[:6000])}</pre></details>') if rss else "") + (
        (f'<details class="card"><summary><b>📐 참고 블로거 틀</b> <span class="muted">썸네일·제목·글 구성 (한 번 분석)</span></summary>'
         f'<pre style="white-space:pre-wrap;font-size:13px">{e(frame.read_text(encoding="utf-8")[:8000])}</pre></details>') if frame.exists() else "")
    return ("<div>" + cost + pub + blog + rss_html + "</div><div><h2>캡처에서 읽은 숫자</h2>" + cap_html + learn_html + "</div>")


def aside_tab(blogs: dict) -> str:
    """🛰 어사이드 탭: 어사이드가 올린 키워드 전체를 경제·패션 각각, 최근 날짜순으로 (대표 요청 2026-10-10)."""
    e = html.escape
    cards = []
    for bid, b in blogs.items():
        flow = b["base"] / "flow"
        days = []
        for f in sorted(flow.glob("*/keywords.yaml"), reverse=True)[:10] if flow.exists() else []:
            try:
                a = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("aside")
            except Exception:  # noqa: BLE001
                a = None
            if a and a.get("list"):
                days.append((f.parent.name, a))
        if days:
            body = "".join(
                f'<details class="fold"{" open" if i == 0 else ""} data-k="aside-{bid}-{day}">'
                f'<summary>{e(day)} · {e(a.get("at", ""))} · {len(a["list"])}개</summary>'
                f'<ol style="margin:6px 0 10px;padding-left:22px">'
                + "".join(f'<li style="padding:2px 0">{e(str(k))}</li>' for k in a["list"]) + '</ol></details>'
                for i, (day, a) in enumerate(days))
        else:
            body = '<p class="muted">어사이드가 올린 키워드가 아직 없어요. 매일 아침 어사이드 루틴이 돌면 여기에 쌓여요.</p>'
        cards.append(f'<div class="card"><h2>{e(b["label"])}</h2>{body}</div>')
    return ('<h2 style="margin:8px 0">🛰 어사이드가 올린 키워드</h2>'
            '<p class="muted" style="margin:0 0 10px">점수·섹션과 상관없이, 어사이드가 네이버에서 모아 올린 그대로예요.</p>'
            + "".join(cards))


def compare_html(blogs: dict, by_blog: dict[str, list[dict]]) -> str:
    """성과: 블로그들을 한 화면에서 비교 (대표 지시 2026-10-05). 비용은 econ/costs.csv의 blog 칸(옛 줄은 경제)."""
    import csv
    e = html.escape
    now = datetime.now(KST)
    month, today = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
    from .econ_flow import COST_FROM  # 이 날부터 다시 셈 (대표 지시 2026-10-06)
    rows = [r for r in (csv.DictReader(COSTS.open(encoding="utf-8")) if COSTS.exists() else [])
            if r["date"].startswith(month) and r["date"] >= COST_FROM]
    krw = lambda usd: int(round(usd * 1400))  # noqa: E731  (econ_flow.KRW와 같게)
    total = krw(sum(float(r["total_usd"]) for r in rows))
    pct = min(100, total * 100 // F_CAP)
    head_ = (f'<div class="card"><h2>이번 달 AI 비용</h2><p style="font-size:26px;margin:4px 0"><b>{total:,}원</b> '
             f'<span class="muted">/ 상한 {F_CAP:,}원</span></p><div style="background:var(--line);border-radius:8px;height:12px">'
             f'<div style="width:{pct}%;height:12px;border-radius:8px;background:var(--accent)"></div></div>'
             '</div>')
    cols, lines = [], {"오늘 발행 / 2": [], "이번 달 발행": [], "만든 글": [], "이번 달 비용": [],
                       "키워드 모으기 (1번)": [], "제목 후보 (키워드 1개)": [], "글·사진 만들기 (1편)": [], "글 1편 어림": []}
    for bid, b in blogs.items():
        posts = by_blog.get(bid, [])
        used = [p for p in posts if p.get("status", {}).get("status") == "used"]
        mine = [r for r in rows if (r.get("blog") or "econ") == bid]
        won = krw(sum(float(r["total_usd"]) for r in mine))
        made = sum(1 for r in mine if r["cmd"] == "produce")
        lines["오늘 발행 / 2"].append(sum(1 for p in used if str(p["status"].get("at", "")).startswith(today)))
        lines["이번 달 발행"].append(sum(1 for p in used if str(p["status"].get("at", "")).startswith(month)))
        lines["만든 글"].append(len(posts))
        lines["이번 달 비용"].append(f"{won:,}원")
        # 단계별로 나눠 보기 (대표 질문 2026-10-06 "글 하나에 천원꼴? 키워드 조사는 한 번이니 나눠 봐야?")
        def avg(cmd):
            v = [float(r["total_usd"]) for r in mine if r["cmd"] == cmd]
            return (krw(sum(v) / len(v)), len(v)) if v else (None, 0)
        (kw_a, kw_n), (ti_a, ti_n), (pr_a, pr_n) = avg("keywords"), avg("titles"), avg("produce")
        cell = lambda a, n: f"{a:,}원 <span class=\"muted\">({n}번)</span>" if a is not None else "-"  # noqa: E731
        lines["키워드 모으기 (1번)"].append(cell(kw_a, kw_n))
        lines["제목 후보 (키워드 1개)"].append(cell(ti_a, ti_n))
        lines["글·사진 만들기 (1편)"].append(cell(pr_a, pr_n))
        kw_share = krw(sum(float(r["total_usd"]) for r in mine if r["cmd"] == "keywords") / pr_n) if pr_n else 0
        lines["글 1편 어림"].append(f"{(ti_a or 0) + (pr_a or 0) + kw_share:,}원" if pr_n else "-")
        feed = blog_rss(b.get("url", ""))
        link = (f'<a class="btn" href="{e(b["url"], quote=True)}">블로그 열기</a>' if b.get("url")
                else '<div class="muted">블로그 주소를 알려 주시면 연결돼요.</div>')
        recent = "".join(f'<div style="font-size:14px">· <a href="{e(i["link"], quote=True)}">{e(i["title"])}</a></div>'
                         for i in feed[:5]) or '<div class="muted">최근 발행 글이 아직 없어요.</div>'
        cols.append(f'<div class="card"><h2>{e(b["label"])} · {e(b["name"])}</h2>{link}<div class="muted" style="margin-top:8px">최근 발행 글</div>{recent}</div>')
    th = "".join(f'<th style="text-align:right;padding:6px">{e(b["label"])}</th>' for b in blogs.values())
    tr = "".join(f'<tr><td style="padding:6px">{e(k)}</td>' + "".join(f'<td style="text-align:right;padding:6px"><b>{v}</b></td>' for v in vals)
                 + "</tr>" for k, vals in lines.items())
    table = (f'<div class="card"><h2>한눈에 비교</h2><table style="width:100%;border-collapse:collapse;font-size:15px">'
             f'<tr><th style="text-align:left;padding:6px">항목</th>{th}</tr>{tr}</table></div>')
    grid = f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">{"".join(cols)}</div>'
    note = ('<div class="card muted" style="font-size:14px">글 1편 어림 = 제목 후보 1번 + 글·사진 1번 + 키워드 모으기 비용을 만든 글 수로 나눈 몫. '
            '제목을 다시 뽑거나 고른 키워드로 글을 안 만들면 그만큼 더 들어요.</div>')
    return stats_html(blogs) + head_  # 어사이드 통계 위, 비용 아래, 나머지 없앰 (대표 지시 2026-10-08)


def stats_html(blogs: dict) -> str:
    """지난주 블로그 성과 (어사이드가 매주 월요일 읽은 네이버 블로그 통계, 대표 결정 2026-10-08). 없으면 한 줄만."""
    from .blog_stats import recent
    e = html.escape
    rs = recent(8)
    if not rs:
        return '<div class="card muted">블로그 통계 없음</div>'
    last = rs[0]
    cols = []
    for bid, b in blogs.items():
        d = (last.get("blogs") or {}).get(bid)
        if not d:
            continue
        prev = next(((r.get("blogs") or {}).get(bid, {}).get("total", {}).get("조회") for r in rs[1:] if (r.get("blogs") or {}).get(bid)), None)
        tot = d.get("total", {})
        diff = (f' <span class="muted">(전날 {prev:,})</span>' if prev else "")
        posts = "".join(f'<li>{e(r["title"])} <b>{r.get("조회", 0):,}</b>'
                        f'<span class="muted">{" · 공감 " + str(r["공감"]) if r.get("공감") else ""}{" · 댓글 " + str(r["댓글"]) if r.get("댓글") else ""}</span></li>'
                        for r in d.get("posts", [])[:5])
        qs = " · ".join(f'{e(q["q"])}{" " + str(q["n"]) if q.get("n") else ""}' for q in d.get("queries", [])[:8])
        ps = " · ".join(f'{e(x["path"])} {e(x.get("share", ""))}' for x in d.get("paths", [])[:5])
        cols.append(f'<div class="card"><h2>{e(b["label"])} · {e(d.get("period") or last.get("date", ""))}</h2>'
                    f'<p style="font-size:22px;margin:4px 0">조회 <b>{tot.get("조회", 0):,}</b>{diff} · 방문 <b>{tot.get("방문", 0):,}</b></p>'
                    f'{"<b>많이 본 글</b><ol style=margin:4px 0 8px 18px>" + posts + "</ol>" if posts else ""}'
                    f'{"<b>유입 검색어</b><div class=muted>" + qs + "</div>" if qs else ""}'
                    f'{"<b style=display:block;margin-top:6px>유입 경로</b><div class=muted>" + ps + "</div>" if ps else ""}</div>')
    return (f'<h2 style="margin:8px 0">지난주 블로그 성과</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">'
            f'{"".join(cols)}</div>') if cols else ""


def load() -> list[dict]:
    out = []
    for f in sorted((x for x in POSTS.iterdir() if x.is_dir()), reverse=True) if POSTS.exists() else []:
        p = desk.parse(f)
        if p:
            p["short"] = read_short(f)
            out.append(p)
    return out


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u23E9-\u23FA\u2122\u2139\u24C2]\\s?")


def plain(html_text: str) -> str:
    """이모지 없이 (대표 지시 2026-10-05). 화살표(→ ←)·동그라미 숫자는 남긴다."""
    return EMOJI.sub("", html_text)


def build(out: Path) -> list[dict]:
    from .blogs import all_blogs
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    by_blog, everything = {}, []
    for bid, b in all_blogs().items():
        use(b)
        posts = load()
        by_blog[bid] = posts
        everything += posts
        for p in posts:
            d = out / "p" / f"{bid}-{desk.slug(p['folder'])}"
            d.mkdir(parents=True)
            for x in p["images"]:
                src = POSTS / p["folder"] / x["file"]
                if src.exists():
                    shutil.copy(src, d / x["file"])
            (d / "index.html").write_text(plain(page(p)), encoding="utf-8")
    (out / "index.html").write_text(plain(index(by_blog)), encoding="utf-8")
    fb = all_blogs().get("fashion")
    if fb:  # 착장 도우미 (2026-10-10)
        (out / "outfit").mkdir(exist_ok=True)
        (out / "outfit" / "index.html").write_text(plain(outfit_page(fb, by_blog.get("fashion", []))), encoding="utf-8")
    (out / "photo").mkdir(exist_ok=True)
    (out / "photo" / "index.html").write_text(plain(photo_page()), encoding="utf-8")  # 사진 크기 맞추기 (2026-10-07)
    for s in (180, 192, 512):
        shutil.copy(BRAND / f"desk-icon-{s}.png", out / f"icon-{s}.png")
    (out / "manifest.webmanifest").write_text(json.dumps({
        "name": f"{NAME} 발행 도우미", "short_name": "발행 도우미", "start_url": "./", "display": "standalone",
        "background_color": "#f5f4ee", "theme_color": "#c96442",
        "icons": [{"src": f"icon-{s}.png", "sizes": f"{s}x{s}", "type": "image/png"} for s in (192, 512)]},
        ensure_ascii=False), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8")
    return everything


def mark(title: str) -> str | None:
    """'[경제|연예|패션발행완료] <글>' → 그 블로그 posts/<글>/status.yaml. 처리한 글 이름 (형식이 다르거나 없는 글이면 None)."""
    from .blogs import by_label
    m = MARK.match(title.strip())
    b = by_label(m.group(1)) if m else None
    if not b or not (b["base"] / "posts" / m.group(2) / "post.md").exists():
        return None
    f = b["base"] / "posts" / m.group(2) / "status.yaml"
    st = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    st.update(status="used", at=datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
    f.write_text(yaml.safe_dump(st, allow_unicode=True), encoding="utf-8")
    return m.group(2)


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--mark":
        name = mark(sys.argv[2])
        print(f"발행 완료 표시: {name}" if name else "형식이 다르거나 없는 글")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
                fh.write(f"folder={name or ''}\n")
        sys.exit(0 if name else 1)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site-econ"
    posts = build(out)
    print(f"{NAME} 발행 도우미: 글 {len(posts)}편 → {out}")


if __name__ == "__main__":
    main()
