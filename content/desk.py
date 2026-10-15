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


def clean_tags(tags: list[str], limit: int = 15) -> list[str]:
    """띄어쓰기·가운뎃점은 떼고, 그래도 특수문자(. % - 등)가 남는 태그는 뺀다. 최대 15개 (2026-09-30, 전엔 10개)."""
    out = []
    for x in tags:
        x = re.sub(r"[\s·#]", "", x)
        if TAG_OK.match(x) and x not in out:
            out.append(x)
    return out[:limit]

POSTS = ROOT / "posts"
REPO = os.environ.get("GITHUB_REPOSITORY", "mahatera9218-create/shorts-engine")
IMG_LINE = re.compile(r"^\[이미지 (\d+)_([^:\]]*):\s*([^\]]+)\]$")
TABLE_LINE = re.compile(r"^\[표 (\d+):\s*([^\]]+)\]$")  # 네이버 표 자리 (AI 브리핑 인용, 2026-10-01)
TITLE_LINE = re.compile(r"^\d+\.\s+(★\s+)?(.+)\s+—\s+([^—]+?)$")  # 유형에 띄어쓰기 허용 (패션 "그룹 2"·"쿠니네패션식 방식", 2026-10-07)


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
        if para == "[대표 한마디]":  # 옛 자리 — 지어낸 경험 금지로 폐지 (2026-10-03). 남아 있으면 버린다
            continue
        if para == "[상품 자리]":  # 쇼핑커넥트 상품 카드 자리 (2026-10-01)
            blocks.append({"shop": True})
            continue
        tm = TABLE_LINE.match(para)
        if tm:
            tj, cj = folder / "table.json", folder / "clip.json"  # 선수 실제 데이터 표, 없으면 클립 표
            tb = (json.loads(tj.read_text(encoding="utf-8")) if tj.exists() else
                  (json.loads(cj.read_text(encoding="utf-8")).get("table") if cj.exists() else None)) or {}
            if tb.get("rows"):
                blocks.append({"table": int(tm.group(1)), "title": tb.get("title", tm.group(2)),
                               "header": [str(x) for x in tb["header"]], "rows": [[str(x) for x in r] for r in tb["rows"]]})
                continue
        m = IMG_LINE.match(para)
        if m:
            images.append({"n": int(m.group(1)), "label": m.group(2), "file": m.group(3).strip()})
            blocks.append({"img": m.group(3).strip(), "n": int(m.group(1)), "label": m.group(2)})
        else:
            blocks.append({"text": para})
    sources = t.split("## 출처", 1)[1].split("\n## ", 1)[0].strip() if "## 출처" in t else ""
    checklist = re.findall(r"^- ([✅⚠️].+)$", t.split("## 제목")[0], re.M)  # 원문 체크 (2026-10-10)
    human = re.findall(r"^- 👀 (.+)$", t.split("## 제목")[0], re.M)  # 사람이 확인할 항목
    def _sec(head):  # 편집장 '고친 것'·'아직 남은 것' 목록 (2026-10-11)
        m = re.search(rf"### {head}\n((?:- .+\n?)+)", t)
        return [l[2:].strip() for l in m.group(1).splitlines() if l.startswith("- ") and l[2:].strip() != "없음"] if m else []
    fixed, remaining = _sec("고친 것"), _sec("아직 남은 것")
    return {"folder": folder.name, "date": folder.name[:10], "ok": status_ok, "problems": problems, "checklist": checklist, "human": human,
            "fixed": fixed, "remaining": remaining,
            "titles": titles, "tags": clean_tags(tags.group(1).split(",")) if tags else [],
            "category": cat.group(1) if cat else "", "blocks": blocks, "images": images, "sources": sources,
            "clip": (folder / "clip.mp4").exists(), "status": read_status(folder),
            "review": (re.search(r"## 편집장 검토[^\n]*\n\n(.+)", t) or [None, ""])[1].strip(),
            "clip_text": (folder / "clip.txt").read_text(encoding="utf-8") if (folder / "clip.txt").exists() else "",
            "shop": _shop(folder), "marketer": _marketer(folder),
            "notes": len(re.findall(r"^- ", t.split("**참고 (말투·형식", 1)[1].split("\n\n", 2)[1], re.M))
                     if "**참고 (말투·형식" in t else 0}


def _marketer(folder: Path) -> int | None:
    f = folder / "data.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("marketer") if f.exists() else None


def _label(m) -> str:
    from .marketers import label
    return label(m)


def review_mean(p: dict) -> float:
    """'약속 회수 4 · 신뢰 5 · …' → 평균 (없으면 0)."""
    xs = [int(x) for x in re.findall(r"\s(\d)(?:\s|$)", " " + p.get("review", "") + " ")]
    return sum(xs) / len(xs) if xs else 0.0


def today_picks(posts: list[dict], today: str) -> list[dict]:
    """오늘 블로그에 올릴 글 (대표 결정 2026-10-02: 1일 2포, 제대로 써진 2편만). 오늘 ✅ 글 중
    편집장 평균 점수 높은 순 → '참고'(말투·형식) 적은 순 → 마케터 차례 순으로 2편. 이미 올린 글도 2편에 센다."""
    from .marketers import cfg, ids, turn
    n = cfg().get("blog_per_day", 2)
    cands = [p for p in posts if p["date"] == today and p["ok"] and p.get("marketer")
             and p.get("status", {}).get("status") != "rejected"]
    ms = ids()
    t = ms.index(turn(today)) if turn(today) in ms else 0
    order = ms[t:] + ms[:t]
    cands.sort(key=lambda p: (-review_mean(p), p.get("notes", 0),
                              order.index(p["marketer"]) if p["marketer"] in order else 99, p["folder"]))
    return cands[:n]


def _shop(folder: Path) -> dict | None:
    """쇼핑커넥트 상품군 (config/commerce.yaml, 가입 전에는 None)."""
    f = folder / "data.yaml"
    if not f.exists():
        return None
    from .commerce import info
    return info(yaml.safe_load(f.read_text(encoding="utf-8")) or {}, folder.name)


def naver_table(b: dict) -> str:
    """네이버 에디터에 붙여도 모양이 같은 표 (대표 지적 2026-10-03: 도우미와 블로그 모양이 다름).
    에디터는 CSS 클래스·<th>·표 바깥 스타일을 버리므로, 칸마다 글자에 직접 스타일을 넣고 너비를 정해 둔다.
    도우미 화면과 복사가 이 HTML 하나를 같이 쓴다 (화면 = 붙여 넣은 모양)."""
    e = html.escape
    n = len(b["header"])
    widths = ["34%", "66%"] if n == 2 else [f"{100 // n}%"] * n
    cell = "border:1px solid #c8c8c8;padding:8px 10px;font-size:15px;line-height:1.5;vertical-align:middle;word-break:keep-all"
    head = "".join(f'<td style="{cell};width:{w};background:#f2f2f2;font-weight:bold;text-align:center">{e(str(x))}</td>'
                   for x, w in zip(b["header"], widths))
    rows = "".join("<tr>" + "".join(
        f'<td style="{cell};width:{w}' + (';background:#fafafa;font-weight:bold' if j == 0 else '') + f'">{e(str(x))}</td>'
        for j, (x, w) in enumerate(zip(r, widths))) + "</tr>" for r in b["rows"])
    return (f'<table id="nt{b["table"]}" style="width:100%;border-collapse:collapse;border:1px solid #c8c8c8;table-layout:fixed;'
            f'color:#222;background:#fff"><tbody><tr>{head}</tr>{rows}</tbody></table>')


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
table.nt{border-collapse:collapse;width:100%;margin:8px 0;font-size:15px}table.nt th,table.nt td{border:1px solid var(--line);padding:6px 8px;text-align:center}table.nt th{background:var(--bg)}
textarea.ed{width:100%;font:inherit;line-height:1.6;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0;background:var(--card);color:var(--ink);resize:none;overflow:hidden}
textarea.ed.changed{border-color:var(--warn);box-shadow:0 0 0 2px rgba(184,110,0,.18)}textarea.ttl{font-weight:700;font-size:18px}
.row{display:flex;gap:8px}.row button{flex:1}button.small{min-height:40px;font-size:15px;padding:6px 10px}
"""

JS = """
function flash(b,t){const o=b.dataset.o||b.textContent;b.dataset.o=o;b.textContent=t;b.classList.add('done');setTimeout(()=>{b.textContent=o;b.classList.remove('done')},1600)}
async function copyText(b,t){try{await navigator.clipboard.writeText(t);flash(b,'복사됨 ✓')}catch(e){prompt('길게 눌러 복사하세요',t)}}
// 고치기 (대표 요청 2026-09-30): 고친 글은 이 휴대폰에 저장되고, 복사 버튼은 고친 글을 복사한다
function ls(k,v){const key='ed:'+(POST.folder||location.pathname)+':'+k;try{if(v===undefined)return localStorage.getItem(key);if(v===null)localStorage.removeItem(key);else localStorage.setItem(key,v)}catch(e){return null}}
function grow(t){t.style.height='auto';t.style.height=(t.scrollHeight+4)+'px'}
function ed(k){return document.querySelector('textarea.ed[data-k="'+k+'"]')}
function val(k){const t=ed(k);return t?t.value.trim():''}
function paint(t){t.classList.toggle('changed',t.value!==t.defaultValue);const c=document.querySelector('[data-count="'+t.dataset.k+'"]');if(c)c.textContent=t.value.trim().length+'자'+(t.value!==t.defaultValue?' · 고침':'')}
function setEd(k,v){const t=ed(k);if(!t)return;t.value=v;ls(k,v===t.defaultValue?null:v);paint(t);grow(t)}
function resetEd(k){const t=ed(k);if(t)setEd(k,t.defaultValue)}
// 아이폰에서 칸을 눌러도 키보드가 안 뜰 때 (대표 지적 2026-10-06): 입력 창으로 고치기
function askEd(k){const t=ed(k);if(!t)return;const v=prompt('고칠 내용을 입력하세요',t.value);if(v!==null){setEd(k,v.replace(/\\n/g,' '));ls(k,t.value===t.defaultValue?null:t.value)}}
function copyEd(b,k){copyText(b,val(k))}
document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('textarea.ed').forEach(t=>{const v=ls(t.dataset.k);if(v!=null)t.value=v;paint(t);grow(t);
  t.addEventListener('input',()=>{if(t.classList.contains('one'))t.value=t.value.replace(/\\n/g,' ');ls(t.dataset.k,t.value===t.defaultValue?null:t.value);paint(t);grow(t)})}))
function tableText(x){return x.header.length===2?x.rows.map(r=>r[0]+': '+r[1]).join('\\n'):[x.header.join(' · ')].concat(x.rows.map(r=>r.join(' · '))).join('\\n')}
function esc(t){return String(t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function tableHtml(x){const t=document.getElementById('nt'+x.table);return t?t.outerHTML:''}  // 화면에 보이는 표 그대로 복사 (2026-10-03)
// 글꼴 강조 (대표 지시 2026-10-06): **굵게** __밑줄__ *기울임* → 복사할 때 서식으로, 글자만 복사할 땐 표시 빼고. ■ 소제목은 굵고 크게
function plainT(t){return t.replace(/\\*\\*|__/g,'').replace(/(^|[^*])\\*([^*\\n]+)\\*/g,'$1$2')}
function fmt(t){return esc(t).replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>').replace(/__(.+?)__/g,'<u>$1</u>').replace(/(^|[^*])\\*([^*\\n]+)\\*/g,'$1<i>$2</i>').replace(/\\n/g,'<br>')}
function para(t){return /^■ /.test(t)?'<p><b><span style="font-size:20px">'+esc(plainT(t.slice(2)))+'</span></b></p>':'<p>'+fmt(t)+'</p>'}
function para2(t){t=plainT(t);return /^■ /.test(t)?'\\n'+t.slice(2).trim()+'\\n':t}  // 소제목: ■ 빼고 앞뒤 빈 줄 2칸 (대표 지시 2026-10-08)
function bodyText(){const tg=(POST.tags||[]).length?'\\n\\n'+POST.tags.map(t=>'#'+t.replace(/\\s+/g,'')).join(' '):'';return POST.blocks.map((x,i)=>x.text!==undefined?para2(val('b'+i)||x.text):x.table?tableText(x):x.shop?'🛒 상품 자리 (상품 카드를 넣고 이 줄은 지우기)':'📷 사진 '+x.n+' ('+x.label+')').join('\\n\\n')+tg}  // 해시태그는 맨 끝 (2026-10-08)
function bodyHtml(){return POST.blocks.map((x,i)=>x.text!==undefined?para(val('b'+i)||x.text):x.table?tableHtml(x):x.shop?'<p>🛒 상품 자리 (상품 카드를 넣고 이 줄은 지우기)</p>':'<p>📷 사진 '+x.n+' ('+esc(x.label)+')</p>').join('')}
async function copyRich(b,html,text){  // 표가 표로 붙게 HTML과 글자를 같이 넣는다 (안 되는 브라우저는 글자만)
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);flash(b,'복사됨 ✓')}
  catch(e){copyText(b,text)}}
function copyTable(b,n){const x=POST.blocks.find(y=>y.table===n);copyRich(b,tableHtml(x),tableText(x))}
async function saveEdits(b){
  let body='';const t=ed('title');if(t&&t.value!==t.defaultValue)body+='제목: '+val('title')+'\\n\\n';
  document.querySelectorAll('textarea.ed[data-k^="b"]').forEach(x=>{if(x.value!==x.defaultValue)body+='[문단 '+x.dataset.k.slice(1)+']\\n'+x.value.trim()+'\\n\\n'});
  if(!body){alert('고친 곳이 없어요.');return}
  const base='https://github.com/'+POST.repo+'/issues/new?title='+encodeURIComponent((POST.editTag||'[수정]')+' '+POST.folder);
  let url=base+'&body='+encodeURIComponent(body+'아래 초록색 Create 버튼만 누르면 됩니다.');
  if(url.length>7000){try{await navigator.clipboard.writeText(body)}catch(e){prompt('길게 눌러 복사하세요',body)}
    alert('고친 내용이 길어서 복사해 뒀어요. 열리는 화면의 본문 칸을 길게 눌러 붙여넣은 뒤 Create를 누르세요.');url=base}
  location.href=url}
// 아이폰 네이버 앱은 HTML 클립보드를 안 읽어서 서식이 빠짐 (대표 확인 2026-10-06) → 화면에 그린 글을 선택해 복사하면
// 사파리가 서식 있는 글(웹 아카이브·RTF)로 넣어 줘서 앱이 굵게·밑줄을 살린다. 안 되면 예전 방식
async function copyBody(b){copyText(b,bodyText())}  // 글자만 복사: 서식 붙여넣기는 네이버 앱에서 안 되고(2026-10-06 포기), 복사한 글자색·글꼴이 묻어 글이 회색처럼 보일 수 있어서 (대표 지적 2026-10-07)
async function saveClip(b,name){
  name=name||'clip.mp4';
  try{
    const r=await fetch(name);const bl=await r.blob();const files=[new File([bl],name.split('/').pop(),{type:'video/mp4'})];
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


def split_tags(text: str) -> tuple[str, str]:
    """설명과 해시태그를 나눈다 (대표 요청: 따로 복사). 모든 단어가 #으로 시작하는 줄 = 해시태그."""
    desc, tags = [], []
    for line in text.strip().splitlines():
        (tags if line.strip() and all(w.startswith("#") for w in line.split()) else desc).append(line)
    return "\n".join(desc).strip(), " ".join(tags).strip()


def edit_box(key: str, text: str, label: str, one_line: bool = False) -> str:
    """고칠 수 있는 칸 + 복사·되돌리기 (고친 글은 그 휴대폰에 저장, 대표 요청 2026-09-30)."""
    e = html.escape
    k = e(key, quote=True)
    return (f'<textarea class="ed{" ttl one" if one_line else ""}" data-k="{k}" rows="{2 if one_line else 4}">{e(text)}</textarea>'
            f'<div class="muted" data-count="{k}"></div>'
            f'<div class="row"><button onclick="copyEd(this,\'{k}\')">📋 {e(label)}</button>'
            + (f'<button class="ghost small" onclick="askEd(\'{k}\')">✏️ 고치기</button>' if one_line else '')
            + f'<button class="ghost small" onclick="resetEd(\'{k}\')">↩ 원래대로</button></div>')


def copy_pair(text: str, what: str, key: str = "") -> str:
    """설명(고칠 수 있는 칸 + 복사) · 해시태그 복사."""
    e = html.escape
    desc, tags = split_tags(text)
    out = edit_box(f"d:{key or what}", desc, f"{what} 설명 복사")
    if tags:
        out += (f'<button class="ghost" onclick="copyText(this,{e(json.dumps(tags), quote=True)})">📋 해시태그 복사: '
                f'<span class="muted">{e(tags)}</span></button>')
    return out


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

    def pick(t):
        return (f'<button class="ghost" onclick="setEd(\'title\',{e(json.dumps(t["text"]), quote=True)})">'
                f'{e(t["text"])} <span class="muted">· {e(t["type"])} · 이 제목으로 바꾸기</span></button>')

    rest = "".join(pick(t) for t in p["titles"] if t is not best)
    titles = (edit_box("title", best["text"], "제목 복사", one_line=True) if best else "") + (
        f'<details><summary class="muted">다른 제목 {len(p["titles"]) - 1}개 (썸네일과 짝이 아니라 예비)</summary>{rest}</details>'
        if rest else "")
    def tbl(b):
        return (f'<div class="ph"><b>📊 표 {b["table"]} · {e(b["title"])}</b>{naver_table(b)}'
                f'<button class="ghost small" onclick="copyTable(this,{b["table"]})">📋 이 표만 복사</button>'
                '<small>네이버 앱은 붙여넣기로 표가 안 들어가요. 대신 <b>항목: 값</b> 줄글로 깔끔하게 들어가고, <b>AI 브리핑은 이 글도 읽어요</b>(표만 보는 게 아님). '
                '표 모양을 꼭 원하시면 앱의 <b>표</b> 버튼으로 넣고 칸을 채우세요(선택).</small></div>')

    body = "".join(
        f'<textarea class="ed" data-k="b{i}" rows="3">{e(b["text"])}</textarea>' if "text" in b else tbl(b) if "table" in b else
        '<div class="ph" style="border:2px dashed var(--warn);border-radius:10px;padding:10px"><b>🛒 상품 자리</b><small>쇼핑커넥트 상품 카드를 여기에 1개 넣으세요 (없으면 이 줄 지우기)</small></div>' if "shop" in b else
        f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy"><small>📷 사진 {b["n"]} · {e(b["label"])}</small></div>'
        for i, b in enumerate(p["blocks"]))
    each = "".join(f'<div class="ph"><img src="{e(x["file"])}" alt="사진 {x["n"]}" loading="lazy"><small>📷 사진 {x["n"]} · {e(x["label"])}'
                   f'{" · 대표이미지로 지정" if x["n"] == 1 else ""} (길게 눌러 저장)</small></div>' for x in p["images"])
    tags = " ".join("#" + t for t in p["tags"])
    chips = "".join(f'<button class="ghost chip" onclick="copyText(this,{e(json.dumps(t), quote=True)})">{e(t)}</button>' for t in p["tags"])
    data = json.dumps({"blocks": p["blocks"], "images": p["images"], "folder": p["folder"], "repo": REPO},
                      ensure_ascii=False).replace("</", "<\\/")
    thumb = next((x["file"] for x in p["images"] if x["n"] == 1), "thumb.png")
    st = p.get("status", {})
    used = (f'<div class="card" style="border-color:var(--warn)"><b>⚠️ 이미 발행한 글이에요 ({e(st.get("at", ""))})</b>'
            '<div class="muted">같은 글을 두 번 올리지 마세요.</div>'
            + (f'<a class="btn" href="{e(st["url"], quote=True)}">네이버에 올라간 글 보기</a>' if st.get("url") else
               '<div class="muted">네이버 공개 확인 전 (매일 아침 자동 확인)</div>')
            + '</div>') if st.get("status") == "used" else ""
    sh = p.get("shop")
    shop = (f'<div class="card"><h2>🛒 쇼핑커넥트: {e(sh["name"])}</h2>'
            + "".join(f'<a class="btn" href="{e(x["url"], quote=True)}">{e(x["name"])}</a>' for x in sh["products"])
            + (f'<button onclick="copyText(this,{e(json.dumps(sh["keyword"]), quote=True)})">🔎 검색어 복사: {e(sh["keyword"])}</button>'
               f'<div class="muted">브랜드 커넥트에서 이 검색어로 찾아 <b>{e(sh["pick"])}</b>인 상품 1개를 글에 붙이세요.'
               f' 마땅한 게 없으면 다른 검색어: {e(" · ".join(k for k in sh["others"] if k != sh["keyword"]))}</div>'
               if sh["keyword"] else "")
            + edit_box("shopnote", sh["disclosure"], "광고 고지 복사")
            + '<div class="muted">같은 상품을 <b>클립에 상품 태그로</b> 다는 게 핵심이에요 (클립 조회가 훨씬 많아요). 이 글의 클립은 선수 사진 없이 만들어져 태그를 달아도 돼요. 블로그 글에 붙일 때는 <b>본문 맨 첫 줄</b>에 광고 고지를 넣고(공정위 지침: 글 첫 부분), 상품 카드는 본문의 <b>🛒 상품 자리</b>에 넣으세요.</div></div>'
            ) if sh else ""
    done_btn = e(issue_link("발행완료", p["folder"], "블로그·클립 발행을 마쳤어요."), quote=True)
    again_btn = e(issue_link("다시뽑기", p["folder"], "이 글은 버리고 다른 선수·테마로 새로 써 주세요."), quote=True)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>{e(best["text"] if best else p["folder"])}</title><style>{CSS}</style></head><body><main>
<a href="../../" class="muted">← 글 목록</a>
<h1>{e(best["text"] if best else p["folder"])}</h1><div class="muted">{e(p["date"])} · 카테고리 {e(p["category"])}{" · " + e(_label(p.get("marketer"))) if p.get("marketer") else ""}</div>
<p>{status}</p>{f"<ul>{probs}</ul>" if probs else ""}{used}
{f'<p class="muted">편집장 검토: {e(p["review"])}</p>' if p.get("review") else ""}
<div class="card"><h2><span class="step">1</span>사진 저장</h2>
<button onclick="saveAll(this)">📷 사진 {len(p["images"])}장 한 번에 저장</button>
<div class="muted">공유 창이 뜨면 "이미지 저장" / "사진에 저장"을 누르세요. 파일 이름 앞 번호가 넣는 순서예요.</div></div>
<div class="card"><h2><span class="step">2</span>제목</h2>{titles}
<div class="muted">썸네일과 짝으로 만든 제목이에요. 칸을 눌러 바로 고칠 수 있어요 (고친 글은 이 휴대폰에 저장, 복사하면 고친 제목이 복사돼요).</div></div>
<div class="card"><h2><span class="step">3</span>대표 사진 (썸네일)</h2><img class="thumb" src="{e(thumb)}" alt="썸네일">
<div class="muted">본문에 넣은 뒤 이 사진을 대표이미지로 지정하세요.</div></div>
<div class="card"><h2><span class="step">4</span>본문</h2>
<button onclick="copyBody(this)">📋 본문 복사 (사진 자리 📷 표시)</button>
<div class="muted">네이버 앱에 붙여넣고, "📷 사진 N" 줄을 지운 자리에 N번 사진을 넣으세요. 고치고 싶은 문단은 아래 <a href="#draft">초안</a>에서 바로 고치면 복사에 반영돼요.</div>
</div>
<div class="card"><h2><span class="step">5</span>태그</h2><button class="ghost" onclick="copyText(this,{e(json.dumps(tags), quote=True)})">📋 한 번에 복사: {e(tags)}</button>
<div class="muted">한 번에 붙여넣기가 안 되면 아래 태그를 하나씩 눌러 복사 → 태그 칸에 붙여넣기 → 완료(엔터)를 반복하세요.</div>
<div class="chips">{chips}</div></div>
{shop}<div class="card"><h2>🎬 클립</h2><div class="muted">클립 영상·설명은 도우미 첫 화면의 <a href="../../#clip">클립 탭</a>에 있어요 (블로그 발행 뒤 올리기).</div></div>
<div class="card"><h2><span class="step">6</span>다 올렸으면</h2>
<a class="btn" href="{done_btn}">✅ 발행 완료 표시</a>
<div class="muted">GitHub 화면이 열리면 초록 <b>Create</b>만 누르세요. 2~3분 뒤 목록에서 "발행한 글"로 내려가요 (중복 발행 방지).</div></div>
<div class="card body" id="draft"><h2>✏️ 초안 (눌러서 고치기)</h2>
<div class="muted">고친 문단은 주황 테두리로 보여요. 이 휴대폰에 자동 저장되고, 위 <b>본문 복사</b>에 반영돼요.</div>{body}
<button onclick="saveEdits(this)">💾 고친 내용 저장 (도우미에 반영)</button>
<div class="muted">GitHub 화면이 열리면 초록 <b>Create</b>만 누르세요. 2~3분 뒤 도우미에 반영되고, 어떻게 고치셨는지 모아서 다음 글쓰기에 반영해요.</div></div>
<div class="card"><h2>🔄 이 글이 마음에 안 들면</h2>
<a class="btn" style="background:var(--card);color:var(--ink);border:1px solid var(--line)" href="{again_btn}">다른 글로 다시 뽑기</a>
<div class="muted">GitHub 화면에서 <b>Create</b>를 누르면 이 글은 목록에서 빠지고, 다른 선수·테마로 새 글을 써요 (약 5~10분).</div></div>
<div class="card" id="each"><h2>사진 하나씩 저장</h2>{each}</div>
<details class="card"><summary>출처</summary><pre style="white-space:pre-wrap">{e(p["sources"])}</pre></details>
</main><script>const POST={data};{JS}</script></body></html>"""


def clip_shop(p: dict) -> str:
    """클립 카드의 쇼핑 태그 안내 (상품군이 있는 글만: 그 클립은 선수 사진 없이 만들어진다)."""
    sh, e = p.get("shop"), html.escape
    if not sh or not sh.get("keyword"):
        return ""
    return (f'<button class="ghost" onclick="copyText(this,{e(json.dumps(sh["keyword"]), quote=True)})">🛒 상품 태그 검색어 복사: '
            f'{e(sh["keyword"])}</button><div class="muted">클립 올릴 때 <b>상품 태그</b>에서 이 검색어로 찾아 '
            f'{e(sh["pick"])}인 상품 1개를 다세요. 광고 고지는 설명 맨 앞에 들어 있어요.</div>')


def clip_cards(posts: list[dict]) -> str:
    """클립 탭 (대표 결정 2026-10-01): 가장 최근 날짜 마케터 글의 클립을 모두 올린다 (클립 조회수로 마케터 비교).
    기준 미달(⚠️)·버린 글의 클립은 뺀다."""
    e = html.escape
    ps = [p for p in posts if p.get("clip") and p["ok"] and p.get("status", {}).get("status") != "rejected"]
    if not ps:
        return "<p>올릴 클립이 없어요.</p>"
    last = max(p["date"] for p in ps)
    ps = sorted((p for p in ps if p["date"] == last), key=lambda p: (p.get("marketer") or 9, p["folder"]))
    from .marketers import label
    out = []
    for p in ps:
        title = next((t["text"] for t in p["titles"] if t["best"]), p["folder"])
        who = label(p.get("marketer")) or "마케터 없음"
        badge = f'<span class="badge ok">{e(who)} → 올리세요</span>'
        src = f"p/{slug(p['folder'])}/clip.mp4"
        out.append(f"""<div class="card"><h2>{e(title)}</h2>{badge} <span class="muted">{e(p["date"])}</span>
<video src="{e(src)}" controls playsinline preload="none" style="width:100%;max-width:320px;border-radius:10px;display:block;margin-top:8px"></video>
<button onclick="saveClip(this,{e(json.dumps(src), quote=True)})">🎬 클립 영상 저장</button>
{copy_pair(p["clip_text"], "클립", p["folder"])}{clip_shop(p)}</div>""")
    return "".join(out)


def inline_article(p: dict) -> str:
    """도우미 첫 화면 '지금 쓰기' 버튼 바로 밑에 완성된 글을 읽기 전용으로 보여 준다 (대표 지시 2026-10-03).
    본문·표·사진 + 본문 복사·발행 완료·자세히 버튼. 복사·표는 index의 POST(= 이 글)로 동작한다."""
    e = html.escape
    from .marketers import label
    best = next((t for t in p["titles"] if t["best"]), (p["titles"][0] if p["titles"] else {"text": p["folder"]}))
    badge = ('<span class="badge ok">✅ 발행 가능</span>' if p["ok"]
             else '<span class="badge warn">⚠️ 확인 필요 — 발행하지 말고 Claude에게</span>')
    parts = []
    for b in p["blocks"]:
        if "text" in b:
            parts.append(f'<p>{e(b["text"]).replace(chr(10), "<br>")}</p>')
        elif "table" in b:
            parts.append(f'<div style="margin:12px 0"><b class="muted">📊 {e(b["title"])}</b>{naver_table(b)}</div>')
        elif "shop" in b:
            parts.append('<div class="ph" style="border:2px dashed var(--warn);border-radius:10px;padding:10px"><b>🛒 상품 자리</b>'
                         '<small>쇼핑커넥트 상품 카드 1개 (없으면 지우기)</small></div>')
        else:
            parts.append(f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy">'
                         f'<small>📷 사진 {b["n"]} · {e(b["label"])} (길게 눌러 저장)</small></div>')
    done_btn = e(issue_link("발행완료", p["folder"], "블로그·클립 발행을 마쳤어요."), quote=True)
    return (f'<div class="card" style="margin-top:14px"><h2>{e(best["text"])}</h2>{badge} '
            f'<span class="muted">{e(label(p.get("marketer")))}</span>'
            f'<button onclick="copyBody(this)">📋 본문 전체 복사 (표·사진 자리 포함)</button>'
            f'<div class="body" style="margin-top:8px">{"".join(parts)}</div>'
            f'<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="p/{slug(p["folder"])}/">✏️ 제목 고르기·칸별 고치기·클립</a>'
            f'<a class="btn" href="{done_btn}">✅ 발행 완료 표시</a>'
            '<div class="muted">누르면 GitHub 화면이 열려요. 초록색 Create만 누르면 끝.</div></div>')


def index(posts: list[dict], n_shorts: int = 0, shorts_html: str = "") -> str:
    e = html.escape

    from .marketers import label, turn
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    picks = today_picks(posts, today)
    todo_picks = [p for p in picks if p.get("status", {}).get("status") != "used"]

    def row(p, muted=False, star=False):
        title = next((t["text"] for t in p["titles"] if t["best"]), p["folder"])
        mark = "☑️" if muted else ("⭐" if star else "✅" if p["ok"] else "⚠️")
        style = ("text-align:left;background:var(--card);color:var(--ink);border:" + ("3px solid var(--accent)" if star else "1px solid var(--line)")
                 + (";opacity:.55" if muted else ""))
        who = f'<br><span class="muted">{e(label(p.get("marketer")))}</span>' if p.get("marketer") else ""
        return f'<a class="btn" style="{style}" href="p/{slug(p["folder"])}/">{mark} {e(p["date"])} · {e(title)}{who}</a>'

    live = [p for p in posts if p.get("status", {}).get("status") not in ("used", "rejected") and p not in picks]
    used = [p for p in posts if p.get("status", {}).get("status") == "used"]
    turn_note = (f'<h2>⭐ 오늘 올릴 글 {len(todo_picks)}편 (잘 써진 순)</h2>' + "".join(row(p, star=True) for p in todo_picks)
                 ) if todo_picks else ("<p class=\"muted\">오늘 올릴 글 2편을 다 올렸어요 👍</p>" if picks else "")
    todo = "".join(row(p) for p in sorted(live, key=lambda p: p["folder"])[-14:])
    done = "".join(row(p, True) for p in sorted(used, key=lambda p: p["status"].get("at", ""), reverse=True)[:10])
    top = todo_picks[0] if todo_picks else None   # '지금 쓰기' 버튼 바로 밑에 완성된 글 1편 (대표 지시 2026-10-03)
    top_article = inline_article(top) if top else ""
    post_data = json.dumps({"blocks": top["blocks"], "images": top["images"]}, ensure_ascii=False) if top else '{"blocks":[],"images":[]}'  # index copyBody가 이 글로 동작
    tabs = """<nav class="tabs"><a href="#blog" data-t="blog">📝 블로그</a><a href="#clip" data-t="clip">🎬 클립</a>
<a href="#shorts" data-t="shorts">▶️ 쇼츠</a></nav>"""
    tab_js = """function writeNow(){const raw=document.getElementById('who').value.trim();if(!raw){alert('선수 이름을 적어 주세요 (예: 김도영 / 어제 끝내기 홈런 / KIA)');return}
  const parts=raw.split('/');const n=parts[0].trim();const ev=(parts[1]||'').trim();const tm=(parts[2]||'').trim();
  if(!n){alert('선수 이름을 적어 주세요');return}
  const nl=String.fromCharCode(10);
  let body=['이 선수로 지금 글을 써 주세요. 아래 초록색 Create 버튼만 누르면 됩니다.'];
  if(ev)body=body.concat(['','사건: '+ev]);if(tm)body=body.concat(['','소속: '+tm]);
  location.href='https://github.com/REPO_SLUG/issues/new?title='+encodeURIComponent('[선수] '+n)+'&body='+encodeURIComponent(body.join(nl))}
function tab(){const h=(location.hash||'#blog').slice(1);document.querySelectorAll('section.tab').forEach(s=>s.hidden=s.id!==h);
document.querySelectorAll('nav.tabs a').forEach(a=>a.classList.toggle('on',a.dataset.t===h));
document.querySelectorAll('section.tab:not([hidden]) textarea.ed').forEach(grow)}addEventListener('hashchange',tab);addEventListener('DOMContentLoaded',tab);tab();"""
    tab_js = tab_js.replace("REPO_SLUG", REPO)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>발행 도우미</title><style>{CSS}
nav.tabs{{display:flex;gap:6px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}}
nav.tabs a{{flex:1;text-align:center;padding:12px 4px;border-radius:12px;border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:700}}
nav.tabs a.on{{background:var(--btn);color:var(--btnink)}}</style></head><body><main>
<h1>발행 도우미 · 억소리 나는 스포츠</h1>
<p class="muted">마지막 업데이트: {datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m월 %d일 %H:%M")}</p>
{tabs}
<section class="tab" id="blog">
<div class="card" style="border:2px solid var(--accent)"><h2>⚡ 이 선수로 지금 쓰기</h2>
<input id="who" placeholder="선수명 / 이슈 / 소속 (예: 김도영 / 어제 홈런 / KIA)" style="width:100%;min-height:50px;margin:8px 0;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:16px">
<button onclick="writeNow()">⚡ 지금 쓰기</button>
<div class="muted">선수명만 적어도 돼요. 우리 목록 선수면 종목이 자동이에요. <b>동명이인이거나 목록에 없는 선수</b>면 뒤에 <b>/ 소속</b>(예: 토트넘·PGA)을 적어 주세요. 사건을 적으면 제목·첫 문단 훅으로 걸어요. 비교 상품은 <b>그날 검색량 상위(가전·차·IT·여행)로 자동</b>이에요. 15~20분 뒤 바로 아래에 <b>블로그·클립·쇼츠</b>가 떠요 (Claude 약 $0.3, 연봉 못 찾는 선수는 안 나올 수 있어요).</div></div>
{top_article}
{turn_note}
<h2>{'다른 글 (예비)' if picks else '오늘의 후보'}</h2>
{todo or '<p>후보가 아직 없어요. 매일 아침 5시쯤 올라와요.</p>'}
{f'<h2 style="margin-top:28px">발행한 글</h2>{done}' if done else ''}
<div class="card" style="margin-top:28px"><h2>필요할 때만 누르는 버튼</h2>
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(issue_link("다시그리기", "오늘후보", "글은 그대로 두고 사진·썸네일·클립만 새로 그려 주세요."), quote=True)}">🎨 사진·클립 다시 그리기</a>
<div class="muted">무료 · 5~10분. 썸네일·클립 디자인을 고친 뒤 지금 있는 후보에 바로 반영할 때.</div>
<a class="btn" style="background:transparent;color:var(--ink);border:1px solid var(--line)" href="{e(issue_link("새후보", "3편", "마케터 3명이 1편씩 새로 써 주세요."), quote=True)}">✍️ 마케터 3명 새로 쓰기</a>
<div class="muted">Claude 비용 약 $1 · 15~25분 (3명이 동시에 써요). 오늘 글이 다 마음에 안 들 때만.</div>
<div class="muted">누르면 GitHub 화면이 열려요. 초록색 <b>Create</b>만 누르면 끝이에요.</div></div>
</section>
<section class="tab" id="clip" hidden>
<p class="muted"><b>오늘 마케터 3명의 클립을 모두 올려요</b> (클립 조회수로 마케터를 비교해요). 블로그 앱 아래 <b>+</b> → <b>클립 만들기</b> → 저장한 영상 → <b>음악</b>에서 인기 음원 → <b>설명 복사</b>·<b>해시태그 복사</b> 붙여넣기 → 상품 태그(있으면) → 올리기.</p>
{clip_cards(posts)}
</section>
<section class="tab" id="shorts" hidden>
{shorts_html}
</section>
</main><script>const POST={post_data};{JS}{tab_js}</script></body></html>"""


SHORTS = ROOT / "shorts"
KIND = {"A": "국내 선수 · 통장형", "B": "해외 선수 vs 국내 · 비교형", "C": "국내 선수 · 순위표"}


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


def shorts_body(items: list[dict], prefix: str = "") -> str:
    """쇼츠 안내 + 카드들 (첫 화면 쇼츠 탭과 /s/ 페이지가 같이 쓴다)."""
    e = html.escape
    cards = []
    for s in items:
        v = f"{prefix}{slug(s['folder'])}.mp4"  # 주소에 한글이 들어가지 않게
        cards.append(f"""<div class="card"><h2>{e(KIND.get(s['kind'], s['kind']))}</h2><div class="muted">{e(s['date'])}</div>
<video src="{e(v)}" controls playsinline preload="none" style="width:100%;max-width:320px;border-radius:10px;display:block;margin-top:8px"></video>
<button onclick="saveClip(this,{e(json.dumps(v), quote=True)})">🎬 영상 저장</button>
{edit_box("t:" + s['folder'], s['title'], "제목 복사", one_line=True)}
{copy_pair(s['desc'], "쇼츠", s['folder'])}
<a class="muted" href="{e(issue_link("쇼츠버림", s['folder'], "이 쇼츠는 올리지 않고 버려 주세요. 같은 형식으로 새로 만들어져요."), quote=True)}">🗑 이 쇼츠는 안 올리고 버리기</a></div>""")
    guide = """<div class="card"><ol class="muted"><li><b>영상 저장</b> → 유튜브 앱 아래 <b>+</b> → <b>동영상 업로드</b> → 저장한 영상</li>
<li><b>사운드 추가</b>로 인기 음원 하나</li>
<li><b>썸네일(커버) 고르기</b>가 보이면 <b>맨 앞 장면</b> (안 보여도 괜찮아요: 모든 장면 위쪽에 제목이 있어요)</li>
<li><b>제목 복사</b> → 제목 칸, <b>설명 복사</b>·<b>해시태그 복사</b> → 설명 칸 → <b>공개</b> → 업로드</li></ol>
<div class="muted">매일 국내 선수 2개 + 해외 리그 선수 1개. 올린 쇼츠는 다음 날 아침 자동 확인돼 사라져요. <b>안 올린 쇼츠가 있으면 그 칸은 새로 만들지 않아요</b> — 올리기 싫으면 '버리기'.</div></div>"""
    return guide + ("".join(cards) or "<p>올릴 쇼츠가 없어요. 매일 아침 글쓰기 뒤에 만들어져요.</p>")


def shorts_page(items: list[dict]) -> str:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>쇼츠 영상 모음</title><style>{CSS}</style></head><body><main>
<a href="../#shorts" class="muted">← 발행 도우미</a>
<h1>유튜브 쇼츠 모음</h1>
{shorts_body(items)}
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
                                          sum(s["date"] == today for s in items), shorts_body(items, "s/")), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8")
    return posts


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    posts = build(out)
    print(f"발행 도우미: 글 {len(posts)}편 → {out}")


if __name__ == "__main__":
    main()
