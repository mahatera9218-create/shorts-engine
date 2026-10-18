"""패션 블로그(캐시미어 다이어리) 발행 도우미 (대표 2026-10-18).

reports/패션글-초안/*.md 를 휴대폰용 버튼 페이지로 만든다. 건강 도우미(content.health_desk)와 같은 틀을 쓴다.
차이: 성별 필터 없음(패션은 성별 구분 안 함), 이름만 다름. 검증 배지는 착용·가격 '확인' 상태로 쓴다.
Cloudflare Pages (.github/workflows/fashion-desk.yml). 검색엔진 수집 금지(noindex).

사용법: python -m content.fashion_desk [출력 폴더, 기본 site-fashion]
"""
from __future__ import annotations

import sys

from market.common import ROOT
from . import health_desk


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "site-fashion"
    sys.exit(health_desk.build(
        out_dir,
        drafts_dir=ROOT / "reports" / "패션글-초안",
        name="캐시미어 다이어리 (패션)",
        show_gender=False,
        research=True,
    ))


if __name__ == "__main__":
    main()
