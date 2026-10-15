"""워드프레스(구글 블로그) 발행: 초안 .md → HTML → WP REST API로 올린다.

- 발행 통로는 WP REST API(/wp-json/wp/v2/posts) + 애플리케이션 비밀번호(기본 인증)다.
  비밀 값(WP_URL·WP_USER·WP_APP_PASSWORD)은 GitHub Secrets → 워크플로 env로만 받는다.
  값 자체는 코드·로그·오류 메시지에 절대 넣지 않는다.
- 기본은 status="draft"다. 글은 워드프레스에 '초안'으로만 올라가고, 바깥 공개(발행)는
  대표가 워드프레스에서 직접 '공개' 버튼을 누른다 (원칙: 외부 공개는 대표 버튼).
- 초안 형식: 첫 줄 "제목: ...", 그 아래 본문(마크다운). reports/구글글-초안/*.md.

사용법:
    python -m content.wp --file reports/구글글-초안/01-소득세율표.md            # 초안으로 올림
    python -m content.wp --file <경로> --status publish                        # 바로 공개(대표 지시 때만)
    python -m content.wp --file <경로> --dry-run                               # 올리지 않고 HTML만 확인
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from pathlib import Path

import requests

from market.common import ROOT, missing_secrets, secret

TITLE_RE = re.compile(r"^제목\s*[:：]\s*(.+)$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ORDERED_RE = re.compile(r"^\d+\.\s+(.+)$")
BULLET_RE = re.compile(r"^[-*]\s+(.+)$")


# ---------------------------------------------------------------- 초안 읽기

def parse_draft(path: Path) -> tuple[str, str]:
    """초안 .md를 (제목, 본문 마크다운)으로 가른다. 첫 '제목:' 줄이 제목이다."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = ""
    start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = TITLE_RE.match(line.strip())
        if m:
            title = m.group(1).strip()
            start = i + 1
        break
    if not title:
        raise ValueError(f"초안 첫 줄에 '제목: ...'이 없다: {path}")
    # 제목 바로 뒤의 구분선(---)·빈 줄은 본문에서 뺀다.
    body_lines = lines[start:]
    while body_lines and (not body_lines[0].strip() or body_lines[0].strip() == "---"):
        body_lines.pop(0)
    return title, "\n".join(body_lines).strip()


# ---------------------------------------------------------------- 마크다운 → HTML

def _inline(text: str) -> str:
    """한 줄 안의 서식(굵게)만 처리하고 나머지는 이스케이프한다."""
    out = []
    pos = 0
    for m in BOLD_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        out.append("<strong>" + html.escape(m.group(1)) + "</strong>")
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def _table(block: list[str]) -> str:
    """| a | b | 형식의 표를 <table>로. 둘째 줄(---)은 구분선이다."""
    rows = [[c.strip() for c in row.strip().strip("|").split("|")] for row in block]
    head, body = rows[0], rows[2:] if len(rows) > 2 else []
    out = ["<figure class=\"wp-block-table\"><table>"]
    out.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead>")
    if body:
        out.append("<tbody>")
        for r in body:
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
        out.append("</tbody>")
    out.append("</table></figure>")
    return "".join(out)


def md_to_html(md: str) -> str:
    """초안 본문 마크다운을 워드프레스용 HTML로. (제목·표·목록·문단·굵게·구분선)"""
    lines = md.splitlines()
    html_parts: list[str] = []
    i = 0
    n = len(lines)
    list_buf: list[str] = []
    list_kind = ""

    def flush_list():
        nonlocal list_buf, list_kind
        if list_buf:
            tag = "ol" if list_kind == "ol" else "ul"
            html_parts.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in list_buf) + f"</{tag}>")
            list_buf = []
            list_kind = ""

    while i < n:
        line = lines[i]
        stripped = line.strip()
        # 표: |로 시작하는 줄이 이어지는 구간
        if stripped.startswith("|"):
            flush_list()
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                html_parts.append(_table(block))
            continue
        if not stripped:
            flush_list()
            i += 1
            continue
        if stripped == "---":
            flush_list()
            html_parts.append("<hr/>")
            i += 1
            continue
        if stripped.startswith("### "):
            flush_list()
            html_parts.append(f"<h3>{_inline(stripped[4:])}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            flush_list()
            html_parts.append(f"<h2>{_inline(stripped[3:])}</h2>")
            i += 1
            continue
        if stripped.startswith("# "):
            flush_list()
            html_parts.append(f"<h2>{_inline(stripped[2:])}</h2>")  # H1은 제목이 쓰므로 본문은 H2로
            i += 1
            continue
        mo = ORDERED_RE.match(stripped)
        if mo:
            if list_kind and list_kind != "ol":
                flush_list()
            list_kind = "ol"
            list_buf.append(_inline(mo.group(1)))
            i += 1
            continue
        mb = BULLET_RE.match(stripped)
        if mb:
            if list_kind and list_kind != "ul":
                flush_list()
            list_kind = "ul"
            list_buf.append(_inline(mb.group(1)))
            i += 1
            continue
        flush_list()
        html_parts.append(f"<p>{_inline(stripped)}</p>")
        i += 1
    flush_list()
    return "\n".join(html_parts)


# ---------------------------------------------------------------- 발행

def _api_base() -> str:
    url = (secret("WP_URL") or "").rstrip("/")
    return f"{url}/wp-json/wp/v2"


def _auth_header() -> dict:
    user = secret("WP_USER") or ""
    pw = (secret("WP_APP_PASSWORD") or "").replace(" ", "")  # 앱 비번의 공백은 무시해도 됨
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def publish(title: str, content_html: str, *, status: str = "draft",
            slug: str | None = None, excerpt: str | None = None) -> dict:
    """WP REST로 글을 올린다. 성공하면 {id, link, status}를, 실패하면 설명과 함께 예외.

    비밀 값은 넣지 않는다. 오류에도 URL 경로까지만 남긴다.
    """
    payload: dict = {"title": title, "content": content_html, "status": status}
    if slug:
        payload["slug"] = slug
    if excerpt:
        payload["excerpt"] = excerpt
    endpoint = f"{_api_base()}/posts"
    try:
        resp = requests.post(endpoint, headers=_auth_header(), json=payload, timeout=30)
    except requests.RequestException as e:
        raise RuntimeError(f"워드프레스 연결 실패: {type(e).__name__}") from None
    if resp.status_code not in (200, 201):
        # 응답 본문에 민감정보는 없지만, 길이를 제한해 둔다.
        raise RuntimeError(f"워드프레스 발행 실패 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return {"id": data.get("id"), "link": data.get("link"), "status": data.get("status")}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="워드프레스(구글 블로그) 발행")
    ap.add_argument("--file", required=True, help="초안 .md 경로 (제목: ... 로 시작)")
    ap.add_argument("--status", choices=["draft", "publish"], default="draft",
                    help="draft=워드프레스 초안(기본), publish=바로 공개(대표 지시 때만)")
    ap.add_argument("--slug", default=None, help="주소 slug (없으면 워드프레스가 자동)")
    ap.add_argument("--dry-run", action="store_true", help="올리지 않고 제목·HTML만 출력")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2

    title, body = parse_draft(path)
    content_html = md_to_html(body)

    if args.dry_run:
        print(f"[제목] {title}\n[상태] {args.status} (dry-run, 올리지 않음)\n")
        print(content_html)
        return 0

    missing = missing_secrets("wordpress")
    if missing:
        print("워드프레스 비밀 값이 없다: " + ", ".join(missing)
              + "\n→ GitHub Secrets에 WP_URL·WP_USER·WP_APP_PASSWORD를 넣어야 한다.", file=sys.stderr)
        return 3

    result = publish(title, content_html, status=args.status, slug=args.slug)
    where = "초안으로 올림(워드프레스에서 검토 후 공개)" if result["status"] == "draft" else "공개됨"
    print(f"[완료] {where}\n  제목: {title}\n  글 번호: {result['id']}\n  주소: {result['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
