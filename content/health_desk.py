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
    """초안 .md 한 편을 조각으로 나눈다."""
    d = {"검증": "", "키워드": "", "제목": "", "본문": "", "해시태그": "", "이미지": "", "출처": ""}
    m = re.search(r"^검증:\s*(.+)$", md, re.M)
    if m:
        d["검증"] = m.group(1).strip()
    m = re.search(r"^키워드:\s*(.+)$", md, re.M)
    if m:
        d["키워드"] = m.group(1).strip()
    m = re.search(r"^제목\(선정\):\s*(.+)$", md, re.M)
    if m:
        d["제목"] = m.group(1).strip()

    # 첫 '---' 이후 ~ '--- 이미지 프롬프트 ---' 전 = 발행 본문 블록(제목줄+본문+해시태그)
    body_block = ""
    parts = re.split(r"^---\s*$", md, maxsplit=1, flags=re.M)
    rest = parts[1] if len(parts) > 1 else md
    img_split = re.split(r"^---\s*이미지 프롬프트\s*---\s*$", rest, maxsplit=1, flags=re.M)
    body_block = img_split[0]
    after_img = img_split[1] if len(img_split) > 1 else ""
    src_split = re.split(r"^---\s*출처.*?---\s*$", after_img, maxsplit=1, flags=re.M)
    d["이미지"] = src_split[0].strip()
    d["출처"] = (src_split[1].strip() if len(src_split) > 1 else "")

    # 본문 블록에서 제목줄·해시태그 분리
    lines = [ln.rstrip() for ln in body_block.strip("\n").split("\n")]
    # 해시태그 = '#'로 시작하는 마지막 줄
    tag_idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith("#")), None)
    if tag_idx is not None:
        d["해시태그"] = lines[tag_idx].strip()
        lines = lines[:tag_idx]
    # 첫 비어있지 않은 줄 = 제목(제목(선정) 못 찾았을 때 대비)
    body_lines = lines[:]
    while body_lines and not body_lines[0].strip():
        if not d["제목"]:
            break
        body_lines.pop(0)
    if not d["제목"]:
        first = next((i for i, ln in enumerate(body_lines) if ln.strip()), None)
        if first is not None:
            d["제목"] = body_lines[first].strip()
            body_lines = body_lines[first + 1:]
    else:
        # 본문에서 중복 제목줄 한 번 제거
        fn = next((i for i, ln in enumerate(body_lines) if ln.strip()), None)
        if fn is not None and body_lines[fn].strip() == d["제목"]:
            body_lines = body_lines[fn + 1:]
    d["본문"] = "\n".join(body_lines).strip("\n")
    return d


def badge(v: str) -> str:
    key = "확인됨" if v.startswith("확인됨") else ("미확인" if v.startswith("미확인") else "부분확인")
    color = {"확인됨": "#2e7d52", "부분확인": "#b7791f", "미확인": "#b5482f"}[key]
    return f'<span class="badge" style="background:{color}">검증 {html.escape(key)}</span>'


def card(d: dict, fname: str) -> str:
    def box(label, text, cls=""):
        if not text:
            return ""
        tid = f"t_{abs(hash(label+fname))%10**8}"
        return (
            f'<div class="row {cls}"><div class="lab">{html.escape(label)}</div>'
            f'<button class="cp" data-t="{tid}">복사</button>'
            f'<textarea id="{tid}" readonly>{html.escape(text)}</textarea></div>'
        )
    kw = html.escape(d["키워드"] or "(키워드 미상)")
    return (
        '<section class="card">'
        f'<div class="head"><span class="kw">{kw}</span>{badge(d["검증"])}</div>'
        f'<div class="title">{html.escape(d["제목"])}</div>'
        + box("제목 복사", d["제목"])
        + box("본문 복사", d["본문"])
        + box("해시태그 복사", d["해시태그"])
        + box("이미지 프롬프트 복사", d["이미지"], "img")
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
.cp{{border:0;background:var(--point);color:#fff;font-size:13px;padding:8px 14px;border-radius:9px;cursor:pointer}}
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
<div class="sub">{now} 기준 · 글 {len(files)}편 · 순서: 제목→본문→해시태그 복사해 네이버에 붙이고, 이미지 프롬프트로 그림 생성</div>
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
