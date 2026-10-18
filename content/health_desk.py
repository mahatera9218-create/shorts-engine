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
SHOW_GENDER = True   # 패션 등 다른 블로그는 build()에서 끈다


def parse(md: str) -> dict:
    """초안 .md 한 편을 조각으로 나눈다.

    새 형식(2026-10-18): 제목은 '후보 여러 개'를 보여 주고 대표가 고른다.
    본문 블록에는 사진 자리([사진N])와 해시태그가 함께 들어 있어 '본문 복사' 한 번으로 다 복사된다.
    이미지 프롬프트는 별도.
    """
    d = {"검증": "", "키워드": "", "대상": "", "후보": [], "추천": "", "본문": "", "이미지": "", "출처": "", "사진확인": ""}
    m = re.search(r"^검증:\s*(.+)$", md, re.M)
    if m:
        d["검증"] = m.group(1).strip()
    m = re.search(r"^키워드:\s*(.+)$", md, re.M)
    if m:
        d["키워드"] = m.group(1).strip()
    # 사진 확인 링크(패션): 가상 모델로 그리니, 대표가 실제 셀럽 착장을 눈으로 확인할 원본 사진 출처 URL
    m = re.search(r"^사진\s*확인\s*[:：]\s*(\S+)", md, re.M)
    if m:
        d["사진확인"] = m.group(1).strip()
    m = re.search(r"^대상:\s*(.+)$", md, re.M)
    if m:
        v = m.group(1).strip()
        d["대상"] = "남성" if v.startswith("남") else ("여성" if v.startswith("여") else "공용")
    else:
        d["대상"] = "공용"

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
    src_rest = (src_split[1] if len(src_split) > 1 else "")
    # 관련글(함께 보면 좋은 글)은 '본문 안'에 들어 있어야 한다(대표 2026-10-18: 따로 주지 말 것).
    # ① 본문에 이미 'http'가 들어간 '제목 | URL' 줄이 있으면 그걸 관련글로 읽는다(복사는 본문에 포함됨).
    d["관련글"] = []
    for ln in d["본문"].splitlines():
        if "|" in ln and "http" in ln:
            title, url = ln.rsplit("|", 1)
            d["관련글"].append((title.strip(" -*·•"), url.strip()))
    # ② (옛 형식 호환) 끝에 '--- 함께 보면 좋은 글 ---' 블록으로 따로 있으면 읽어서 본문 안으로 옮긴다.
    rel_split = re.split(r"^---\s*함께 보면 좋은 글\s*---\s*$", src_rest, maxsplit=1, flags=re.M)
    d["출처"] = rel_split[0].strip()
    if not d["관련글"] and len(rel_split) > 1:
        for ln in rel_split[1].splitlines():
            if "|" in ln and "http" in ln:
                title, url = ln.rsplit("|", 1)
                d["관련글"].append((title.strip(" -*·•"), url.strip()))
        d["본문"] = _inject_related(d["본문"], d["관련글"])
    return d


def _inject_related(body: str, rels: list) -> str:
    """관련글을 본문 해시태그 줄 바로 위에 끼워 넣는다(본문 복사 한 번에 같이 복사되도록)."""
    if not rels or any(u in body for _, u in rels):
        return body
    block = "함께 보면 좋은 글\n" + "\n".join(f"· {t} | {u}" for t, u in rels)
    lines = body.rstrip().split("\n")
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s.startswith("#"):
            idx = i
        elif s:
            break
    if idx is None:
        return body.rstrip() + "\n\n" + block
    before = "\n".join(lines[:idx]).rstrip()
    tags = "\n".join(lines[idx:])
    return before + "\n\n" + block + "\n\n" + tags


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
    sx = d.get("대상") or "공용"
    if SHOW_GENDER:
        sx_color = {"여성": "#c05f8a", "남성": "#3a6ea5", "공용": "#6b645c"}[sx]
        sx_chip = f'<span class="sx" style="background:{sx_color}">{sx}</span>'
        data_sex = f' data-sex="{sx}"'
    else:
        sx_chip = ""
        data_sex = ""
    return (
        f'<section class="card"{data_sex}>'
        f'<div class="head"><span class="kw">{kw}</span>{sx_chip}{badge(d["검증"])}</div>'
        + titles
        + photo_check(d.get("사진확인") or "")
        + box("본문 복사 (사진 위치·관련글·해시태그 포함)", d["본문"])
        + box("이미지 프롬프트 복사 (별도)", d["이미지"], "img")
        + rel_block(d.get("관련글") or [])
        + (f'<details><summary>출처(F목록)</summary><pre>{html.escape(d["출처"])}</pre></details>' if d["출처"] else "")
        + '</section>'
    )


def photo_check(url):
    """사진 확인 링크(패션): 가상 모델 사진이 실제 착장과 맞는지 대표가 눌러서 확인."""
    if not url:
        return ""
    return (
        '<div class="pchk"><span class="plab">실제 사진으로 확인</span>'
        f'<a class="pbtn" href="{html.escape(url)}" target="_blank" rel="noopener">원본 사진 보기</a></div>'
    )


def rel_block(rels):
    """함께 보면 좋은 글: 이미 '본문'에 들어 있으므로(본문 복사에 포함) 여기선 눌러서 미리 확인만."""
    if not rels:
        return ""
    links = "".join(
        f'<div class="rl"><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(t)}</a></div>'
        for t, u in rels
    )
    return (
        '<div class="relwrap"><div class="rlab">함께 보면 좋은 글 '
        '<span class="rnote">(본문에 이미 포함됨 · 눌러서 확인)</span></div>'
        f'{links}</div>'
    )


def build(out_dir: str, drafts_dir: Path | None = None, name: str | None = None,
          show_gender: bool = True) -> int:
    global DRAFTS, NAME, SHOW_GENDER
    if drafts_dir is not None:
        DRAFTS = drafts_dir
    if name is not None:
        NAME = name
    SHOW_GENDER = show_gender
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
    filter_bar = ('<div class="filter">'
                  '<button class="fb on" data-f="전체">전체</button>'
                  '<button class="fb" data-f="여성">여성</button>'
                  '<button class="fb" data-f="남성">남성</button>'
                  '<button class="fb" data-f="공용">공용</button>'
                  '</div>') if SHOW_GENDER else ''
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
.sx{{color:#fff;font-size:11px;padding:3px 9px;border-radius:20px;white-space:nowrap;font-weight:700}}
.filter{{display:flex;gap:8px;margin:0 0 16px;flex-wrap:wrap}}
.fb{{border:1px solid var(--line);background:var(--card);color:var(--ink);font-size:13px;padding:7px 14px;border-radius:20px;cursor:pointer}}
.fb.on{{background:var(--point);color:#fff;border-color:var(--point)}}
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
.relwrap{{margin-top:12px;padding-top:10px;border-top:1px solid var(--line)}}
.rlab{{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);margin-bottom:6px}}
.rlab .cp{{margin-left:auto}}
.rl{{margin:4px 0}}
.rl a{{color:var(--point);font-size:13px;text-decoration:none;line-height:1.4}}
.rnote{{color:var(--muted);font-size:11px;font-weight:400}}
.pchk{{display:flex;align-items:center;gap:8px;margin:10px 0 2px;padding:8px 10px;background:#f0ebe0;border-radius:8px}}
.plab{{font-size:12px;color:var(--muted);flex:1}}
.pbtn{{background:var(--point);color:#fff;font-size:12px;padding:7px 12px;border-radius:9px;text-decoration:none;white-space:nowrap}}
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
{filter_bar}
{''.join(cards) if cards else empty}
</div>
<script>
document.querySelectorAll('.fb').forEach(function(b){{
  b.addEventListener('click', function(){{
    document.querySelectorAll('.fb').forEach(function(x){{x.classList.remove('on');}});
    b.classList.add('on');
    var f=b.dataset.f;
    document.querySelectorAll('.card').forEach(function(c){{
      c.style.display = (f==='전체' || c.dataset.sex===f) ? '' : 'none';
    }});
  }});
}});
document.querySelectorAll('.cp').forEach(function(b){{
  b.addEventListener('click', function(){{
    if(b.id==='mkbtn') return;
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
    (out / "_headers").write_text(
        "/*\n  X-Robots-Tag: noindex, nofollow\n  Cache-Control: no-store, must-revalidate\n",
        encoding="utf-8",
    )
    print(f"건강 도우미 생성: {out}/index.html (글 {len(files)}편)")
    return 0


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "site-health"
    sys.exit(build(out_dir))


if __name__ == "__main__":
    main()
