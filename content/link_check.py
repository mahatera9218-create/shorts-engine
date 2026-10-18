"""내부 링크 점검: 글끼리 서로 연결되는지(고아 글·깨진 링크·나가는 링크 0)를 검사한다.

- 대상: 발행 글(web/content/posts/*.md)과 대기 초안(reports/구글글-초안/*.md). 본문의 [텍스트](/slug) 마크다운 링크와 발행 글의 <a href="/slug"> 링크를 본다.
- 고아 글: 다른 글에서 들어오는 링크가 0개. 깨진 링크: 존재하지 않는 slug·페이지로의 링크.
- 발행 글끼리가 기준이며, 대기 초안으로 가는 링크는 '아직 미발행'으로 따로 센다(발행되면 정상).
- 종료코드 1: 깨진 링크가 있을 때만(고아·미발행은 경고). 사용: python -m content.link_check
"""
from __future__ import annotations

import re
import sys

from content import wp
from market.common import ROOT

POSTS = ROOT / "web" / "content" / "posts"
DRAFTS = ROOT / "reports" / "구글글-초안"
PAGES = ROOT / "web" / "content" / "pages"
LINK = re.compile(r"(?:\]\(|href=\")/(?:p/|category/|rank/)?([a-z0-9][a-z0-9-]*)/?[\)\"]")


def _slug_of(path, drafts: bool) -> str:
    if drafts:
        return wp.draft_slug(path) or path.stem
    m = re.search(r"^slug:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else path.stem


def analyze() -> dict:
    pub = {_slug_of(f, False): f for f in POSTS.glob("*.md")}
    drafts = {_slug_of(f, True): f for f in DRAFTS.glob("*.md")} if DRAFTS.exists() else {}
    pages = {f.stem for f in PAGES.glob("*.md")} if PAGES.exists() else set()
    known = set(pub) | set(drafts) | pages | {"rank", "tax-apps", "tax-firms", "law-firms", "insurance-apps"}
    cats = {"jaetech", "realty", "tax", "pension"}
    out: dict[str, set[str]] = {}
    for s, f in {**drafts, **pub}.items():
        out[s] = {m for m in LINK.findall(f.read_text(encoding="utf-8")) if m != s}
    broken = {s: sorted(t - known - cats) for s, t in out.items() if t - known - cats}
    inbound = {s: 0 for s in pub}
    for s, targets in out.items():
        for t in targets:
            if t in inbound and s != t:
                inbound[t] += 1
    orphans = sorted(s for s, n in inbound.items() if n == 0)
    no_out = sorted(s for s in pub if not out.get(s))
    unpublished = {s: sorted(t for t in ts if t in drafts and t not in pub) for s, ts in out.items() if s in pub}
    return {"published": len(pub), "drafts": len(drafts), "broken": broken, "orphans": orphans,
            "no_outbound": no_out, "to_unpublished": {s: v for s, v in unpublished.items() if v}}


def main() -> int:
    r = analyze()
    print(f"발행 {r['published']}편 · 대기 초안 {r['drafts']}편")
    print(f"깨진 링크: {r['broken'] or '없음'}")
    print(f"고아 글(들어오는 링크 0): {r['orphans'] or '없음'}")
    print(f"나가는 링크 0: {r['no_outbound'] or '없음'}")
    print(f"아직 미발행 글로 가는 링크: {r['to_unpublished'] or '없음'}")
    return 1 if r["broken"] else 0


if __name__ == "__main__":
    sys.exit(main())
