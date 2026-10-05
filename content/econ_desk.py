"""경제 블로그 발행 도우미 '억선생의 경제판' (2026-10-05, 대표 지시: 스포츠처럼 홈 화면에 깔아 두고 쓰게).

- econ/posts/<날짜-주제>/ 의 발행 패키지(post.md · body.txt · 사진 · short.mp4 · short.txt)를 휴대폰용 정적 사이트로 만든다.
- 글마다: 사진 한 번에 저장 → 제목 → 썸네일 → 본문 복사 → 태그 → 쇼츠·클립(영상 저장 + 설명·해시태그) → 발행 완료.
- 글 형식은 스포츠 도우미와 같다(content/desk.parse 재사용). 색은 화투 팔레트, 홈 화면 아이콘은 억선생 프로필.
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
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from market.common import ROOT
from . import desk

POSTS = ROOT / "econ" / "posts"
BRAND = ROOT / "assets" / "brand"
NAME = "억선생의 경제판"
KST = ZoneInfo("Asia/Seoul")
MARK = re.compile(r"^\[경제발행완료\]\s*(\d{4}-\d{2}-\d{2}-[\w가-힣-]+)\s*$")

CSS = desk.CSS + """
:root{--bg:#f3ebdd;--card:#fffaf1;--ink:#16140f;--soft:#6b5e4a;--line:#e0d3bd;--accent:#c81e28;--btn:#16140f;--btnink:#f3ebdd;--gold:#e8b422;--pine:#1e5a3a}
@media (prefers-color-scheme:dark){:root{--bg:#16140f;--card:#221e17;--ink:#f3ebdd;--soft:#b9ab92;--line:#3a3328;--btn:#f3ebdd;--btnink:#16140f}}
header.brand{display:flex;align-items:center;gap:12px;margin:6px 0 4px}
header.brand img{width:56px;height:56px;border-radius:50%;border:3px solid var(--accent)}
header.brand h1{margin:0;font-size:21px}header.brand .muted{margin:0}
.step{background:var(--accent)}h2{border-left:5px solid var(--accent);padding-left:8px}
nav.tabs{display:flex;gap:6px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}
nav.tabs a{flex:1;text-align:center;padding:12px 4px;border-radius:12px;border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:700}
nav.tabs a.on{background:var(--accent);color:#fff;border-color:var(--accent)}
/* 태블릿 (대표 주 작업 기기, 2026-10-05): 넓은 화면은 두 칸 — 왼쪽 할 일, 오른쪽 결과 */
@media (min-width:900px){main{max-width:1240px}.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}
.cols>div>.card:first-child,.cols>div>h2:first-child{margin-top:0}.stick{position:sticky;top:64px;max-height:calc(100vh - 80px);overflow:auto}nav.tabs{max-width:640px}}
.seal{display:inline-block;background:var(--accent);color:#fff;border-radius:6px;padding:0 6px;font-weight:800}
"""


def head(title: str, depth: str = "") -> str:
    e = html.escape
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<meta name="theme-color" content="#c81e28"><link rel="manifest" href="{depth}manifest.webmanifest">
<link rel="apple-touch-icon" href="{depth}icon-180.png"><meta name="apple-mobile-web-app-title" content="억선생 도우미">
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


def page(p: dict) -> str:
    e = html.escape
    best = next((t for t in p["titles"] if t["best"]), p["titles"][0] if p["titles"] else {"text": p["folder"], "type": ""})
    status = ('<span class="badge ok">✅ 발행 가능</span>' if p["ok"] else
              '<span class="badge warn">⚠️ 확인 필요 — 발행하지 말고 Claude에게 알려주세요</span>')
    probs = "".join(f"<li>{e(x)}</li>" for x in p["problems"])
    rest = "".join(f'<button class="ghost" onclick="setEd(\'title\',{e(json.dumps(t["text"]), quote=True)})">{e(t["text"])}'
                   f' <span class="muted">· {e(t["type"])} · 이 제목으로 바꾸기</span></button>' for t in p["titles"] if t is not best)
    body = "".join(
        f'<textarea class="ed" data-k="b{i}" rows="3">{e(b["text"])}</textarea>' if "text" in b else
        f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy"><small>📷 사진 {b["n"]} · {e(b["label"])}</small></div>'
        for i, b in enumerate(p["blocks"]) if "text" in b or "img" in b)
    each = "".join(f'<div class="ph"><img src="{e(x["file"])}" alt="사진 {x["n"]}" loading="lazy"><small>📷 사진 {x["n"]} · {e(x["label"])}'
                   f'{" · 대표이미지로 지정" if x["n"] == 1 else ""} (길게 눌러 저장)</small></div>' for x in p["images"])
    tags = " ".join("#" + t for t in p["tags"])
    chips = "".join(f'<button class="ghost chip" onclick="copyText(this,{e(json.dumps(t), quote=True)})">{e(t)}</button>' for t in p["tags"])
    thumb = next((x["file"] for x in p["images"] if x["n"] == 1), "")
    data = json.dumps({"blocks": p["blocks"], "images": p["images"], "folder": p["folder"], "repo": desk.REPO,
                       "editTag": "[경제수정]"},
                      ensure_ascii=False).replace("</", "<\\/")
    used = p.get("status", {}).get("status") == "used"
    done = desk.issue_link("경제발행완료", p["folder"], "블로그·쇼츠·클립 발행을 마쳤어요.")
    return head(best["text"], "../../") + f"""
<a href="../../" class="muted">← 글 목록</a>
<h1>{e(best["text"])}</h1><div class="muted">{e(p["date"])} · 카테고리 {e(p["category"])}</div>
<p>{status}</p>{f"<ul>{probs}</ul>" if probs else ""}
{'<div class="card" style="border-color:var(--accent)"><b>⚠️ 이미 발행한 글이에요</b><div class="muted">같은 글을 두 번 올리지 마세요.</div></div>' if used else ''}
<div class="cols"><div>
<div class="card"><h2><span class="step">1</span>사진 저장</h2>
<button onclick="saveAll(this)">📷 사진 {len(p["images"])}장 한 번에 저장</button>
<div class="muted">공유 창에서 "이미지 저장"을 누르세요. 파일 이름 앞 번호가 넣는 순서예요.</div></div>
<div class="card"><h2><span class="step">2</span>제목</h2>{desk.edit_box("title", best["text"], "제목 복사", one_line=True)}
{f'<details><summary class="muted">다른 제목 {len(p["titles"]) - 1}개</summary>{rest}</details>' if rest else ''}</div>
<div class="card"><h2><span class="step">3</span>대표 사진 (썸네일)</h2>{f'<img class="thumb" src="{e(thumb)}" alt="썸네일">' if thumb else ''}
<div class="muted">본문에 넣은 뒤 이 그림을 대표이미지로 지정하세요.</div></div>
<div class="card"><h2><span class="step">4</span>본문</h2>
<button onclick="copyBody(this)">📋 본문 복사 (사진 자리 📷 표시)</button>
<div class="muted">네이버 앱에 붙여넣고, "📷 사진 N" 줄 자리에 N번 사진을 넣으세요. 고칠 문단은 아래 <a href="#draft">초안</a>에서 바로 고치면 복사에 반영돼요.</div></div>
<div class="card"><h2><span class="step">5</span>태그</h2><button class="ghost" onclick="copyText(this,{e(json.dumps(tags), quote=True)})">📋 한 번에 복사: {e(tags)}</button>
<div class="chips">{chips}</div></div>
{video_card(p, "short.mp4") if p.get("short") else ''}
<div class="card"><h2><span class="step">6</span>다 올렸으면</h2>
<a class="btn" href="{e(done, quote=True)}">✅ 발행 완료 표시</a>
<div class="muted">GitHub 화면이 열리면 초록 <b>Create</b>만 누르세요. 2~3분 뒤 목록에서 "발행한 글"로 내려가요.</div></div>
</div><div class="stick">
<div class="card body" id="draft"><h2>✏️ 초안 (눌러서 고치기)</h2>
<div class="muted">고친 문단은 주황 테두리로 보이고, 이 휴대폰에 저장돼 위 <b>본문 복사</b>에 반영돼요.</div>{body}
<button onclick="saveEdits(this)">💾 고친 내용 저장 (다음 글이 배워요)</button>
<div class="muted">제목·문단을 고쳤다면 눌러 주세요. GitHub 화면에서 초록 <b>Create</b>만 누르면, 고친 방향을 모아 다음 글부터 그렇게 써요.</div></div>
</div></div>
<div class="card" id="each"><h2>사진 하나씩 저장</h2>{each}</div>
<details class="card"><summary>출처</summary><pre style="white-space:pre-wrap">{e(p["sources"])}</pre></details>
</main><script>const POST={data};{desk.JS}</script></body></html>"""


def index(posts: list[dict]) -> str:
    e = html.escape
    live = [p for p in posts if p.get("status", {}).get("status") not in ("used", "rejected")]
    used = [p for p in posts if p.get("status", {}).get("status") == "used"]

    def row(p, muted=False):
        t = next((x["text"] for x in p["titles"] if x["best"]), p["folder"])
        mark = "☑️" if muted else ("✅" if p["ok"] else "⚠️")
        v = " · 🎬" if p.get("short") else ""
        style = "text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" + (";opacity:.55" if muted else "")
        return f'<a class="btn" style="{style}" href="p/{desk.slug(p["folder"])}/">{mark} {e(p["date"])} · {e(t)}{v}</a>'

    vids = "".join(f'<div class="card"><b>{e(p["short"]["title"])}</b><div class="muted">{e(p["date"])}</div>'
                   f'<video src="p/{desk.slug(p["folder"])}/short.mp4" controls playsinline preload="none" '
                   f'style="width:100%;max-width:320px;border-radius:10px;display:block;margin-top:8px"></video>'
                   f'<a class="btn" href="p/{desk.slug(p["folder"])}/">글·영상 올리기 화면으로</a></div>'
                   for p in live if p.get("short"))
    now = datetime.now(KST).strftime("%m월 %d일 %H:%M")
    return head(f"{NAME} 발행 도우미") + f"""
<header class="brand"><img src="icon-180.png" alt=""><div><h1>{NAME}</h1><p class="muted">발행 도우미 · {now} 업데이트</p></div></header>
<nav class="tabs"><a href="#blog" data-t="blog">📝 블로그</a><a href="#stats" data-t="stats">📊 성과</a><a href="#video" data-t="video">🎬 영상</a></nav>
<section class="tab" id="blog"><div class="cols"><div>
{flow_html()}
</div><div class="stick">
<h2><span class="step">3</span>올릴 글</h2>{"".join(row(p) for p in sorted(live, key=lambda p: p["folder"], reverse=True)) or '<p class="muted">올릴 글이 아직 없어요.</p>'}
{f'<h2 style="margin-top:28px">발행한 글</h2>' + "".join(row(p, True) for p in used[:10]) if used else ''}
</div></div></section>
<section class="tab" id="stats" hidden><div class="cols">{stats_html(posts)}</div></section>
<section class="tab" id="video" hidden><p class="muted">영상은 당분간 보류예요 (대표 결정 10-05). 글에 집중!</p>{vids or '<p class="muted">올릴 영상이 없어요.</p>'}</section>
<div class="card muted" style="margin-top:28px">홈 화면에 두기: 이 화면에서 브라우저 메뉴(⋮ 또는 공유 ↑) → <b>홈 화면에 추가</b>. 억선생 얼굴 아이콘으로 생겨요.</div>
</main><script>const POST={{"blocks":[],"images":[]}};{desk.JS}
function tab(){{const h=(location.hash||'#blog').slice(1);document.querySelectorAll('section.tab').forEach(s=>s.hidden=s.id!==h);
document.querySelectorAll('nav.tabs a').forEach(a=>a.classList.toggle('on',a.dataset.t===h))}}addEventListener('hashchange',tab);tab();</script></body></html>"""


FLOW = ROOT / "econ" / "flow"
_REFS = (yaml.safe_load((ROOT / "config" / "econ_refs.yaml").read_text(encoding="utf-8")) or {}) \
    if (ROOT / "config" / "econ_refs.yaml").exists() else {}
REF_MAIN = _REFS.get("main", "")
REF_NAMES = _REFS.get("bloggers", {}) if isinstance(_REFS.get("bloggers"), dict) else {}


def flow_html() -> str:
    """① 오늘의 키워드 → ② 제목 고르기 (대표 결정 2026-10-05: 대표가 키워드·제목을 고른 뒤에 전체 제작)."""
    e = html.escape
    today = datetime.now(KST).strftime("%Y-%m-%d")
    day = FLOW / today
    kw = (yaml.safe_load((day / "keywords.yaml").read_text(encoding="utf-8")) or {}) if (day / "keywords.yaml").exists() else {}
    rows = []
    for it in kw.get("items", [])[:20]:
        link = desk.issue_link("경제키워드", it["kw"], "이 키워드로 제목 후보를 만들어 주세요.")
        src = dict(it.get("sources") or {})
        bl = it.get("bloggers") or []
        main_name = REF_NAMES.get(REF_MAIN, "")
        src.pop(REF_MAIN, None)
        src.pop("블로거", None)
        who = " · ".join([("⭐" if b == main_name else "") + b for b in sorted(bl, key=lambda b: b != main_name)]
                         + [f"{k}{'×' + str(v) if v > 1 else ''}" for k, v in src.items()]) or it.get("src", "")
        pt = it.get("parts") or {}
        sc = f' <span class="seal">{it["score"]}점</span>' if "score" in it else ""
        st = it.get("stats") or {}
        bar = (f'<span class="muted">출처 {pt.get("출처", 0)}/40 · 뉴스 {pt.get("뉴스", 0)}/25 · 검색 {pt.get("검색", 0)}/35'
               f'{" · 월검색 " + format(st["월검색"], ",") if st.get("월검색") else ""}</span><br>') if pt else ""
        rows.append(f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                    f'href="{e(link, quote=True)}"><b>{e(it["kw"])}</b>'
                    f'{sc}'
                    f'<br><span class="muted">📌 {e(who)}</span><br>{bar}<span class="muted">{e(it.get("why", ""))}</span></a>')
    add_js = ("function addKw(){const v=document.getElementById('kwin').value.trim();if(!v){alert('키워드를 적어 주세요');return}"
              f"location.href='https://github.com/{desk.REPO}/issues/new?title='+encodeURIComponent('[경제키워드추가] {today}')"
              "+'&body='+encodeURIComponent(v+String.fromCharCode(10,10)+'아래 초록색 Create만 누르면 됩니다.')}")
    refresh = desk.issue_link("경제키워드새로", today, "Grok과 코드로 키워드를 다시 모아 주세요.")
    kw_html = f"""<div class="card" style="border:2px solid var(--accent)"><h2><span class="step">1</span>오늘의 키워드 고르기</h2>
<div class="muted">점수순이에요(100점 = 출처 겹침 40 + 네이버 뉴스량 25 + 검색량 35). 누르면 그 키워드로 <b>제목 후보</b>를 만들어요 (약 3~5분). {e(kw.get("updated", ""))} 기준</div>
{''.join(rows) or '<p class="muted">아직 없어요. 매일 아침 6시쯤 Grok·코드가 모아요.</p>'}
<textarea id="kwin" class="ed" rows="3" placeholder="어드바이저·뉴스 랭킹·트렌드에서 찾은 키워드 (한 줄에 하나)"></textarea>
<button onclick="addKw()">➕ 내 키워드 넣기</button>
{inbox_buttons(today)}
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(refresh, quote=True)}">🔄 Grok으로 다시 모으기</a>
<script>{add_js}</script></div>"""
    topics = []
    for t in sorted(day.glob("*/titles.yaml")) if day.exists() else []:
        T = yaml.safe_load(t.read_text(encoding="utf-8")) or {}
        chosen = t.parent / "chosen.yaml"
        if chosen.exists():
            c = yaml.safe_load(chosen.read_text(encoding="utf-8")) or {}
            topics.append(f'<div class="card"><b>{e(T.get("keyword", ""))}</b> → ✅ 「{e(c.get("title", ""))}」 제작 완료 ({e(c.get("at", ""))}). 아래 목록에서 올리세요.</div>')
            continue
        btns = []
        for i, it in enumerate(T.get("items", []), 1):
            flags = " · ⚠️ " + ", ".join(it["flags"]) if it.get("flags") else ""
            link = desk.issue_link("경제제목", f"{t.parent.name} {i}", "이 제목으로 글·그림·쇼츠를 전부 만들어 주세요.")
            btns.append(f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                        f'href="{e(link, quote=True)}">{i}. {e(it["title"])}<br><span class="muted">{e(it.get("type", ""))} · '
                        f'{it.get("chars", "")}자 · 핵심 "{e(it.get("badge", ""))}"{e(flags)}</span></a>')
        topics.append(f'<div class="card" style="border:2px solid var(--accent)"><h2><span class="step">2</span>제목 고르기 · {e(T.get("keyword", ""))}</h2>'
                      f'<div class="muted">마음에 드는 제목을 누르면 그 제목으로 <b>글·썸네일·본문 그림·쇼츠 대본</b>을 만들어요 (약 5~10분). {e(T.get("made", ""))} 기준'
                      f'{" · " + e(T.get("person")) if T.get("person") else ""}</div>{"".join(btns)}'
                      f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(desk.issue_link("경제제목새로", T.get("keyword", ""), "마음에 드는 제목이 없어요. 다시 취재해서 새로 뽑아 주세요."), quote=True)}">🔄 마음에 드는 게 없어요 · 다시 조사해서 새로 뽑기</a>'
                      f'<details><summary class="muted">취재 메모 보기</summary><pre style="white-space:pre-wrap;font-size:13px">'
                      f'{e((t.parent / "research.md").read_text(encoding="utf-8")[:4000]) if (t.parent / "research.md").exists() else ""}</pre></details></div>')
    return kw_html + "".join(topics)


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
    pct = min(100, total * 100 // 50000)
    cost = (f'<div class="card"><h2>💰 이번 달 AI 비용</h2><p style="font-size:26px;margin:4px 0"><b>{total:,}원</b> '
            f'<span class="muted">/ 상한 50,000원</span></p>'
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
    pub = (f'<div class="card"><h2>📝 발행</h2><p style="font-size:22px;margin:4px 0">오늘 <b>{today_n}</b> / 3편 · '
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


def load() -> list[dict]:
    out = []
    for f in sorted((x for x in POSTS.iterdir() if x.is_dir()), reverse=True) if POSTS.exists() else []:
        p = desk.parse(f)
        if p:
            p["short"] = read_short(f)
            out.append(p)
    return out


def build(out: Path) -> list[dict]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    posts = load()
    for p in posts:
        d = out / "p" / desk.slug(p["folder"])
        d.mkdir(parents=True)
        for x in p["images"]:
            src = POSTS / p["folder"] / x["file"]
            if src.exists():
                shutil.copy(src, d / x["file"])
        if p.get("short"):
            shutil.copy(POSTS / p["folder"] / "short.mp4", d / "short.mp4")
        (d / "index.html").write_text(page(p), encoding="utf-8")
    (out / "index.html").write_text(index(posts), encoding="utf-8")
    for s in (180, 192, 512):
        shutil.copy(BRAND / f"eok-icon-{s}.png", out / f"icon-{s}.png")
    (out / "manifest.webmanifest").write_text(json.dumps({
        "name": f"{NAME} 발행 도우미", "short_name": "억선생", "start_url": "./", "display": "standalone",
        "background_color": "#f3ebdd", "theme_color": "#c81e28",
        "icons": [{"src": f"icon-{s}.png", "sizes": f"{s}x{s}", "type": "image/png"} for s in (192, 512)]},
        ensure_ascii=False), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8")
    return posts


def mark(title: str) -> str | None:
    """'[경제발행완료] <글>' → econ/posts/<글>/status.yaml. 처리한 글 이름 (형식이 다르거나 없는 글이면 None)."""
    m = MARK.match(title.strip())
    if not m or not (POSTS / m.group(1) / "post.md").exists():
        return None
    f = POSTS / m.group(1) / "status.yaml"
    st = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    st.update(status="used", at=datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
    f.write_text(yaml.safe_dump(st, allow_unicode=True), encoding="utf-8")
    return m.group(1)


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
