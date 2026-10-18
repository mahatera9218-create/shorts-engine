"""건강 블로그 발행 도우미 (대표 2026-10-18).

reports/건강글-초안/*.md (예약작업/수동 생성한 발행 패키지)를 휴대폰용 정적 페이지로 만든다.
글마다 복사 버튼: 제목 / 본문 / 해시태그 / 이미지 프롬프트. 검증 상태 배지. 홈 화면에 깔아 두고 쓴다.
디자인은 경제 도우미와 같은 결(크림 바탕·테라코타 포인트·이모지 없음). 검색엔진 수집 금지(noindex).
Cloudflare Pages (.github/workflows/health-desk.yml).

사용법: python -m content.health_desk [출력 폴더, 기본 site-health]
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from market.common import ROOT

DRAFTS = ROOT / "reports" / "건강글-초안"
KST = ZoneInfo("Asia/Seoul")
NAME = "건강 블로그 (갱년기)"


def parse(md: str) -> dict:
    """초안 .md 한 편을 조각으로 나눈다.

    새 형식(2026-10-18): 제목은 '후보 여러 개'를 보여 주고 대표가 고른다.
    본문 블록에는 사진 자리([사진N])와 해시태그가 함께 들어 있어 '본문 복사' 한 번으로 다 복사된다.
    이미지 프롬프트는 별도.
    """
    d = {"검증": "", "키워드": "", "후보": [], "추천": "", "본문": "", "이미지": "", "출처": ""}
    m = re.search(r"^검증:\s*(.+)$", md, re.M)
    if m:
        d["검증"] = m.group(1).strip()
    m = re.search(r"^키워드:\s*(.+)$", md, re.M)
    if m:
        d["키워드"] = m.group(1).strip()

    # 제목 후보: '제목 후보:' 줄 아래의 번호 줄들을 줄 단위로 수집. 없으면 옛 '제목(선정):' 한 개로.
    head = re.split(r"^---\s*$", md, maxsplit=1, flags=re.M)[0]
    collecting = False
    for ln in head.splitlines():
        if re.match(r"^\s*제목\s*후보\s*[:：]?\s*$", ln):
            collecting = True
            continue
        if collecting:
            mm = re.match(r"^\s*(?:\d+[.)]|[-*])\s*(.+?)\s*$", ln)
            if mm and mm.group(1).strip():
                d["후보"].append(mm.group(1).strip())
            elif ln.strip() == "":
                continue
            else:
                collecting = False  # 추천:/기타 줄 만나면 종료
    rec = re.search(r"추천\s*[:：]?\s*(\d+)\s*번?", head)
    if rec:
        d["추천"] = rec.group(1)
    if not d["후보"]:
        m = re.search(r"^제목\(선정\):\s*(.+)$", md, re.M)
        if m:
            d["후보"] = [m.group(1).strip()]

    # 첫 '---' 이후 ~ '--- 이미지 프롬프트 ---' 전 = 발행 본문(사진 자리·해시태그 포함, 그대로 복사)
    parts = re.split(r"^---\s*$", md, maxsplit=1, flags=re.M)
    rest = parts[1] if len(parts) > 1 else md
    img_split = re.split(r"^---\s*이미지 프롬프트\s*---\s*$", rest, maxsplit=1, flags=re.M)
    d["본문"] = img_split[0].strip("\n")
    after_img = img_split[1] if len(img_split) > 1 else ""
    src_split = re.split(r"^---\s*출처.*?---\s*$", after_img, maxsplit=1, flags=re.M)
    d["이미지"] = src_split[0].strip()
    d["출처"] = (src_split[1].strip() if len(src_split) > 1 else "")
    return d


def badge(v: str) -> str:
    key = "확인됨" if v.startswith("확인됨") else ("미확인" if v.startswith("미확인") else "부분확인")
    color = {"확인됨": "#2e7d52", "부분확인": "#b7791f", "미확인": "#b5482f"}[key]
    return f'<span class="badge" style="background:{color}">검증 {html.escape(key)}</span>'


_tid = 0


def card(d: dict, fname: str) -> str:
    global _tid

    def hidden(text):
        global _tid
        _tid += 1
        tid = f"t{_tid}"
        return tid, f'<textarea id="{tid}" readonly>{html.escape(text)}</textarea>'

    def box(label, text, cls=""):
        if not text:
            return ""
        tid, ta = hidden(text)
        return (
            f'<div class="row {cls}"><div class="lab">{html.escape(label)}</div>'
            f'<button class="cp" data-t="{tid}">복사</button>{ta}</div>'
        )

    kw = html.escape(d["키워드"] or "(키워드 미상)")
    # 제목 후보 — 골라서 복사
    cand_rows = []
    for i, t in enumerate(d["후보"], 1):
        tid, ta = hidden(t)
        rec = " 추천" if str(i) == d["추천"] else ""
        cand_rows.append(
            f'<div class="trow"><button class="cp tcp" data-t="{tid}">고르기</button>'
            f'<span class="tt">{html.escape(t)}<span class="rec">{rec}</span></span>{ta}</div>'
        )
    titles = (
        '<div class="lab2">제목 — 마음에 드는 것 하나 골라 복사</div>' + "".join(cand_rows)
        if cand_rows else '<div class="lab2">제목 후보 없음</div>'
    )
    return (
        '<section class="card">'
        f'<div class="head"><span class="kw">{kw}</span>{badge(d["검증"])}</div>'
        + titles
        + box("본문 복사 (사진 위치·해시태그 포함)", d["본문"])
        + box("이미지 프롬프트 복사 (별도)", d["이미지"], "img")
        + (f'<details><summary>출처(F목록)</summary><pre>{html.escape(d["출처"])}</pre></details>' if d["출처"] else "")
        + '</section>'
    )


def build(out_dir: str) -> int:
    out = ROOT / out_dir
    out.mkdir(parents=True, exist_ok=True)
    files = [p for p in DRAFTS.glob("*.md") if p.name != "README.md"] if DRAFTS.exists() else []
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    cards = []
    for p in files:
        try:
            cards.append(card(parse(p.read_text(encoding="utf-8")), p.name))
        except Exception as e:  # 한 글이 깨져도 나머지는 보이게
            cards.append(f'<section class="card"><div class="title">[읽기 실패] {html.escape(p.name)}: {html.escape(str(e))}</div></section>')
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    empty = '<p class="empty">아직 생성된 초안이 없어요. 생성되면 여기에 자동으로 떠요.</p>'
    page = f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{html.escape(NAME)} 발행 도우미</title>
<style>
:root{{--bg:#f4efe6;--card:#fbf8f2;--ink:#2b2724;--muted:#6b645c;--line:#e4dccb;--point:#c0603f}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.6}}
.wrap{{max-width:680px;margin:0 auto;padding:18px 16px 60px}}
h1{{font-size:20px;margin:6px 0 2px}}
.sub{{color:var(--muted);font-size:13px;margin-bottom:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:16px}}
.head{{display:flex;align-items:center;gap:8px;margin-bottom:6px}}
.kw{{font-size:13px;color:var(--muted);flex:1}}
.badge{{color:#fff;font-size:11px;padding:3px 8px;border-radius:20px;white-space:nowrap}}
.title{{font-weight:700;font-size:16px;margin:4px 0 12px}}
.row{{display:flex;align-items:center;gap:8px;margin:8px 0}}
.lab{{flex:1;font-size:14px}}
.lab2{{font-size:13px;color:var(--muted);margin:10px 0 4px}}
.trow{{display:flex;align-items:flex-start;gap:8px;margin:6px 0;padding:6px 0;border-top:1px dashed var(--line)}}
.tt{{flex:1;font-size:14px;font-weight:600;line-height:1.45}}
.rec{{color:var(--point);font-size:11px;font-weight:700;margin-left:4px}}
.cp{{border:0;background:var(--point);color:#fff;font-size:13px;padding:8px 14px;border-radius:9px;cursor:pointer;white-space:nowrap}}
.tcp{{padding:6px 12px;font-size:12px}}
.cp.done{{background:#2e7d52}}
textarea{{position:absolute;left:-9999px;opacity:0}}
details{{margin-top:10px}}
summary{{color:var(--muted);font-size:13px;cursor:pointer}}
pre{{white-space:pre-wrap;font-size:12px;color:var(--muted);background:#f0ebe0;padding:10px;border-radius:8px;overflow:auto}}
.empty{{color:var(--muted);text-align:center;padding:40px 0}}
.tip{{font-size:12px;color:var(--muted);margin-top:4px}}
</style></head>
<body><div class="wrap">
<h1>{html.escape(NAME)} 발행 도우미</h1>
<div class="sub">{now} 기준 · 글 {len(files)}편 · ①제목 하나 골라 복사 → ②본문 복사(사진 위치·해시태그 포함)해 네이버에 붙이기 → ③이미지 프롬프트 복사로 그림 생성</div>
{''.join(cards) if cards else empty}
</div>
<script>
document.querySelectorAll('.cp').forEach(function(b){{
  b.addEventListener('click', function(){{
    var t=document.getElementById(b.dataset.t); if(!t) return;
    var txt=t.value;
    function ok(){{ var o=b.textContent; b.textContent='복사됨'; b.classList.add('done'); setTimeout(function(){{b.textContent=o;b.classList.remove('done');}},1200); }}
    if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(txt).then(ok,function(){{t.style.position='static';t.style.opacity=1;t.select();document.execCommand('copy');t.style.position='absolute';t.style.opacity=0;ok();}}); }}
    else {{ t.style.position='static';t.style.opacity=1;t.select();document.execCommand('copy');t.style.position='absolute';t.style.opacity=0;ok(); }}
  }});
}});
</script>
</body></html>"""
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n", encoding="utf-8")
    print(f"건강 도우미 생성: {out}/index.html (글 {len(files)}편)")
    return 0


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "site-health"
    sys.exit(build(out_dir))


if __name__ == "__main__":
    main()
