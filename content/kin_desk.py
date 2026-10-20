"""지식iN 답변 도우미 (대표 2026-10-20).

reports/지식인-답변-queue.md 의 '대기' 초안을 휴대폰용 정적 페이지로 만든다.
질문마다: '질문 열기' 버튼(kin 링크) + '답변 복사' 버튼. 검색엔진 수집 금지(noindex).
고정 주소: https://eok-kin-desk.pages.dev (홈 화면에 추가해 쓴다). Cloudflare Pages.

사용법: python -m content.kin_desk [출력 폴더, 기본 site-kin]
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from market.common import ROOT

QUEUE = ROOT / "reports" / "지식인-답변-queue.md"
KST = ZoneInfo("Asia/Seoul")


def parse(md: str) -> list[dict]:
    """'## 대기 중인 초안' 아래의 카드들을 파싱. 상태가 '대기'인 것만 반환."""
    m = re.search(r"##\s*대기 중인 초안\s*(.*)$", md, re.S)
    body = m.group(1) if m else md
    cards = []
    for block in re.split(r"(?m)^##\s+", body):
        block = block.strip()
        if not block or block.startswith("대기 중인 초안"):
            continue
        title = block.splitlines()[0].strip()
        link = (re.search(r"^-\s*바로가기\s*[:：]\s*(\S+)", block, re.M) or [None, ""])[1]
        state = (re.search(r"^-\s*상태\s*[:：]\s*(\S+)", block, re.M) or [None, ""])[1]
        dm = re.search(r"^-\s*답변\s*초안\s*[:：]\s*(.*?)(?=^-\s*상태\s*[:：])", block, re.S | re.M)
        draft = (dm.group(1) if dm else "").strip()
        draft = re.sub(r"(?m)^\s{2,}", "", draft)  # 들여쓰기 제거
        if state == "대기" and draft:
            cards.append({"title": title, "link": link, "draft": draft})
    return cards


PAGE = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<meta name=robots content="noindex,nofollow"><title>지식iN 답변 도우미</title>
<style>
:root{{color-scheme:light}}
body{{margin:0;background:#f7f3ea;color:#2b2622;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;padding:16px}}
h1{{font-size:19px;margin:4px 0 2px}}
.sub{{color:#8a7f72;font-size:13px;margin:0 0 16px}}
.card{{background:#fff;border:1px solid #eadfce;border-radius:14px;padding:14px;margin:0 0 14px}}
.q{{font-weight:700;font-size:15px;margin:0 0 10px;word-break:keep-all}}
.draft{{white-space:pre-wrap;background:#faf6ee;border:1px solid #eee3d2;border-radius:10px;padding:11px;font-size:14px;margin:0 0 10px}}
.row{{display:flex;gap:8px}}
a.btn,button.btn{{flex:1;text-align:center;border:0;border-radius:10px;padding:12px;font-size:15px;font-weight:600;text-decoration:none;cursor:pointer}}
.open{{background:#2f6f4e;color:#fff}}
.copy{{background:#c0603a;color:#fff}}
.copy.done{{background:#2f6f4e}}
.empty{{color:#8a7f72;text-align:center;padding:40px 0}}
.tip{{font-size:12px;color:#8a7f72;margin:14px 2px 0;line-height:1.5}}
</style></head><body>
<h1>지식iN 답변 도우미</h1>
<p class=sub>{when} 기준 · 대기 {n}건 · 하루 2~3개만 띄엄띄엄 게시</p>
{cards}
<p class=tip>① ‘질문 열기’로 질문 확인 → ② ‘답변 복사’ → ③ 지식iN에 붙여넣고 게시.<br>
같은 링크 반복·한 번에 몰아서 게시는 금지(스팸). 숫자 애매하면 공단·국세청 확인 문구는 그대로 두세요.</p>
<script>
function cp(id,b){{
 var t=document.getElementById(id).innerText;
 function ok(){{b.classList.add('done');b.textContent='복사됨';setTimeout(function(){{b.classList.remove('done');b.textContent='답변 복사';}},1500);}}
 if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(ok,function(){{fb();}});}}else{{fb();}}
 function fb(){{var r=document.createRange();r.selectNodeContents(document.getElementById(id));var s=getSelection();s.removeAllRanges();s.addRange(r);try{{document.execCommand('copy');ok();}}catch(e){{}}s.removeAllRanges();}}
}}
</script></body></html>"""

CARD = """<div class=card>
<p class=q>{title}</p>
<div class=draft id="d{i}">{draft}</div>
<div class=row>
{open}
<button class="btn copy" onclick="cp('d{i}',this)">답변 복사</button>
</div></div>"""


def build(out_dir: str = "site-kin") -> Path:
    md = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else ""
    cards = parse(md)
    when = datetime.now(KST).strftime("%m/%d %H:%M")
    if cards:
        blocks = []
        for i, c in enumerate(cards):
            openbtn = (f'<a class="btn open" href="{html.escape(c["link"])}" target="_blank" rel="noopener">질문 열기</a>'
                       if c["link"] else '<span class="btn open" style="opacity:.5">링크 없음</span>')
            blocks.append(CARD.format(i=i, title=html.escape(c["title"]),
                                      draft=html.escape(c["draft"]), open=openbtn))
        cards_html = "\n".join(blocks)
    else:
        cards_html = '<p class=empty>대기 중인 초안이 없습니다.<br>9·12·16시에 자동으로 채워집니다.</p>'
    page = PAGE.format(when=when, n=len(cards), cards=cards_html)
    d = ROOT / out_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page, encoding="utf-8")
    (d / "_headers").write_text("/*\n  X-Robots-Tag: noindex\n  Cache-Control: no-cache\n", encoding="utf-8")
    print(f"지식iN 도우미 생성: {out_dir}/index.html (대기 {len(cards)}건)")
    return d


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "site-kin")
