"""저장소 발행기: 대기 초안을 '사이트가 직접 읽는 글 파일'로 바꾼다(워드프레스 불필요).

- 큐: reports/구글글-초안/*.md  (제목/슬러그/분류 머리글 + 마크다운 본문)
- 결과: web/content/posts/<slug>.md  (frontmatter + 변환된 HTML 본문)
- 이미 발행된 slug(web/content/posts/에 파일 있음)는 건너뛴다 → 중복 방지.
- 하루 상한 2편(오전 1·오후 1) 안에서 구간당 1편 발행. 초안 머리글 '검증:'이 확인됨/부분확인이 아니면 발행하지 않는다. --force면 상한 무시. --max N 으로 여러 편(초기 씨딩).
- 도식(그림) 토큰은 이미지 호스팅이 없어 본문에서 제거한다. 진짜 데이터 표(<table>)는 그대로 유지.
- 대표 사진은 사이트가 주제별 실사진(Unsplash)으로 자동 표시한다(발행기는 신경 쓰지 않는다).

워드프레스 비밀 값이 필요 없다(순수 파일 작업). 커밋·푸시는 워크플로에서 한다.

사용법:
    python -m content.publish_fs                 # 하루 상한 안이면 1편 발행
    python -m content.publish_fs --force         # 상한 무시하고 1편
    python -m content.publish_fs --force --max 6 # 대기분 여러 편 한꺼번에(초기 씨딩)
    python -m content.publish_fs --dry-run       # 다음 대상만 출력
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market.common import ROOT
from content import wp

QUEUE = ROOT / "reports" / "구글글-초안"
PAGES_SRC = ROOT / "reports" / "구글-페이지"
POSTS_OUT = ROOT / "web" / "content" / "posts"
PAGES_OUT = ROOT / "web" / "content" / "pages"
KST = timezone(timedelta(hours=9))


def daily_max() -> int:
    """하루 발행 상한 5편(2026-10-18 대표 결정: 본진 글 수 증량). 구간 5개에 1편씩, 하루 종일 퍼지게."""
    return 5


# KST 시각을 5개 구간으로 나눠, 구간마다 1편만 나가게 한다(하루 5편, 자연스럽게 분산).
# s1 아침(<10) · s2 오전(10~11) · s3 점심(12~14) · s4 오후(15~17) · s5 저녁(≥18)
def slot_of(hour: int) -> str:
    if hour < 10:
        return "s1"
    if hour < 12:
        return "s2"
    if hour < 15:
        return "s3"
    if hour < 18:
        return "s4"
    return "s5"


def slot_filled(now: datetime | None = None) -> bool:
    """지금 구간에 오늘 이미 발행된 글이 있는가. 구간마다 1편만 나가게 한다."""
    now = now or datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    cur = slot_of(now.hour)
    for f in POSTS_OUT.glob("*.md") if POSTS_OUT.exists() else []:
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})T(\d{2})", f.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) == today and slot_of(int(m.group(2))) == cur:
            return True
    return False


def draft_verification(path: Path) -> str:
    """초안 윗부분의 '검증: 확인됨|부분확인|미확인' 줄. 줄이 없으면 '미확인'으로 본다(검증 전 발행 금지)."""
    for line in path.read_text(encoding="utf-8").splitlines()[:8]:
        m = re.match(r"^검증:\s*(\S+)", line.strip())
        if m:
            return m.group(1)
    return "미확인"


def is_publishable(path: Path) -> bool:
    return draft_verification(path) in ("확인됨", "부분확인")


def publish_pages() -> int:
    """고정 페이지(개인정보·약관·면책·연락처·소개)를 사이트용으로 변환. 파일 이름=slug."""
    if not PAGES_SRC.exists():
        return 0
    PAGES_OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(PAGES_SRC.glob("*.md")):
        slug = f.stem
        title, body = wp.parse_draft(f)
        html = wp.md_to_html(body)
        one = lambda s: re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()
        front = f"---\ntitle: {one(title)}\nslug: {slug}\n---\n"
        (PAGES_OUT / f"{slug}.md").write_text(front + html + "\n", encoding="utf-8")
        n += 1
    print(f"고정 페이지 {n}개 변환.")
    return n


def published_slugs() -> set[str]:
    """이미 발행된 글의 slug(파일 이름 기준)."""
    if not POSTS_OUT.exists():
        return set()
    return {f.stem for f in POSTS_OUT.glob("*.md")}


def published_today() -> int:
    """오늘(KST) 발행된 글 수. frontmatter의 date 기준."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    n = 0
    for f in POSTS_OUT.glob("*.md") if POSTS_OUT.exists() else []:
        m = re.search(r"^date:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
        if m and m.group(1)[:10] == today:
            n += 1
    return n


def next_draft(existing: set[str]) -> tuple[Path | None, str | None]:
    for f in sorted(QUEUE.glob("*.md")):
        slug = wp.draft_slug(f)
        if not slug or slug in existing:
            continue
        if not is_publishable(f):
            print(f"[보류] {f.name}: 숫자 검증 전('검증:' 줄이 없거나 미확인)")
            continue
        return f, slug
    return None, None


def make_excerpt(body: str, limit: int = 150) -> str:
    """본문 첫 문단에서 요약 한 줄(마크다운·공백 제거)."""
    for block in re.split(r"\n\s*\n", body.strip()):
        line = block.strip()
        if not line or line.startswith(("#", "|", ">", "-", "*", "[[")) or line[:2].isdigit():
            continue
        text = re.sub(r"[*_`#>]", "", line)
        text = re.sub(r"\[\[도식:[^\]]+\]\]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text[:limit]
    return ""


def publish_one(path: Path, slug: str) -> Path:
    title, body = wp.parse_draft(path)
    # 도식(그림) 토큰 제거 — 이미지 호스팅이 없으므로. 진짜 표는 본문에 그대로 남는다.
    for tok in wp.figure_tokens(body):
        body = re.sub(r"[ \t]*\[\[도식:" + re.escape(tok) + r"\]\][ \t]*\n?", "", body)
    html = wp.md_to_html(body)
    excerpt = make_excerpt(body)
    cat = wp.draft_category(path) or ""
    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    date = now
    modified_line = ""
    prev = POSTS_OUT / f"{slug}.md"
    if prev.exists():  # 이미 발행된 글을 고쳐 다시 올릴 때: 최초 발행일은 유지하고 수정일만 갱신
        m = re.search(r"^date:\s*(\S+)", prev.read_text(encoding="utf-8"), re.M)
        if m:
            date = m.group(1)
            modified_line = f"modified: {now}\n"
    # frontmatter 값은 한 줄(개행 금지). 콜론은 첫 콜론만 분리되므로 그대로 둬도 안전.
    one = lambda s: re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()
    front = (
        "---\n"
        f"title: {one(title)}\n"
        f"slug: {slug}\n"
        f"category: {cat}\n"
        f"date: {date}\n"
        f"{modified_line}"
        f"excerpt: {one(excerpt)}\n"
        "---\n"
    )
    POSTS_OUT.mkdir(parents=True, exist_ok=True)
    out = POSTS_OUT / f"{slug}.md"
    out.write_text(front + html + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="저장소 글 발행(워드프레스 불필요)")
    ap.add_argument("--force", action="store_true", help="하루 상한 무시")
    ap.add_argument("--max", type=int, default=1, help="한 번에 최대 몇 편(기본 1)")
    ap.add_argument("--dry-run", action="store_true", help="올리지 않고 다음 대상만 출력")
    ap.add_argument("--pages", action="store_true", help="고정 페이지도 다시 변환")
    ap.add_argument("--file", default=None, help="특정 초안 1편만 발행(경로)")
    args = ap.parse_args(argv)

    if args.pages:
        publish_pages()

    if args.file:
        p = Path(args.file)
        slug = wp.draft_slug(p)
        if not p.exists() or not slug:
            print(f"초안을 못 찾거나 슬러그가 없습니다: {args.file}")
            return 2
        out = publish_one(p, slug)
        print(f"[발행] {p.name} → {out.relative_to(ROOT)}")
        return 0

    if args.max <= 0:  # 페이지만 변환할 때(--max 0)
        return 0

    if not QUEUE.exists():
        print("대기 폴더가 없습니다: reports/구글글-초안")
        return 0

    if args.dry_run:
        f, slug = next_draft(published_slugs())
        print(f"다음 대상: {f.name if f else '없음'} slug={slug}")
        return 0

    existing = published_slugs()
    published = 0
    for _ in range(max(1, args.max)):
        cap = daily_max()
        if not args.force and published_today() + published >= cap:
            print(f"오늘 목표 채움({published_today()}/{cap}편).")
            break
        if not args.force and (published > 0 or slot_filled()):
            print("이번 구간(오전/오후)에는 이미 발행했습니다.")
            break
        f, slug = next_draft(existing)
        if not f:
            print("대기 중 글 없음(모두 발행됐거나 slug 없는 초안뿐).")
            break
        out = publish_one(f, slug)
        existing.add(slug)
        published += 1
        print(f"[발행] {f.name} → {out.relative_to(ROOT)}")

    print(f"이번에 {published}편 발행.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
