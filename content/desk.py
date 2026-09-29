"""발행 도우미 페이지: posts/의 발행 패키지를 태블릿에서 버튼 몇 번으로 옮길 수 있는 정적 사이트로 만든다.

- 글마다 한 페이지: 제목 후보(누르면 복사), 썸네일, [본문 복사], [사진 한 번에 저장], [사진까지 통째로 복사(시험)], 태그 복사
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
import re
import shutil
import sys
from pathlib import Path

from market.common import ROOT

POSTS = ROOT / "posts"
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
            "titles": titles, "tags": [x.strip() for x in tags.group(1).split(",")] if tags else [],
            "category": cat.group(1) if cat else "", "blocks": blocks, "images": images, "sources": sources}


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
async function copyRich(b){
  const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
  const h=POST.blocks.map(x=>x.text?'<p>'+esc(x.text).replace(/\\n/g,'<br>')+'</p>':'<p><img src="'+new URL(x.img,location.href).href+'"></p>').join('');
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([h],{type:'text/html'}),'text/plain':new Blob([bodyText()],{type:'text/plain'})})]);flash(b,'복사됨 ✓ 네이버에 붙여넣어 보세요')}
  catch(e){alert('이 브라우저는 사진 포함 복사를 지원하지 않아요. [본문 복사]를 써 주세요.')}
}
async function saveAll(b){
  try{
    const files=await Promise.all(POST.images.map(async x=>{const r=await fetch(x.file);const bl=await r.blob();return new File([bl],String(x.n).padStart(2,'0')+'_'+x.file,{type:bl.type||'image/png'})}));
    if(navigator.canShare&&navigator.canShare({files})){await navigator.share({files});flash(b,'완료 ✓');return}
  }catch(e){if(e.name==='AbortError')return}
  document.getElementById('each').scrollIntoView({behavior:'smooth'});alert('한 번에 저장이 안 되는 브라우저예요. 아래 사진을 하나씩 길게 눌러 저장해 주세요.')
}
"""


def page(p: dict) -> str:
    e = html.escape
    best = next((t for t in p["titles"] if t["best"]), p["titles"][0] if p["titles"] else None)
    status = ('<span class="badge ok">✅ 발행 가능</span>' if p["ok"] else
              '<span class="badge warn">⚠️ 확인 필요 — 발행하지 말고 Claude에게 알려주세요</span>')
    probs = "".join(f"<li>{e(x)}</li>" for x in p["problems"])
    titles = "".join(
        f'<button class="ghost" onclick="copyText(this,{e(json.dumps(t["text"]), quote=True)})">'
        f'{"★ " if t["best"] else ""}{e(t["text"])} <span class="muted">· {e(t["type"])} · {len(t["text"])}자</span></button>'
        for t in p["titles"])
    body = "".join(
        f'<p>{e(b["text"])}</p>' if "text" in b else
        f'<div class="ph"><img src="{e(b["img"])}" alt="사진 {b["n"]}" loading="lazy"><small>📷 사진 {b["n"]} · {e(b["label"])}</small></div>'
        for b in p["blocks"])
    each = "".join(f'<div class="ph"><img src="{e(x["file"])}" alt="사진 {x["n"]}" loading="lazy"><small>📷 사진 {x["n"]} · {e(x["label"])}'
                   f'{" · 대표이미지로 지정" if x["n"] == 1 else ""} (길게 눌러 저장)</small></div>' for x in p["images"])
    tags = " ".join("#" + t.replace(" ", "") for t in p["tags"])
    data = json.dumps({"blocks": p["blocks"], "images": p["images"]}, ensure_ascii=False).replace("</", "<\\/")
    thumb = next((x["file"] for x in p["images"] if x["n"] == 1), "thumb.png")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>{e(best["text"] if best else p["folder"])}</title><style>{CSS}</style></head><body><main>
<a href="../../" class="muted">← 글 목록</a>
<h1>{e(best["text"] if best else p["folder"])}</h1><div class="muted">{e(p["date"])} · 카테고리 {e(p["category"])}</div>
<p>{status}</p>{f"<ul>{probs}</ul>" if probs else ""}
<div class="card"><h2><span class="step">1</span>사진 저장</h2>
<button onclick="saveAll(this)">📷 사진 {len(p["images"])}장 한 번에 저장</button>
<div class="muted">공유 창이 뜨면 "이미지 저장" / "사진에 저장"을 누르세요. 파일 이름 앞 번호가 넣는 순서예요.</div></div>
<div class="card"><h2><span class="step">2</span>제목 (눌러서 복사)</h2>{titles}
<div class="muted">★ 추천. 마음에 드는 걸 골라 직접 다듬어도 돼요.</div></div>
<div class="card"><h2><span class="step">3</span>대표 사진 (썸네일)</h2><img class="thumb" src="{e(thumb)}" alt="썸네일">
<div class="muted">본문에 넣은 뒤 이 사진을 대표이미지로 지정하세요.</div></div>
<div class="card"><h2><span class="step">4</span>본문</h2>
<button onclick="copyBody(this)">📋 본문 복사 (사진 자리 📷 표시)</button>
<div class="muted">네이버 앱에 붙여넣고, "📷 사진 N" 줄을 지운 자리에 N번 사진을 넣으세요.</div>
<button class="ghost" onclick="copyRich(this)">🧪 사진까지 통째로 복사 (시험)</button>
<div class="muted">네이버 편집기가 사진까지 받아 주면 사진 넣는 과정이 없어져요. 안 되면 위 버튼을 쓰세요.</div></div>
<div class="card"><h2><span class="step">5</span>태그</h2><button class="ghost" onclick="copyText(this,{e(json.dumps(tags), quote=True)})">{e(tags)}</button></div>
<div class="card body"><h2>미리 읽기</h2>{body}</div>
<div class="card" id="each"><h2>사진 하나씩 저장</h2>{each}</div>
<details class="card"><summary>출처</summary><pre style="white-space:pre-wrap">{e(p["sources"])}</pre></details>
</main><script>const POST={data};{JS}</script></body></html>"""


def index(posts: list[dict]) -> str:
    e = html.escape
    rows = "".join(
        f'<a class="btn" style="text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line)" href="p/{slug(p["folder"])}/">'
        f'{"✅" if p["ok"] else "⚠️"} {e(p["date"])} · {e(next((t["text"] for t in p["titles"] if t["best"]), p["folder"]))}</a>'
        for p in posts)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive">
<title>발행 도우미</title><style>{CSS}</style></head><body><main>
<h1>발행 도우미 · 억소리 나는 스포츠</h1>
<p class="muted">마지막 업데이트: {datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m월 %d일 %H:%M")}</p>
<p class="muted">매일 아침 6시 47분에 새 글이 올라와요. 위에서부터(오래된 글부터) 하루 1편씩 발행하세요. ✅만 발행하고 ⚠️는 Claude에게 알려주세요. 최근 14편만 보여요.</p>
{rows or '<p>아직 글이 없어요.</p>'}
</main></body></html>"""


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
        (d / "index.html").write_text(page(p), encoding="utf-8")
    (out / "index.html").write_text(index(sorted(posts, key=lambda p: p["folder"])[-14:]), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8")
    return posts


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    posts = build(out)
    print(f"발행 도우미: 글 {len(posts)}편 → {out}")


if __name__ == "__main__":
    main()
