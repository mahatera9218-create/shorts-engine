"""드립 발행기: 대기 중인 구글 글 초안을 하나씩 '공개'로 올린다(불규칙한 간격).

- 큐: reports/구글글-초안/*.md (파일 이름 순). 각 초안은 윗부분에 '슬러그: xxx' 줄이 있어야 한다.
- 이미 올라간 slug(공개·초안 포함)는 건너뛴다 → 중복 발행 방지.
- 불규칙성: 매 실행마다 확률 게이트로 '올릴지/건너뛸지' 결정. 하루 여러 번 도는 cron과 합쳐
  자연스러운(몰리지 않는) 간격으로 하루 1~2편이 올라간다.
- 원칙: 대표가 '검토 기간 자동 공개'를 결정(DECISIONS). 워크플로를 끄면 즉시 멈춘다.

사용법:
    python -m content.wp_drip               # 확률 게이트 통과 시 1편 공개
    python -m content.wp_drip --force       # 게이트 무시하고 바로 1편
    python -m content.wp_drip --dry-run     # 올리지 않고 '다음 대상'만 출력
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

from market.common import ROOT, missing_secrets
from content import wp

QUEUE = ROOT / "reports" / "구글글-초안"
PUBLISH_PROB = float(os.environ.get("DRIP_PROB", "0.7"))  # 매 실행 공개 확률(불규칙 간격용)
DAILY_MAX = int(os.environ.get("DRIP_DAILY_MAX", "3"))     # 하루 상한(2~3편 목표)


def next_draft(existing: set[str]) -> tuple[Path | None, str | None]:
    """아직 안 올라간 다음 초안과 그 slug. slug 없는 초안은 건너뛴다(중복 못 거름)."""
    for f in sorted(QUEUE.glob("*.md")):
        slug = wp.draft_slug(f)
        if not slug or slug in existing:
            continue
        return f, slug
    return None, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="구글 글 드립(불규칙) 자동 공개")
    ap.add_argument("--force", action="store_true", help="확률 게이트 무시하고 바로 1편")
    ap.add_argument("--dry-run", action="store_true", help="올리지 않고 다음 대상만 출력")
    args = ap.parse_args(argv)

    if not QUEUE.exists():
        print("대기 폴더가 없습니다: reports/구글글-초안")
        return 0

    if args.dry_run:
        f, slug = next_draft(set())
        print(f"다음 대상(중복검사 생략): {f.name if f else '없음'} slug={slug}")
        return 0

    missing = missing_secrets("wordpress")
    if missing:
        print("워드프레스 비밀 값이 없다: " + ", ".join(missing), file=sys.stderr)
        return 3

    existing = wp.existing_slugs()
    f, slug = next_draft(existing)
    if not f:
        print("대기 중 글 없음(모두 발행됐거나 slug 없는 초안뿐).")
        return 0

    if not args.force:
        today = wp.published_today_kst()
        if today >= DAILY_MAX:
            print(f"오늘 목표 채움({today}/{DAILY_MAX}편). 다음 대상 대기: {f.name}")
            return 0
        if random.random() > PUBLISH_PROB:
            print(f"이번엔 건너뜀(불규칙 간격, 오늘 {today}/{DAILY_MAX}). 다음 대상: {f.name}")
            return 0

    result = wp.publish_file(f, status="publish", slug=slug, verbose=True)
    print(f"[드립 발행] {f.name} → #{result.get('id')} {result.get('link')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
