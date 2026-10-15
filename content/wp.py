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
import tempfile
from pathlib import Path

import requests

from market.common import ROOT, missing_secrets, secret

TITLE_RE = re.compile(r"^제목\s*[:：]\s*(.+)$")
SLUG_RE = re.compile(r"^슬러그\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9-]*)$")
CATEGORY_RE = re.compile(r"^분류\s*[:：]\s*([A-Za-z0-9-]+)$")
# 카테고리 slug → 표시 이름 (세무 클러스터). 발행 시 WP 카테고리를 만들어 붙인다.
CAT_NAMES = {
    "realty": "부동산·상속 세금",
    "saving": "절세·연금",
    "life": "생활·4대보험",
}
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ORDERED_RE = re.compile(r"^\d+\.\s+(.+)$")
BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
# 본문에 그림을 넣는 자리표: 한 줄에 [[도식:세율표]] 또는 [[도식:계산:60000000]]
FIGURE_RE = re.compile(r"^\[\[도식:([^\]]+)\]\]$")


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
    # 제목 바로 뒤의 '슬러그:'·'분류:' 줄·구분선(---)·빈 줄은 본문에서 뺀다.
    body_lines = lines[start:]
    while body_lines and (not body_lines[0].strip() or body_lines[0].strip() == "---"
                          or SLUG_RE.match(body_lines[0].strip())
                          or CATEGORY_RE.match(body_lines[0].strip())):
        body_lines.pop(0)
    return title, "\n".join(body_lines).strip()


def draft_slug(path: Path) -> str | None:
    """초안 윗부분의 '슬러그: xxx' 줄에서 slug를 읽는다(없으면 None)."""
    for line in path.read_text(encoding="utf-8").splitlines()[:6]:
        m = SLUG_RE.match(line.strip())
        if m:
            return m.group(1)
    return None


def draft_category(path: Path) -> str | None:
    """초안 윗부분의 '분류: realty|saving|life' 줄에서 카테고리 slug를 읽는다."""
    for line in path.read_text(encoding="utf-8").splitlines()[:6]:
        m = CATEGORY_RE.match(line.strip())
        if m and m.group(1) in CAT_NAMES:
            return m.group(1)
    return None


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


def md_to_html(md: str, images: dict[str, str] | None = None) -> str:
    """초안 본문 마크다운을 워드프레스용 HTML로.

    표·목록·문단·굵게·구분선·인용(>)·그림 자리표를 처리한다.
    images: 그림 토큰("세율표" 등) → <figure> HTML. 없으면 자리표를 안내 문구로 남긴다.
    """
    images = images or {}
    lines = md.splitlines()
    html_parts: list[str] = []
    i = 0
    n = len(lines)
    list_buf: list[str] = []
    list_kind = ""
    quote_buf: list[str] = []

    def flush_quote():
        nonlocal quote_buf
        if quote_buf:
            inner = "".join(f"<p>{x}</p>" for x in quote_buf)
            html_parts.append(
                '<blockquote class="wp-block-quote" style="border-left:4px solid #f5be28;'
                'background:#fafafa;margin:1.5em 0;padding:1em 1.25em;border-radius:4px;">'
                f"{inner}</blockquote>")
            quote_buf = []

    def flush():
        """목록·인용 블록을 모두 닫는다."""
        flush_list()
        flush_quote()

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
        # 그림 자리표: [[도식:세율표]]
        mf = FIGURE_RE.match(stripped)
        if mf:
            flush()
            token = mf.group(1).strip()
            html_parts.append(images.get(token, f'<p><em>[도식: {html.escape(token)} — 발행 시 생성·삽입]</em></p>'))
            i += 1
            continue
        # 표: |로 시작하는 줄이 이어지는 구간
        if stripped.startswith("|"):
            flush()
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                html_parts.append(_table(block))
            continue
        # 인용/요약 박스: > 로 시작하는 줄
        if stripped.startswith(">"):
            flush_list()
            quote_buf.append(_inline(stripped.lstrip(">").strip()))
            i += 1
            continue
        if not stripped:
            flush()
            i += 1
            continue
        if stripped == "---":
            flush()
            html_parts.append("<hr/>")
            i += 1
            continue
        if stripped.startswith("### "):
            flush()
            html_parts.append(f"<h3>{_inline(stripped[4:])}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            flush()
            html_parts.append(f"<h2>{_inline(stripped[3:])}</h2>")
            i += 1
            continue
        if stripped.startswith("# "):
            flush()
            html_parts.append(f"<h2>{_inline(stripped[2:])}</h2>")  # H1은 제목이 쓰므로 본문은 H2로
            i += 1
            continue
        mo = ORDERED_RE.match(stripped)
        if mo:
            flush_quote()
            if list_kind and list_kind != "ol":
                flush_list()
            list_kind = "ol"
            list_buf.append(_inline(mo.group(1)))
            i += 1
            continue
        mb = BULLET_RE.match(stripped)
        if mb:
            flush_quote()
            if list_kind and list_kind != "ul":
                flush_list()
            list_kind = "ul"
            list_buf.append(_inline(mb.group(1)))
            i += 1
            continue
        flush()
        html_parts.append(f"<p>{_inline(stripped)}</p>")
        i += 1
    flush()
    return "\n".join(html_parts)


# ---------------------------------------------------------------- 그림(도식) 생성

def figure_tokens(md: str) -> list[str]:
    """본문에서 그림 자리표 토큰을 등장 순서대로 (중복 제거) 뽑는다."""
    out: list[str] = []
    for line in md.splitlines():
        m = FIGURE_RE.match(line.strip())
        if m:
            tok = m.group(1).strip()
            if tok not in out:
                out.append(tok)
    return out


def _figure_alt(token: str) -> str:
    if token == "세율표":
        return "2026년 종합소득세 과세표준 구간별 세율·누진공제 표"
    if token.startswith("계산:"):
        return "종합소득세 산출세액 계산 예시"
    return token


def render_figure(token: str, out_dir: Path) -> Path:
    """토큰에 맞는 도식 PNG를 만든다. (세율표 / 계산:<금액>)"""
    from content import tax_cards  # 무거운 Pillow 로드는 필요할 때만
    out_dir.mkdir(parents=True, exist_ok=True)
    if token == "세율표":
        return tax_cards.rate_table_card(out_dir / "sodeukse-yulpyo-2026.png")
    if token.startswith("계산:"):
        base = int(re.sub(r"[^\d]", "", token.split(":", 1)[1]))
        return tax_cards.calc_card(out_dir / f"sodeukse-gyesan-{base}.png", base)
    raise ValueError(f"모르는 도식 토큰: {token}")


# ---------------------------------------------------------------- 발행

def _api_base() -> str:
    url = (secret("WP_URL") or "").rstrip("/")
    return f"{url}/wp-json/wp/v2"


def _auth() -> dict:
    user = secret("WP_USER") or ""
    pw = (secret("WP_APP_PASSWORD") or "").replace(" ", "")  # 앱 비번의 공백은 무시해도 됨
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _auth_header() -> dict:
    return {**_auth(), "Content-Type": "application/json"}


def upload_image(path: Path, *, alt: str = "") -> dict:
    """그림을 워드프레스 미디어에 올린다. {id, source_url}을 돌려준다."""
    data = Path(path).read_bytes()
    headers = {
        **_auth(),
        "Content-Type": "image/png",
        "Content-Disposition": f'attachment; filename="{Path(path).name}"',
    }
    endpoint = f"{_api_base()}/media"
    try:
        resp = requests.post(endpoint, headers=headers, data=data, timeout=60)
    except requests.RequestException as e:
        raise RuntimeError(f"워드프레스 그림 업로드 연결 실패: {type(e).__name__}") from None
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"그림 업로드 실패 HTTP {resp.status_code}: {resp.text[:200]}")
    media = resp.json()
    mid = media.get("id")
    # 대체텍스트(alt)는 SEO·접근성·애드센스 심사에 중요 → 따로 채워 준다.
    if mid and alt:
        try:
            requests.post(f"{endpoint}/{mid}", headers=_auth_header(),
                          json={"alt_text": alt}, timeout=30)
        except requests.RequestException:
            pass
    return {"id": mid, "source_url": media.get("source_url")}


def published_today_kst() -> int:
    """오늘(KST) '공개'된 글 수. 드립 하루 상한 체크용. 실패 시 0."""
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    try:
        r = requests.get(f"{_api_base()}/posts",
                         params={"per_page": 50, "status": "publish", "orderby": "date",
                                 "order": "desc", "_fields": "date"}, timeout=20)
    except requests.RequestException:
        return 0
    if r.status_code != 200:
        return 0
    return sum(1 for p in r.json() if str(p.get("date", ""))[:10] == today)


def existing_slugs() -> set[str]:
    """이미 올라간 글(공개·초안·대기·예약 포함)의 slug 집합. 중복 발행 방지용."""
    try:
        r = requests.get(f"{_api_base()}/posts",
                         params={"per_page": 100, "status": "publish,draft,pending,future",
                                 "_fields": "slug"}, headers=_auth(), timeout=20)
    except requests.RequestException:
        return set()
    if r.status_code != 200:
        return set()
    return {p.get("slug", "") for p in r.json() if p.get("slug")}


def ensure_category(slug: str) -> int | None:
    """카테고리 slug에 해당하는 WP 카테고리 id. 없으면 만들어서 돌려준다."""
    name = CAT_NAMES.get(slug)
    if not name:
        return None
    base = _api_base()
    try:
        r = requests.get(f"{base}/categories", params={"slug": slug, "_fields": "id,slug"},
                         headers=_auth(), timeout=20)
        if r.status_code == 200 and r.json():
            return r.json()[0].get("id")
        c = requests.post(f"{base}/categories", headers=_auth_header(),
                          json={"name": name, "slug": slug}, timeout=20)
        if c.status_code in (200, 201):
            return c.json().get("id")
    except requests.RequestException:
        return None
    return None


def _figure_html(source_url: str, alt: str) -> str:
    cap = html.escape(alt)
    return ('<figure class="wp-block-image size-large" style="margin:1.5em 0;text-align:center;">'
            f'<img src="{html.escape(source_url)}" alt="{cap}" loading="lazy" '
            'style="max-width:100%;height:auto;border-radius:8px;"/>'
            f'<figcaption style="color:#777;font-size:0.9em;margin-top:0.5em;">{cap}</figcaption>'
            '</figure>')


def publish(title: str, content_html: str, *, status: str = "draft",
            slug: str | None = None, excerpt: str | None = None,
            featured_media: int | None = None, kind: str = "post",
            categories: list[int] | None = None) -> dict:
    """WP REST로 글(post) 또는 페이지(page)를 올린다. 성공하면 {id, link, status}.

    비밀 값은 넣지 않는다. 오류에도 URL 경로까지만 남긴다.
    """
    payload: dict = {"title": title, "content": content_html, "status": status}
    if slug:
        payload["slug"] = slug
    if excerpt:
        payload["excerpt"] = excerpt
    if featured_media:
        payload["featured_media"] = featured_media
    if categories:
        payload["categories"] = categories
    endpoint = f"{_api_base()}/{'pages' if kind == 'page' else 'posts'}"
    try:
        resp = requests.post(endpoint, headers=_auth_header(), json=payload, timeout=30)
    except requests.RequestException as e:
        raise RuntimeError(f"워드프레스 연결 실패: {type(e).__name__}") from None
    if resp.status_code not in (200, 201):
        # 응답 본문에 민감정보는 없지만, 길이를 제한해 둔다.
        raise RuntimeError(f"워드프레스 발행 실패 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return {"id": data.get("id"), "link": data.get("link"), "status": data.get("status")}


def publish_file(path: Path, *, status: str = "draft", slug: str | None = None,
                 kind: str = "post", verbose: bool = False) -> dict:
    """초안 .md 한 편을 통째로 발행: 파싱 → 도식 생성·업로드·삽입 → WP 발행.

    도식 생성·업로드가 필요하므로 비밀 값(WORDPRESS)이 있어야 한다. 결과 dict 반환.
    """
    title, body = parse_draft(path)
    tokens = figure_tokens(body)
    images: dict[str, str] = {}
    featured_media: int | None = None
    tmp = Path(tempfile.mkdtemp(prefix="wp_fig_"))
    if tokens:
        for tok in tokens:
            png = render_figure(tok, tmp)
            alt = _figure_alt(tok)
            up = upload_image(png, alt=alt)
            images[tok] = _figure_html(up["source_url"], alt)
            if featured_media is None and up.get("id"):
                featured_media = up["id"]
            if verbose:
                print(f"[도식 업로드] {tok} → media #{up.get('id')}")
    # 대표 이미지가 없으면(글·페이지 공통) 제목 표지 카드를 코드로 만들어 썸네일로 쓴다.
    if featured_media is None and kind == "post":
        from content import tax_cards
        cover = tax_cards.cover_card(tmp / "cover.png", title)
        up = upload_image(cover, alt=title)
        if up.get("id"):
            featured_media = up["id"]
            if verbose:
                print(f"[표지 업로드] media #{up.get('id')}")
    content_html = md_to_html(body, images)
    categories = None
    if kind == "post":
        cat_slug = draft_category(path)
        cid = ensure_category(cat_slug) if cat_slug else None
        if cid:
            categories = [cid]
    return publish(title, content_html, status=status, slug=slug,
                   featured_media=featured_media, kind=kind, categories=categories)


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="워드프레스(구글 블로그) 발행")
    ap.add_argument("--file", required=True, help="초안 .md 경로 (제목: ... 로 시작)")
    ap.add_argument("--status", choices=["draft", "publish"], default="draft",
                    help="draft=워드프레스 초안(기본), publish=바로 공개(대표 지시 때만)")
    ap.add_argument("--slug", default=None, help="주소 slug (없으면 워드프레스가 자동)")
    ap.add_argument("--type", choices=["post", "page"], default="post",
                    help="post=글(기본), page=고정 페이지(개인정보·약관 등)")
    ap.add_argument("--dry-run", action="store_true", help="올리지 않고 제목·HTML만 출력")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2

    title, body = parse_draft(path)
    tokens = figure_tokens(body)

    if args.dry_run:
        # 올리지 않지만 도식은 실제로 그려 봐서(오류 걸러내기) 로컬 경로를 보여 준다.
        tmp = Path(tempfile.mkdtemp(prefix="wp_fig_"))
        for tok in tokens:
            try:
                p = render_figure(tok, tmp)
                print(f"[도식] {tok} → {p} ({p.stat().st_size} bytes)")
            except Exception as e:  # noqa: BLE001
                print(f"[도식 실패] {tok}: {e}", file=sys.stderr)
        content_html = md_to_html(body)
        print(f"\n[제목] {title}\n[상태] {args.status} (dry-run, 올리지 않음)\n")
        print(content_html)
        return 0

    missing = missing_secrets("wordpress")
    if missing:
        print("워드프레스 비밀 값이 없다: " + ", ".join(missing)
              + "\n→ GitHub Secrets에 WP_URL·WP_USER·WP_APP_PASSWORD를 넣어야 한다.", file=sys.stderr)
        return 3

    result = publish_file(path, status=args.status, slug=args.slug, kind=args.type, verbose=True)
    kind_label = "페이지" if args.type == "page" else "글"
    where = f"{kind_label} 초안으로 올림(워드프레스에서 검토 후 공개)" if result["status"] == "draft" else f"{kind_label} 공개됨"
    print(f"[완료] {where}\n  제목: {title}\n  글 번호: {result['id']}\n  주소: {result['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
