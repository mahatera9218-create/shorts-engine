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
from datetime import datetime
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
nav.tabs{display:flex;gap:6px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}
nav.tabs a{flex:1;text-align:center;padding:12px 4px;border-radius:12px;border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:700}
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
    "econ": ("아래 {n}장의 블로그 사진을 만들어 주세요. 반드시 번호 순서대로 한 장씩 따로따로 만들어 주세요(여러 장면을 한 장에 합치지 말 것, "
             "중간에 멈추면 이어서 계속). 공통: 실제 뉴스 현장 사진처럼 사실적인 사진, 자연광, 또렷한 초점. "
             "회사가 나오면 그 회사의 실제 건물과 진짜 로고·회사 이름 간판이 정확히 보이게. 그 밖의 글자·숫자·워터마크·차트는 넣지 말 것. "
             "실존 인물의 얼굴이 알아보이게 그리지 말 것(뒷모습·손·멀리 있는 사람은 괜찮음)."),
    "fashion": ("아래 {n}장의 패션 블로그 사진을 만들어 주세요. 반드시 번호 순서대로 한 장씩 따로따로 만들어 주세요(여러 장면을 한 장에 합치지 말 것, "
                "중간에 멈추면 이어서 계속). 공통: 고급 패션 잡지 정물 사진, 부드러운 자연광, 크림색 리넨·따뜻한 돌 위, 조용한 럭셔리 분위기, "
                "원단·니트·가죽·금속 장식의 질감이 아주 선명하게, 실제 색감. 제품만(사람·손·얼굴 없음), 브랜드 로고·글자·워터마크 없음."),
}


def all_prompt(items: list[dict]) -> str:
    """이 글 사진 전부를 한 번에 요청하는 프롬프트 하나 (대표 지시 2026-10-06: 구분 없이 '사진 프롬프트' 하나로)."""
    draw = [it for it in items if not it.get("person") and it.get("desc")]
    find = [it for it in items if it.get("person")]
    lines = [ALL_HEAD.get(BID, ALL_HEAD["econ"]).format(n=len(draw)), ""]
    for it in draw:
        shape = "정사각형 1:1" if it.get("size") == "1024x1024" else "가로 3:2"
        brand = f" — {it['brand']} 실제 건물, 진짜 로고·간판" if it.get("brand") else ""
        hook = (" — 썸네일이라 자극적으로: 홈피드에서 손이 멈추게 극적인 조명·강한 명암·높은 채도·대상을 화면 가득"
                if it["n"] == 1 and BID == "econ" else "")  # 경제 썸네일은 자극적으로 (대표 지시 2026-10-06)
        lines.append(f"{it['n']}번 ({shape}, {it['label']}{brand}{hook}): {it['desc']}")
    if find:  # 실제 인물 사진은 그리지 않는다 — 번호만 비워 둔다
        lines += ["", "※ 다음 번호는 그리지 마세요(실제 사진으로 넣을 자리): "
                  + ", ".join(f"{it['n']}번 {it.get('find') or it['label']}" for it in find)]
    return "\n".join(lines)


def prompts_card(p: dict) -> str:
    """사진 프롬프트: 복사해서 ChatGPT·제미나이에 붙여넣으면 이 글 사진이 번호 순서대로 따로 나온다."""
    e = html.escape
    f = POSTS / p["folder"] / "prompts.json"
    if not f.exists():
        return ""
    items = json.loads(f.read_text(encoding="utf-8"))
    text = all_prompt(items)
    # 인물 사진 자리: 대표가 직접 실제 사진을 넣는다 (대표 결정 2026-10-06, 출처 표기). 찾을 검색어 + 출처 줄
    people = "".join(
        f'<div style="padding:6px 0;border-top:1px solid var(--line)"><b>{it["n"]}번</b> {e(it["label"])} · '
        f'<a href="https://search.naver.com/search.naver?where=image&query={e(urllib.parse.quote(it.get("find") or it["label"]), quote=True)}" '
        f'target="_blank" rel="noopener">사진 찾기: {e(it.get("find") or it["label"])}</a></div>'
        for it in items if it.get("person"))
    people = (f'<div style="margin-top:10px"><b>인물 사진 자리 (직접 넣기)</b>{people}'
              '<div class="muted" style="margin-top:6px">사진 아래에 출처를 꼭 적어 주세요. 예) 사진 출처: OOO 인스타그램 / OO일보</div></div>') if people else ""
    return (f'<div class="card" style="border:2px solid var(--accent)"><h2>사진 프롬프트</h2>'
            f'<button onclick="copyText(this,{e(json.dumps(text), quote=True)})">📋 사진 프롬프트 복사</button>'
            # 안쪽 스크롤 상자(overflow:auto)는 아이폰에서 아래 입력칸 키보드를 막는 일이 있어 접기 방식으로 (2026-10-06)
            f'<details><summary class="muted">프롬프트 내용 보기</summary><div style="font-size:13px;white-space:pre-wrap;word-break:break-word;'
            f'background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-top:8px">{e(text)}</div></details>{people}</div>')


def page(p: dict) -> str:
    e = html.escape
    p = {**p, "images": [x for x in p["images"] if x["file"] != "-"]}  # '-' = 대표가 직접 넣을 자리
    best = next((t for t in p["titles"] if t["best"]), p["titles"][0] if p["titles"] else {"text": p["folder"], "type": ""})
    status = ('<span class="badge ok">✅ 발행 가능</span>' if p["ok"] else
              '<span class="badge warn">⚠️ 확인 필요 — 발행하지 말고 Claude에게 알려주세요</span>')
    probs = "".join(f"<li>{e(x)}</li>" for x in p["problems"])
    rest = "".join(f'<button class="ghost" onclick="setEd(\'title\',{e(json.dumps(t["text"]), quote=True)})">{e(t["text"])}'
                   f' <span class="muted">· {e(t["type"])} · 이 제목으로 바꾸기</span></button>' for t in p["titles"] if t is not best)
    body = "".join(
        f'<textarea class="ed" data-k="b{i}" rows="3">{e(b["text"])}</textarea>' if "text" in b else
        (f'<div class="ph"><div class="card muted" style="text-align:center;padding:24px">📷 사진 {b["n"]} · 직접 넣을 자리<br>{e(b["label"])}</div></div>'
         if b["img"] == "-" else
         f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy"><small>📷 사진 {b["n"]} · {e(b["label"])}</small></div>')
        for i, b in enumerate(p["blocks"]) if "text" in b or "img" in b)
    each = "".join(f'<div class="ph"><img src="{e(x["file"])}" alt="사진 {x["n"]}" loading="lazy"><small>📷 사진 {x["n"]} · {e(x["label"])}'
                   f'{" · 대표이미지로 지정" if x["n"] == 1 else ""} (길게 눌러 저장)</small></div>' for x in p["images"])
    tags = " ".join("#" + t for t in p["tags"])
    chips = "".join(f'<button class="ghost chip" onclick="copyText(this,{e(json.dumps(t), quote=True)})">{e(t)}</button>' for t in p["tags"])
    thumb = next((x["file"] for x in p["images"] if x["n"] == 1), "")
    data = json.dumps({"blocks": p["blocks"], "images": p["images"], "folder": p["folder"], "repo": desk.REPO,
                       "editTag": f"[{LABEL}수정]"},
                      ensure_ascii=False).replace("</", "<\\/")
    used = p.get("status", {}).get("status") == "used"
    done = desk.issue_link(f"{LABEL}발행완료", p["folder"], "블로그 발행을 마쳤어요.")
    return head(best["text"], "../../") + f"""
<a href="../../" class="muted">← 글 목록</a>
<h1>{e(best["text"])}</h1><div class="muted">{e(p["date"])} · 카테고리 {e(p["category"])}</div>
<p>{status}</p>{f"<ul>{probs}</ul>" if probs else ""}
{'<div class="card" style="border-color:var(--accent)"><b>⚠️ 이미 발행한 글이에요</b><div class="muted">같은 글을 두 번 올리지 마세요.</div></div>' if used else ''}
<div class="cols"><div>
{prompts_card(p)}
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
<details class="card" ontoggle="if(this.open)document.getElementById('pv').innerHTML=bodyHtml()"><summary><b>글 미리보기 (굵게·밑줄 적용된 모양)</b></summary><div id="pv" style="line-height:1.8"></div></details>
<div class="card body" id="draft"><h2>✏️ 초안 (눌러서 고치기)</h2>
<div class="muted">**굵게** · __밑줄__ · *기울임* 표시는 본문 복사 때 서식으로 바뀌어요.</div>
<div class="muted">고친 문단은 주황 테두리로 보이고, 이 휴대폰에 저장돼 위 <b>본문 복사</b>에 반영돼요.</div>{body}
<button onclick="saveEdits(this)">💾 고친 내용 저장 (다음 글이 배워요)</button>
<div class="muted">제목·문단을 고쳤다면 눌러 주세요. GitHub 화면에서 초록 <b>Create</b>만 누르면, 고친 방향을 모아 다음 글부터 그렇게 써요.</div></div>
</div></div>
<div class="card" id="each"><h2>사진 하나씩 저장</h2>{each}</div>
<details class="card"><summary>출처</summary><pre style="white-space:pre-wrap">{e(p["sources"])}</pre></details>
</main><script>const POST={data};{desk.JS}</script></body></html>"""


def blog_section(b: dict, posts: list[dict]) -> str:
    """블로그 한 개의 탭: ① 키워드 ② 제목 ③ 올릴 글."""
    e = html.escape
    use(b)
    live = [p for p in posts if p.get("status", {}).get("status") not in ("used", "rejected")]
    used = [p for p in posts if p.get("status", {}).get("status") == "used"]

    def row(p, muted=False):
        t = next((x["text"] for x in p["titles"] if x["best"]), p["folder"])
        mark = "발행함" if muted else ("" if p["ok"] else "확인 필요 · ")
        style = "text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" + (";opacity:.55" if muted else "")
        return f'<a class="btn" style="{style}" href="p/{b["id"]}-{desk.slug(p["folder"])}/">{mark}{e(p["date"])} · {e(t)}</a>'

    return f"""<section class="tab" id="{b['id']}" hidden><p class="muted" style="margin:4px 0 0">{e(b['name'])}</p><div class="cols"><div>
{flow_html()}
</div><div class="stick">
<details class="card fold" data-k="f3-{b['id']}" open><summary><h2><span><span class="step">3</span>올릴 글</span></h2></summary>{"".join(row(p) for p in sorted(live, key=lambda p: p["folder"], reverse=True)) or '<p class="muted">올릴 글이 아직 없어요.</p>'}
{f'<h2 style="margin-top:28px">발행한 글</h2>' + "".join(row(p, True) for p in used[:10]) if used else ''}</details>
</div></div></section>"""


def index(by_blog: dict[str, list[dict]]) -> str:
    from .blogs import all_blogs
    blogs = all_blogs()
    now = datetime.now(KST).strftime("%m월 %d일 %H:%M")
    tabs = "".join(f'<a href="#{bid}" data-t="{bid}">{html.escape(b["label"])}</a>' for bid, b in blogs.items())
    secs = "".join(blog_section(b, by_blog.get(bid, [])) for bid, b in blogs.items())
    first = next(iter(blogs))
    return head(f"{NAME} 발행 도우미") + f"""
<header class="brand"><img src="icon-180.png" alt=""><div><h1>발행 도우미</h1><p class="muted">{" · ".join(html.escape(b["label"]) for b in blogs.values())} · {now} 업데이트</p></div></header>
<nav class="tabs">{tabs}<a href="#stats" data-t="stats">성과</a></nav>
{secs}
<section class="tab" id="stats" hidden>{compare_html(blogs, by_blog)}</section>
<div class="card muted" style="margin-top:28px">홈 화면에 두기: 이 화면에서 브라우저 메뉴(⋮ 또는 공유 ↑) → <b>홈 화면에 추가</b>.</div>
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


def flow_html() -> str:
    """① 오늘의 키워드 → ② 제목 고르기 (대표 결정 2026-10-05: 대표가 키워드·제목을 고른 뒤에 전체 제작)."""
    e = html.escape
    today = datetime.now(KST).strftime("%Y-%m-%d")
    day = FLOW / today
    kw = (yaml.safe_load((day / "keywords.yaml").read_text(encoding="utf-8")) or {}) if (day / "keywords.yaml").exists() else {}
    from .blogs import get as _bget
    _kc = ROOT / _bget(BID).get("keywords", "config/econ_keywords.yaml")
    _kcfg = (yaml.safe_load(_kc.read_text(encoding="utf-8")) or {}) if _kc.exists() else {}
    W = {"출처": 40, "뉴스": 25, "검색": 35, "최신": 0, **_kcfg.get("weights", {})}
    MIN = _kcfg.get("min_score", MIN_SCORE)  # 블로그마다 (패션은 30, 2026-10-06)
    rows, hidden = [], 0
    for it in kw.get("items", [])[:20]:
        mine = it.get("src") in ("대표", "캡처") or any(k in (it.get("sources") or {}) for k in ("대표", "캡처"))
        if "score" in it and it["score"] < MIN and not mine:  # 50점 미만은 안 보여 줌 (대표 지시 2026-10-05), 대표가 넣은 건 예외
            hidden += 1
            continue
        link = desk.issue_link(f"{LABEL}키워드", it["kw"], "이 키워드로 제목 후보를 만들어 주세요.")
        src = dict(it.get("sources") or {})
        bl = it.get("bloggers") or []
        main_name = REF_NAMES.get(REF_MAIN, "")
        src.pop(REF_MAIN, None)
        src.pop("블로거", None)
        who = " · ".join([b + ("(최우선)" if b == main_name else "") for b in sorted(bl, key=lambda b: b != main_name)]
                         + [f"{k}{'×' + str(v) if v > 1 else ''}" for k, v in src.items()]) or it.get("src", "")
        pt = it.get("parts") or {}
        sc = f' <span class="seal">{it["score"]}점</span>' if "score" in it else ""
        st = it.get("stats") or {}
        bar = (f'<span class="muted">{"최신 " + str(pt.get("최신", 0)) + "/" + str(W["최신"]) + " · " if W.get("최신") else ""}'
               f'출처 {pt.get("출처", 0)}/{W["출처"]} · 뉴스 {pt.get("뉴스", 0)}/{W["뉴스"]} · 검색 {pt.get("검색", 0)}/{W["검색"]}'
               f'{" · 월검색 " + format(st["월검색"], ",") if st.get("월검색") else ""}</span><br>') if pt else ""
        rows.append(f'<div style="display:flex;gap:8px;align-items:stretch"><label style="display:flex;align-items:center;padding:0 4px">'
                    f'<input type="checkbox" class="kwpick-{BID}" value="{e(it["kw"], quote=True)}" onchange="pick_{BID}()" style="width:22px;height:22px"></label>'
                    f'<a class="btn" style="flex:1;text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                    f'href="{e(link, quote=True)}"><b>{e(it["kw"])}</b>'
                    f'{sc}'
                    f'<br><span class="muted">📌 {e(who)}</span><br>{bar}<span class="muted">{e(it.get("why", ""))}</span></a></div>')
    add_js = (f"function addKw_{BID}(){{const v=document.getElementById('kwin-{BID}').value.trim();if(!v){{alert('키워드를 적어 주세요');return}}"
              f"location.href='https://github.com/{desk.REPO}/issues/new?title='+encodeURIComponent('[{LABEL}키워드추가] {today}')"
              "+'&body='+encodeURIComponent(v+String.fromCharCode(10,10)+'아래 초록색 Create만 누르면 됩니다.')}")
    # 여러 개 골라 제목 한 번에 (대표 지시 2026-10-06): 체크한 키워드를 ' / '로 이어 이슈 하나로 → 차례로 제목 후보
    add_js += (f"function pick_{BID}(){{const n=document.querySelectorAll('.kwpick-{BID}:checked').length;"
               f"const b=document.getElementById('kwmulti-{BID}');b.textContent='선택한 키워드 '+n+'개 제목 한 번에 뽑기';b.style.opacity=n?1:.5}}"
               f"function multi_{BID}(){{const v=[...document.querySelectorAll('.kwpick-{BID}:checked')].map(x=>x.value);"
               f"if(!v.length){{alert('왼쪽 네모를 눌러 키워드를 골라 주세요');return}}if(v.length>5){{alert('한 번에 5개까지예요');return}}"
               f"location.href='https://github.com/{desk.REPO}/issues/new?title='+encodeURIComponent('[{LABEL}키워드] '+v.join(' / '))"
               "+'&body='+encodeURIComponent('이 키워드들로 제목 후보를 차례로 만들어 주세요.'+String.fromCharCode(10,10)+'아래 초록색 Create만 누르면 됩니다.')}")
    multi_btn = (f'<button id="kwmulti-{BID}" onclick="multi_{BID}()" style="opacity:.5;position:sticky;bottom:10px;z-index:5;box-shadow:0 4px 14px rgba(0,0,0,.18)">선택한 키워드 0개 제목 한 번에 뽑기</button>'
                 '<div class="muted">왼쪽 네모로 여러 개(최대 5개) 고르면 한 번에 제목 후보를 만들어요. 1개에 약 3~5분, 비용 약 150원.</div>') if rows else ""
    refresh = desk.issue_link(f"{LABEL}키워드새로", today, "여러 출처에서 키워드를 모아 점수를 매겨 주세요.")
    kw_html = f"""<details class="card fold" data-k="f1-{BID}" open style="border:2px solid var(--accent)"><summary><h2><span><span class="step">1</span>오늘의 키워드 고르기</span></h2></summary>
<div class="muted">점수순이에요(100점 = {"최신(6시간 기사) " + str(W["최신"]) + " + " if W.get("최신") else ""}출처 겹침 {W["출처"]} + 네이버 뉴스량 {W["뉴스"]} + 검색량 {W["검색"]}, {MIN}점 이상만{f" · {hidden}개 숨김" if hidden else ""}). 누르면 그 키워드로 <b>제목 후보</b>를 만들어요 (약 3~5분). {e(kw.get("updated", ""))} 기준</div>
{''.join(rows)}{multi_btn}{'' if rows else '<p class="muted">아직 없어요. 아래 <b>🔄 키워드 모으기</b>를 누르면 여러 출처에서 모아 점수를 매겨요(약 3분).</p>'}
<textarea id="kwin-{BID}" rows="3" style="width:100%;min-height:84px;font:inherit;line-height:1.6;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0;background:var(--card);color:var(--ink);resize:vertical" placeholder="{'어드바이저·뉴스 랭킹·트렌드에서 찾은 키워드' if BID == 'econ' else '눈에 띈 연예인 + 아이템 (예: 윤아 코트)'} (한 줄에 하나)"></textarea>
<button onclick="addKw_{BID}()">➕ 내 키워드 넣기</button>
{inbox_buttons(today) if BID == 'econ' else ''}
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(refresh, quote=True)}">🔄 키워드 모으기</a>
<script>{add_js}</script></details>"""
    topics = []
    for t in sorted(day.glob("*/titles.yaml")) if day.exists() else []:
        T = yaml.safe_load(t.read_text(encoding="utf-8")) or {}
        chosen = t.parent / "chosen.yaml"
        if chosen.exists():
            continue  # 제작 끝난 주제는 ②에 안 남김 — ③ 올릴 글에 있음 (대표 지적 2026-10-06)
        def btn(i: int, it: dict, label: str) -> str:
            flags = " · ⚠️ " + ", ".join(it["flags"]) if it.get("flags") else ""
            link = desk.issue_link(f"{LABEL}제목", f"{t.parent.name} {i}", "이 제목으로 글·사진을 만들어 주세요.")
            return (f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" '
                    f'href="{e(link, quote=True)}">{label}{e(it["title"])}<br><span class="muted">{e(it.get("type", ""))} · '
                    f'{it.get("chars", "")}자{" · 유형 BEST" if it.get("best") else ""}{e(flags)}</span></a>')

        items = T.get("items", [])
        if T.get("groups"):  # 최종 추천을 위에, 유형·그룹별 후보는 접어서 (쿠니네 6유형×5, 연예·패션 3그룹×5)
            btns = [btn(i, it, f"{it.get('rank')}. {'(추천) ' if it.get('rank') == 1 else ''}")
                    for i, it in enumerate(items, 1) if it.get("rank")]
            for g in T.get("groups", []):
                inner = "".join(btn(j + 1, items[j], "BEST · " if j == g.get("best") else "· ") for j in g["idx"] if j < len(items))
                ver = g["type"].endswith("식")  # 제목 고수 방식 묶음은 비교해 보려고 펼쳐 둠 (2026-10-06)
                btns.append(f'<details{" open" if ver else ""}><summary class="muted">{e(g["type"][:-1]) + " 방식 " if ver else e(g["type"]) + " "}{len(g["idx"])}개 보기</summary>{inner}</details>')
        else:
            btns = [btn(i, it, f"{i}. ") for i, it in enumerate(items, 1)]
        topics.append(f'<details class="card fold" data-k="f2-{e(t.parent.name)}" open style="border:2px solid var(--accent)"><summary><h2><span><span class="step">2</span>제목 고르기 · {e(T.get("keyword", ""))}</span></h2></summary>'
                      f'<div class="muted">마음에 드는 제목을 누르면 그 제목으로 <b>글·썸네일·본문 사진</b>을 만들어요 (약 5~10분). {e(T.get("made", ""))} 기준'
                      f'{" · " + e(T.get("person")) if T.get("person") else ""}{" · 🔥 강하게 차례(3편에 1편)" if T.get("strong") else ""}</div>{"".join(btns)}'
                      f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(desk.issue_link(f"{LABEL}제목새로", T.get("keyword", ""), "마음에 드는 제목이 없어요. 다시 취재해서 새로 뽑아 주세요."), quote=True)}">🔄 마음에 드는 게 없어요 · 다시 조사해서 새로 뽑기</a>'
                      f'<details><summary class="muted">취재 메모 보기</summary><pre style="white-space:pre-wrap;font-size:13px">'
                      f'{e((t.parent / "research.md").read_text(encoding="utf-8")[:4000]) if (t.parent / "research.md").exists() else ""}</pre></details></details>')
    if topics:  # 제목 고수 참고를 마지막 ② 칸 안에 접어서 (대표 지시 2026-10-05)
        topics[-1] = topics[-1][:-len("</details>")] + masters_html() + "</details>"
    if not topics:  # 제목이 아직 없어도 ② 칸은 늘 보이게 (대표 지적 2026-10-05: 1·3만 보여 헷갈림)
        topics.append(f'<details class="card fold" data-k="f2-empty-{BID}" open><summary><h2><span><span class="step">2</span>제목 고르기</span></h2></summary>'
                      '<p class="muted">① 에서 키워드를 하나 누르면 3~5분 뒤 여기에 제목 후보가 올라와요.</p>' + masters_html() + '</details>')
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
    head_ = (f'<div class="card"><h2>이번 달 AI 비용 (모든 블로그 합계, {int(COST_FROM[5:7])}월 {int(COST_FROM[8:])}일부터)</h2><p style="font-size:26px;margin:4px 0"><b>{total:,}원</b> '
             f'<span class="muted">/ 상한 {F_CAP:,}원</span></p><div style="background:var(--line);border-radius:8px;height:12px">'
             f'<div style="width:{pct}%;height:12px;border-radius:8px;background:var(--accent)"></div></div>'
             '<div class="muted">토큰으로 어림한 값이라 AI 회사 청구액과 조금 다를 수 있어요.</div></div>')
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
    return head_ + table + note + grid


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
