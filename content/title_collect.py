"""참고 블로거 제목 전체 수집 (대표 요청 2026-10-12 "참고 블로거를 빠짐없이 카테고리화"): 공개 RSS, AI 없음, 0원.

경제 참고 블로거 전원(config/econ_refs.yaml) + 제목 고수(config/title_masters.yaml) + 패션 참고 블로거 + 우리 블로그(config/blogs.yaml url)의
RSS 최근 글(보통 50개 안팎) 제목·날짜·카테고리를 econ/ref/titles/수집/<날짜>.md 에 모은다. 유형 × 양념 분류는 이 파일을 읽고 Claude가 한다.
"""
from __future__ import annotations

import re

import yaml

from market.common import ROOT
from . import econ_flow as F
from .econ_refs import feed

OUT = ROOT / "econ" / "ref" / "titles" / "수집"


def _yaml(p: str) -> dict:
    f = ROOT / p
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def targets() -> dict[str, tuple[str, str]]:
    """아이디 → (이름, 묶음). 같은 아이디는 한 번만."""
    t: dict[str, tuple[str, str]] = {}
    for bid, name in (_yaml("config/econ_refs.yaml").get("bloggers") or {}).items():
        t[str(bid)] = (str(name), "경제 참고")
    for bid, name in (_yaml("config/title_masters.yaml").get("masters") or {}).items():
        t.setdefault(str(bid), (str(name), "제목 고수"))
    for bid, name in (_yaml("config/keywords_fashion.yaml").get("ref_bloggers") or {}).items():
        t.setdefault(str(bid), (str(name), "패션 참고"))
    for k, b in (_yaml("config/blogs.yaml") or {}).items():
        m = re.search(r"blog\.naver\.com/([\w-]+)", str(b.get("url", ""))) if isinstance(b, dict) else None
        if m:
            t[m.group(1)] = (f"우리({b.get('name', k)})", "우리")
    return t


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md, bad = [f"# 참고 블로거 제목 수집 ({F.today()}, 공개 RSS · AI 없음)", ""], []
    for bid, (name, group) in targets().items():
        try:
            items = feed(bid)
        except Exception as ex:
            print(f"{bid} RSS 실패: {type(ex).__name__}")
            bad.append(f"{bid}({name})")
            continue
        md += [f"## {name} ({bid}) · {group} · {len(items)}개", ""]
        md += [f"- {it['title']} · {it['at']:%m-%d} · {it['category']}" for it in items]
        md.append("")
    if bad:
        md += ["## 못 읽음", ""] + [f"- {b}" for b in bad]
    (OUT / f"{F.today()}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"저장: {OUT / (F.today() + '.md')} (실패 {len(bad)})")


if __name__ == "__main__":
    run()
