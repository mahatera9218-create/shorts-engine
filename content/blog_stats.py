"""내 블로그 통계 받기 (대표 결정 2026-10-08: 어사이드가 매일 아침 네이버 블로그 통계를 읽어 [블로그통계] 이슈로 올림).

네이버 블로그 통계는 공식 API가 없어 대표 계정으로 로그인한 어사이드가 화면을 읽는다(대표 본인 데이터).
이슈 본문은 한 줄에 하나, 아래 모양 (블로그 = 경제 | 패션):
  [통계] 경제 | 2026-10-08 | 조회 1234 | 방문 567
  [글] 경제 | 글 제목 | 조회 120 | 공감 3 | 댓글 1
  [검색어] 경제 | 원달러 환율 | 45
  [경로] 경제 | 네이버 검색 | 60%
→ econ/stats/<날짜>.yaml. 도우미 '성과' 탭과 제목 만들기(잘 된 제목 참고)에 쓴다.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "econ" / "stats"
BLOGS = {"경제": "econ", "패션": "fashion"}
NUM = re.compile(r"[\d,]+")


def _n(s: str) -> int:
    m = NUM.search(s or "")
    return int(m.group().replace(",", "")) if m else 0


def parse(text: str) -> tuple[str, dict]:
    day, out = "", {}
    for raw in text.splitlines():
        m = re.match(r"^\s*[-*]?\s*\[(통계|글|검색어|경로)\]\s*(.+)$", raw.strip())
        if not m:
            continue
        kind, parts = m.group(1), [p.strip() for p in m.group(2).split("|")]
        bid = BLOGS.get(parts[0].replace("블로그", "").strip())
        if not bid or len(parts) < 2:
            continue
        b = out.setdefault(bid, {"total": {}, "posts": [], "queries": [], "paths": []})
        if kind == "통계":
            if re.match(r"\d{4}-\d{2}-\d{2}", parts[1]):
                day = day or parts[1][:10]
            for p in parts[1:]:
                if "조회" in p:
                    b["total"]["조회"] = _n(p)
                elif "방문" in p:
                    b["total"]["방문"] = _n(p)
        elif kind == "글" and len(parts) >= 3:
            row = {"title": parts[1]}
            for p in parts[2:]:
                for k in ("조회", "공감", "댓글"):
                    if k in p:
                        row[k] = _n(p)
            b["posts"].append(row)
        elif kind == "검색어" and len(parts) >= 2:
            b["queries"].append({"q": parts[1], "n": _n(parts[2]) if len(parts) > 2 else 0})
        elif kind == "경로" and len(parts) >= 2:
            b["paths"].append({"path": parts[1], "share": parts[2] if len(parts) > 2 else ""})
    for b in out.values():
        b["posts"].sort(key=lambda r: -r.get("조회", 0))
    return day or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), out


def save(text: str) -> str:
    day, data = parse(text)
    if not data:
        return "형식에 맞는 줄([통계]·[글]·[검색어]·[경로])이 없어 저장하지 못했어요."
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{day}.yaml").write_text(yaml.safe_dump({"date": day, "blogs": data}, allow_unicode=True, sort_keys=False),
                                    encoding="utf-8")
    return f"{day} 블로그 통계 저장: " + ", ".join(f"{k} 글 {len(v['posts'])}개·검색어 {len(v['queries'])}개" for k, v in data.items())


def recent(days: int = 14) -> list[dict]:
    """최근 통계 파일들 (새것부터)."""
    files = sorted(OUT.glob("*.yaml"), reverse=True)[:days] if OUT.exists() else []
    return [yaml.safe_load(f.read_text(encoding="utf-8")) or {} for f in files]


def top_titles(bid: str, n: int = 5, days: int = 14) -> list[tuple[str, int]]:
    """최근 days일 동안 조회수 높은 우리 글 제목 (제목별 최고 조회수)."""
    best: dict[str, int] = {}
    for d in recent(days):
        for r in (d.get("blogs", {}).get(bid) or {}).get("posts", []):
            best[r["title"]] = max(best.get(r["title"], 0), r.get("조회", 0))
    return sorted(best.items(), key=lambda x: -x[1])[:n]


def title_hint(bid: str) -> str:
    """제목 만들 때 덧붙일 참고 (잘 된 우리 글). 통계가 없으면 빈칸."""
    top = [t for t in top_titles(bid) if t[1] > 0]
    if not top:
        return ""
    return ("\n\n[우리 블로그에서 최근 조회수가 높았던 제목 — 이 제목들의 공통점(형식·말투·훅)을 참고하되 문장을 복사하지 마세요]\n"
            + "\n".join(f"- {t} (조회 {v:,})" for t, v in top))


def main() -> None:
    msg = save(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(msg)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"msg={msg}\n")


if __name__ == "__main__":
    main()
