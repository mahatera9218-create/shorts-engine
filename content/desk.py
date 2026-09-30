"""발행 도우미 페이지: posts/의 발행 패키지를 태블릿에서 버튼 몇 번으로 옮길 수 있는 정적 사이트로 만든다.

- 글마다 한 페이지: 제목 후보(누르면 복사), 썸네일, [본문 복사], [사진 한 번에 저장], 태그 복사,
  클립(세로 영상 저장·설명 복사), [발행 완료 표시]·[다시 뽑기] (GitHub 이슈 → content/mark.py)
- 목록: 발행할 글(오래된 것부터) → 발행한 글. 버린 글은 숨김.
- 검색엔진 수집 금지 (발행 전 글이 먼저 수집되면 우리 글이 중복 문서가 될 수 있다): meta noindex + robots.txt + X-Robots-Tag
- Cloudflare Pages에 올린다 (.github/workflows/desk.yml)

사용법: python -m content.desk [출력 폴더, 기본 site]
"""
from __future__ import annotations

import hashlib
import html
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import re
import shutil
import urllib.parse
import sys
from pathlib import Path

import yaml

from market.common import ROOT
from .mark import status as read_status

TAG_OK = re.compile(r"^[0-9A-Za-z가-힣_]+$")  # 네이버 블로그 태그: 한글·영문·숫자·_ 만 (특수문자면 거절됨)


def clean_tags(tags: list[str]) -> list[str]:
    """띄어쓰기·가운뎃점은 떼고, 그래도 특수문자(. % - 등)가 남는 태그는 뺀다. 최대 10개."""
    out = []
    for x in tags:
        x = re.sub(r"[\s·#]", "", x)
        if TAG_OK.match(x) and x not in out:
            out.append(x)
    return out[:10]

POSTS = ROOT / "posts"
REPO = os.environ.get("GITHUB_REPOSITORY", "mahatera9218-create/shorts-engine")
IMG_LINE = re.compile(r"^\[이미지 (\d+)_([^:\]]*):\s*([^\]]+)\]$")
TITLE_LINE = re.compile(r"^\d+\.\s+(★\s+)?(.+?)\s+—\s+(\S+)$")


def parse(folder: Path) -> dict | None:
    md = folder / "post.md"
    if not md.exists():
        return None
    t = md.read_text(encoding="utf-8")
    head = t.split("## 제목")[0]
    status_ok = "⚠️" not in head
    problems = re.findall(r"^- (.+)$", head.split("**남은 문제:**")[1], re.M) if "**남은 문제:**" in head else []
    tsec = t.split("## 제목", 1)[1].split("\n## ", 1)[0] if "## 제목" in t else ""
    titles = [{"text": m.group(2), "type": m.group(3), "best": bool(m.group(1))}
              for m in (TITLE_LINE.match(l.strip()) for l in tsec.splitlines()) if m]
    tags = re.search(r"^- 태그: (.+)$", t, re.M)
    cat = re.search(r"^- 카테고리: \*\*(.+?)\*\*", t, re.M)
    body_file = folder / "body.txt"
    body = body_file.read_text(encoding="utf-8") if body_file.exists() else \
        t.split("## 본문", 1)[1].split("\n", 1)[1].split("\n## 출처", 1)[0] if "## 본문" in t else ""
    blocks, images = [], []
    for para in [p.strip() for p in body.strip().split("\n\n") if p.strip()]:
        m = IMG_LINE.match(para)
        if m:
            images.append({"n": int(m.group(1)), "label": m.group(2), "file": m.group(3).strip()})
            blocks.append({"img": m.group(3).strip(), "n": int(m.group(1)), "label": m.group(2)})
        else:
            blocks.append({"text": para})
    sources = t.split("## 출처", 1)[1].split("\n## ", 1)[0].strip() if "## 출처" in t else ""
    return {"folder": folder.name, "date": folder.name[:10], "ok": status_ok, "problems": problems,
            "titles": titles, "tags": clean_tags(tags.group(1).split(",")) if tags else [],
            "category": cat.group(1) if cat else "", "blocks": blocks, "images": images, "sources": sources,
            "clip": (folder / "clip.mp4").exists(), "status": read_status(folder),
            "review": (re.search(r"## 편집장 검토[^\n]*\n\n(.+)", t) or [None, ""])[1].strip(),
            "clip_text": (folder / "clip.txt").read_text(encoding="utf-8") if (folder / "clip.txt").exists() else ""}


def slug(name: str) -> str:
    """주소에 한글을 넣지 않는다 (복사·공유가 깨지지 않게)."""
    return name[:10] + "-" + hashlib.sha1(name.encode()).hexdigest()[:6]


CSS = """
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1d20;--soft:#6b6a66;--line:#e2ddd3;--accent:#d93636;--ok:#1f8a4c;--warn:#b86e00;--btn:#1d1d20;--btnink:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1f1f23;--ink:#f0efeb;--soft:#a3a19b;--line:#34343a;--btn:#f0efeb;--btnink:#141416}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 16px 80px}h1{font-size:22px;margin:8px 0 4px}h2{font-size:18px;margin:0 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}
.muted{color:var(--soft);font-size:14px}.badge{display:inline-block;padding:2px 10px;border-radius:99px;font-size:14px;font-weight:700;color:#fff}
.ok{background:var(--ok)}.warn{background:var(--warn)}
button,.btn{display:block;width:100%;min-height:52px;margin:8px 0;padding:12px 14px;border:0;border-radius:12px;background:var(--btn);color:var(--btnink);font-size:17px;font-weight:700;text-align:center;text-decoration:none;cursor:pointer}
button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line);font-weight:600;text-align:left}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.chips button.chip{width:auto;min-height:44px;margin:0;padding:8px 12px}
button.done{background:var(--ok)!important;color:#fff!important}
img{max-width:100%;border-radius:10px;display:block}.thumb{max-width:360px}
.body p{margin:0 0 14px;white-space:pre-wrap}.body .ph{margin:10px 0 16px}.ph small{display:block;color:var(--soft);margin-top:4px}
.step{display:inline-block;width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;text-align:center;font-weight:800;margin-right:6px;line-height:26px}
a{color:inherit}ol{padding-left:20px}li{margin:6px 0}
"""

JS = """
function flash(b,t){const o=b.dataset.o||b.textContent;b.dataset.o=o;b.textContent=t;b.classList.add('done');setTimeout(()=>{b.textContent=o;b.classList.remove('done')},1600)}
async function copyText(b,t){try{await navigator.clipboard.writeText(t);flash(b,'복사됨 ✓')}catch(e){prompt('길게 눌러 복사하세요',t)}}
function bodyText(){return POST.blocks.map(x=>x.text?x.text:'📷 사진 '+x.n+' ('+x.label+')').join('\\n\\n')}
async function copyBody(b){copyText(b,bodyText())}
async function saveClip(b,name){
  name=name||'clip.mp4';
  try{
    const r=await fetch(name);const bl=await r.blob();const files=[new File([bl],name,{type:'video/mp4'})];
    if(navigator.canShare&&navigator.canShare({files})){await navigator.share({files});flash(b,'완료 ✓');return}
  }catch(e){if(e.name==='AbortError')return}
  alert('영상을 길게 누르거나, 영상 오른쪽 아래 ⋮ 메뉴에서 저장해 주세요.')
}
async function saveAll(b){
  try{
    const files=await Promise.all(POST.images.map(async x=>{const r=await fetch(x.file);const bl=await r.blob();return new File([bl],String(x.n).padStart(2,'0')+'_'+x.file,{type:bl.type||'image/png'})}));
    if(navigator.canShare&&navigator.canShare({files})){await navigator.share({files});flash(b,'완료 ✓');return}
  }catch(e){if(e.name==='AbortError')return}
  document.getElementById('each').scrollIntoView({behavior:'smooth'});alert('한 번에 저장이 안 되는 브라우저예요. 아래 사진을 하나씩 길게 눌러 저장해 주세요.')
}
"""


def issue_link(kind: str, folder: str, note: str) -> str:
    """제목이 채워진 GitHub 이슈 작성 화면 (대표가 Create만 누르면 워크플로가 처리)."""
    q = urllib.parse.urlencode({"title": f"[{kind}] {folder}",
                                "body": f"{note}\n\n아래 초록색 **Create** 버튼만 누르면 됩니다. 이 글은 자동으로 닫혀요."})
    return f"https://github.com/{REPO}/issues/new?{q}"


def page(p: dict) -> str:
    e = html.escape
    best = next((t for t in p["titles"] if t["best"]), p["titles"][0] if p["titles"] else None)
    status = ('<span class="badge ok">✅ 발행 가능</span>' if p["ok"] else
              '<span class="badge warn">⚠️ 확인 필요 — 발행하지 말고 Claude에게 알려주세요</span>')
    probs = "".join(f"<li>{e(x)}</li>" for x in p["problems"])
    def tbtn(t, cls="ghost"):
        return (f'<button class="{cls}" onclick="copyText(this,{e(json.dumps(t["text"]), quote=True)})">'
                f'{e(t["text"])} <span class="muted">· {e(t["type"])} · {len(t["text"])}자</span></button>')

    rest = "".join(tbtn(t) for t in p["titles"] if t is not best)
    titles = (tbtn(best, "ghost") if best else "") + (
        f'<details><summary class="muted">다른 제목 {len(p["titles"]) - 1}개 (썸네일과 짝이 아니라 예비)</summary>{rest}</details>'
        if rest else "")
    body = "".join(
        f'<p>{e(b["text"])}</p>' if "text" in b else
        f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy"><small>📷 사진 {b["n"]} · {e(b["label"])}</small></div>'
        for b in p["blocks"])
    each = "".join(f'<div class="ph"><img src="{e(x["file"])}" alt="사진 {x["n"]}" loading="lazy"><small>📷 사진 {x["n"]} · {e(x["label"])}'
                   f'{" · 대표이미지로 지정" if x["n"] == 1 else ""} (길게 눌러 저장)</small></div>' for x in p["images"])
    tags = " ".join("#" + t for t in p["tags"])
    chips = "".join(f'<button class="ghost chip" onclick="copyText(this,{e(json.dumps(t), quote=True)})">{e(t)}</button>' for t in p["tags"])
    data = json.dumps({"blocks": p["blocks"], "images": p["images"]}, ensure_ascii=False).replace("</", "<\\/")
    thumb = next((x["file"] for x in p["images"] if x["n"] == 1), "thumb.png")
    st = p.get("status", {})
    used = (f'<div class="card" style="border-color:var(--warn)"><b>⚠️ 이미 발행한 글이에요 ({e(st.get("at", ""))})</b>'
            '<div class="muted">같은 글을 두 번 올리지 마세요.</div>'
            + (f'<a class="btn" href="{e(st["url"], quote=True)}">네이버에 올라간 글 보기</a>' if st.get("url") else
               '<div class="muted">네이버 공개 확인 전 (매일 아침 자동 확인)</div>')
            + '</div>') if st.get("status") == "used" else ""
    done_btn = e(issue_link("발행완료", p["folder"], "블로그·클립 발행을 마쳤어요."), quote=True)
    again_btn = e(issue_link("다시뽑기", p["folder"], "이 글은 버리고 다른 선수·테마로 새로 써 주세요."), quote=True)
    clip = "" if not p.get("clip") else f"""<div class="card"><h2><span class="step">6</span>클립 (블로그 발행 뒤)</h2>
<video src="clip.mp4" controls playsinline preload="metadata" style="width:100%;max-width:320px;border-radius:10px;display:block"></video>
<button onclick="saveClip(this)">🎬 클립 영상 저장</button>
<button class="ghost" onclick="copyText(this,{e(json.dumps(p["clip_text"]), quote=True)})">📋 클립 설명·해시태그 복사</button>
<ol class="muted"><li>블로그 앱 아래 <b>+</b> → <b>클립 만들기</b></li><li>방금 저장한 영상 고르기</li>
<li><b>음악</b> → 추천·인기 음악 중 신나는 곡 하나 (네이버가 저작권 계약한 음원이라 안전)</li>
<li>설명 칸에 붙여넣기 → 올리기</li></ol></div>"""
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>{e(best["text"] if best else p["folder"])}</title><style>{CSS}</style></head><body><main>
<a href="../../" class="muted">← 글 목록</a>
<h1>{e(best["text"] if best else p["folder"])}</h1><div class="muted">{e(p["date"])} · 카테고리 {e(p["category"])}</div>
<p>{status}</p>{f"<ul>{probs}</ul>" if probs else ""}{used}
{f'<p class="muted">편집장 검토: {e(p["review"])}</p>' if p.get("review") else ""}
<div class="card"><h2><span class="step">1</span>사진 저장</h2>
<button onclick="saveAll(this)">📷 사진 {len(p["images"])}장 한 번에 저장</button>
<div class="muted">공유 창이 뜨면 "이미지 저장" / "사진에 저장"을 누르세요. 파일 이름 앞 번호가 넣는 순서예요.</div></div>
<div class="card"><h2><span class="step">2</span>제목 (눌러서 복사)</h2>{titles}
<div class="muted">썸네일과 짝으로 만든 제목이에요. 고르지 말고 이걸 그대로 쓰세요.</div></div>
<div class="card"><h2><span class="step">3</span>대표 사진 (썸네일)</h2><img class="thumb" src="{e(thumb)}" alt="썸네일">
<div class="muted">본문에 넣은 뒤 이 사진을 대표이미지로 지정하세요.</div></div>
<div class="card"><h2><span class="step">4</span>본문</h2>
<button onclick="copyBody(this)">📋 본문 복사 (사진 자리 📷 표시)</button>
<div class="muted">네이버 앱에 붙여넣고, "📷 사진 N" 줄을 지운 자리에 N번 사진을 넣으세요.</div>
</div>
<div class="card"><h2><span class="step">5</span>태그</h2><button class="ghost" onclick="copyText(this,{e(json.dumps(tags), quote=True)})">📋 한 번에 복사: {e(tags)}</button>
<div class="muted">한 번에 붙여넣기가 안 되면 아래 태그를 하나씩 눌러 복사 → 태그 칸에 붙여넣기 → 완료(엔터)를 반복하세요.</div>
<div class="chips">{chips}</div></div>
{clip}
<div class="card"><h2><span class="step">7</span>다 올렸으면</h2>
<a class="btn" href="{done_btn}">✅ 발행 완료 표시</a>
<div class="muted">GitHub 화면이 열리면 초록 <b>Create</b>만 누르세요. 2~3분 뒤 목록에서 "발행한 글"로 내려가요 (중복 발행 방지).</div></div>
<div class="card body"><h2>미리 읽기</h2>{body}</div>
<div class="card"><h2>🔄 이 글이 마음에 안 들면</h2>
<a class="btn" style="background:var(--card);color:var(--ink);border:1px solid var(--line)" href="{again_btn}">다른 글로 다시 뽑기</a>
<div class="muted">GitHub 화면에서 <b>Create</b>를 누르면 이 글은 목록에서 빠지고, 다른 선수·테마로 새 글을 써요 (약 5~10분).</div></div>
<div class="card" id="each"><h2>사진 하나씩 저장</h2>{each}</div>
<details class="card"><summary>출처</summary><pre style="white-space:pre-wrap">{e(p["sources"])}</pre></details>
</main><script>const POST={data};{JS}</script></body></html>"""


def index(posts: list[dict], n_shorts: int = 0) -> str:
    e = html.escape

    def row(p, muted=False):
        title = next((t["text"] for t in p["titles"] if t["best"]), p["folder"])
        mark = "☑️" if muted else ("✅" if p["ok"] else "⚠️")
        style = "text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" + (";opacity:.55" if muted else "")
        return f'<a class="btn" style="{style}" href="p/{slug(p["folder"])}/">{mark} {e(p["date"])} · {e(title)}</a>'

    live = [p for p in posts if p.get("status", {}).get("status") not in ("used", "rejected")]
    used = [p for p in posts if p.get("status", {}).get("status") == "used"]
    todo = "".join(row(p) for p in sorted(live, key=lambda p: p["folder"])[-14:])
    done = "".join(row(p, True) for p in sorted(used, key=lambda p: p["status"].get("at", ""), reverse=True)[:10])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>발행 도우미</title><style>{CSS}</style></head><body><main>
<h1>발행 도우미 · 억소리 나는 스포츠</h1>
<p class="muted">마지막 업데이트: {datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m월 %d일 %H:%M")}</p>
<p class="muted">매일 아침 6시 47분에 오늘의 후보 4편이 올라와요. 읽어 보고 <b>마음에 드는 1편만</b> 골라 블로그·클립에 올린 뒤, 글 화면 맨 아래 <b>✅ 발행 완료 표시</b>를 눌러 주세요. 고르지 않은 후보는 다음 날 아침 자동으로 지워져요.</p>
<h2>① 네이버 · 오늘의 후보 (1편 골라 블로그·클립 발행)</h2>
{todo or '<p>후보가 아직 없어요. 내일 아침 6시 47분에 올라와요.</p>'}
{f'<h2 style="margin-top:28px">발행한 글</h2>{done}' if done else ''}
<h2 style="margin-top:28px">② 유튜브 쇼츠 모음 (A·B·C 매일 3개)</h2>
<a class="btn" href="s/">🎬 쇼츠 영상 모음 열기{f" · 오늘 {n_shorts}개" if n_shorts else ""}</a>
<div class="muted">네이버 클립과 다른 영상이에요. 블로그를 먼저 올리고, 시간이 날 때 3개를 올려 주세요.</div>
<div class="card" style="margin-top:28px"><h2>필요할 때만 누르는 버튼</h2>
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(issue_link("다시그리기", "오늘후보", "글은 그대로 두고 사진·썸네일·클립만 새로 그려 주세요."), quote=True)}">🎨 사진·클립 다시 그리기</a>
<div class="muted">무료 · 5~10분. 썸네일·클립 디자인을 고친 뒤 지금 있는 후보에 바로 반영할 때.</div>
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(issue_link("새후보", "4편", "오늘 후보 4편을 새로 써 주세요."), quote=True)}">✍️ 후보 4편 새로 쓰기</a>
<div class="muted">Claude 비용 약 $2~3 · 20~30분. 오늘 후보가 다 마음에 안 들 때만. 매일 아침에는 자동으로 올라와요.</div>
<div class="muted">누르면 GitHub 화면이 열려요. 초록색 <b>Create</b>만 누르면 끝이에요.</div></div>
</main></body></html>"""


SHORTS = ROOT / "shorts"
KIND = {"A": "A · 통장형", "B": "B · 비교형", "C": "C · 한 장 반복형"}


def shorts_list() -> list[dict]:
    out = []
    for f in sorted((x for x in SHORTS.iterdir() if x.is_dir()), reverse=True) if SHORTS.exists() else []:
        m = f / "meta.txt"
        if (f / "video.mp4").exists() and m.exists():
            title, _, desc = m.read_text(encoding="utf-8").partition("\n")
            out.append({"folder": f.name, "date": f.name[:10], "kind": f.name[11:12], "title": title, "desc": desc.strip()})
    log = {x["title"]: x for x in (yaml.safe_load((SHORTS / "log.yaml").read_text(encoding="utf-8")) or [])} \
        if (SHORTS / "log.yaml").exists() else {}
    st = ROOT / "reports" / "쇼츠-성과" / "stats.yaml"
    vids = ((yaml.safe_load(st.read_text(encoding="utf-8")) or {}).get("videos", {})) if st.exists() else {}
    for s in out:
        vid = log.get(s["title"], {}).get("video_id")
        if vid and vid in vids and vids[vid]["snaps"]:
            s["views"] = vids[vid]["snaps"][max(vids[vid]["snaps"])]["views"]
        s["uploaded"] = bool(vid)
    return out


def shorts_page(items: list[dict]) -> str:
    e = html.escape
    cards = []
    for i, s in enumerate(items):
        v = f"{slug(s['folder'])}.mp4"  # 주소에 한글이 들어가지 않게
        up = (f'<span class="badge ok">✅ 올림 · 조회 {s["views"]:,}</span>' if "views" in s else '<span class="badge ok">✅ 올림</span>') \
            if s.get("uploaded") else '<span class="badge warn">아직 안 올림</span>'
        cards.append(f"""<div class="card"><h2>{e(s['date'])} · {e(KIND.get(s['kind'], s['kind']))} {up}</h2>
<video src="{e(v)}" controls playsinline preload="metadata" style="width:100%;max-width:320px;border-radius:10px;display:block"></video>
<button onclick="saveClip(this,{e(json.dumps(v), quote=True)})">🎬 영상 저장</button>
<button class="ghost" onclick="copyText(this,{e(json.dumps(s['title']), quote=True)})">📋 제목 복사: {e(s['title'])}</button>
<button class="ghost" onclick="copyText(this,{e(json.dumps(s['desc']), quote=True)})">📋 설명·해시태그 복사</button></div>""")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>쇼츠 영상 모음</title><style>{CSS}</style></head><body><main>
<a href="../" class="muted">← 발행 도우미</a>
<h1>유튜브 쇼츠 모음</h1>
<div class="card"><ol class="muted"><li><b>영상 저장</b> → 유튜브 앱 아래 <b>+</b> → <b>동영상 업로드</b> → 저장한 영상</li>
<li>편집 화면에 <b>사운드 추가</b>가 보이면 곡 하나 (유튜브 음원이라 안전)</li>
<li>세부정보 화면에서 <b>썸네일(커버) 고르기</b>가 보이면 <b>맨 앞 장면</b>으로 (안 보여도 괜찮아요: 모든 장면 위쪽에 제목이 있어요)</li>
<li><b>제목 복사</b>·<b>설명 복사</b> 붙여넣기 → <b>공개</b> → 업로드</li></ol>
<div class="muted">A·B·C를 2주 동안 번갈아 시험해요. 하루에 3개를 몰아서 올려도 되고, 시간 간격을 두면 더 좋아요. 최근 3일치만 보여요.</div></div>
{"".join(cards) or '<p>아직 쇼츠가 없어요. 매일 아침 글쓰기 뒤에 만들어져요.</p>'}
</main><script>const POST={{"blocks":[],"images":[]}};{JS}</script></body></html>"""


def build(out: Path) -> list[dict]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    posts = [p for p in (parse(f) for f in sorted(POSTS.iterdir(), reverse=True) if f.is_dir()) if p]
    for p in posts:
        d = out / "p" / slug(p["folder"])
        d.mkdir(parents=True)
        for x in p["images"]:
            src = POSTS / p["folder"] / x["file"]
            if src.exists():
                shutil.copy(src, d / x["file"])
        if p.get("clip"):
            shutil.copy(POSTS / p["folder"] / "clip.mp4", d / "clip.mp4")
        (d / "index.html").write_text(page(p), encoding="utf-8")
    items = shorts_list()
    (out / "s").mkdir()
    for s in items:
        shutil.copy(SHORTS / s["folder"] / "video.mp4", out / "s" / f"{slug(s['folder'])}.mp4")
    (out / "s" / "index.html").write_text(shorts_page(items), encoding="utf-8")
    today = max((s["date"] for s in items), default="")
    (out / "index.html").write_text(index(sorted(posts, key=lambda p: p["folder"])[-14:],
                                          sum(s["date"] == today for s in items)), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8")
    return posts


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    posts = build(out)
    print(f"발행 도우미: 글 {len(posts)}편 → {out}")


if __name__ == "__main__":
    main()
