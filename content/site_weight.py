"""사이트 무게 점검: 빌드 결과(web/.next)에서 페이지별 HTML·JS 전송량(gzip 근사)을 재고 예산과 비교한다.

- JS: app-build-manifest.json의 라우트별 청크(공통+해당 페이지) gzip 크기 합 = '첫 로드 JS'.
- HTML: .next/server/app/*.html gzip 크기(인라인 CSS 포함). 이미지는 외부(Unsplash)라 여기서 재지 않고 imgsize 규칙(w=480/800/960)으로 관리.
- 예산(초과하면 종료코드 1): 첫 로드 JS 130KB, 글 HTML 60KB, 일반 페이지 HTML 80KB, 인라인 CSS 25KB.
- 결과는 reports/사이트무게.md 에 날짜별로 한 줄씩 쌓는다(--record).

사용: (web에서 npm run build 후) python -m content.site_weight [--record]
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market.common import ROOT

NEXT = ROOT / "web" / ".next"
REPORT = ROOT / "reports" / "사이트무게.md"
KST = timezone(timedelta(hours=9))
BUDGET = {"js_kb": 130, "html_post_kb": 60, "html_page_kb": 80, "css_kb": 25}


def gz(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), 6))


def route_js(manifest: dict, route: str) -> tuple[int, list[str]]:
    """라우트의 첫 로드 JS(gzip). 레이아웃·메인 청크와 페이지 청크의 합집합."""
    pages = manifest["pages"]
    keys = ["/layout", route + "/page" if route != "/" else "/page"]
    files: list[str] = []
    for k in keys:
        for f in pages.get(k, []):
            if f.endswith(".js") and f not in files:
                files.append(f)
    total = sum(gz(NEXT / f) for f in files if (NEXT / f).exists())
    return total, files


def measure() -> dict:
    manifest = json.loads((NEXT / "app-build-manifest.json").read_text(encoding="utf-8"))
    out = {"routes": [], "css_kb": 0.0}
    html_dir = NEXT / "server" / "app"
    for h in sorted(html_dir.rglob("*.html")):
        if h.name.startswith("_not-found"):
            continue
        rel = h.relative_to(html_dir).with_suffix("")
        route = "/" if str(rel) == "index" else "/" + str(rel).replace("\\", "/")
        text = h.read_text(encoding="utf-8", errors="ignore")
        css = sum(len(m) for m in re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
        # 동적 라우트 청크 키는 [slug] 형태 — 실제 경로를 템플릿으로 바꿔 찾는다
        tmpl = route
        for k in manifest["pages"]:
            if k.endswith("/page"):
                base = k[: -len("/page")] or "/"
                pat = "^" + re.sub(r"\\\[[^/]+?\\\]", "[^/]+", re.escape(base)) + "$"
                if re.match(pat, route) and ("[" in base or base == route):
                    tmpl = base
                    if base == route:
                        break
        js, _ = route_js(manifest, tmpl)
        out["routes"].append({"route": route, "html_kb": gz(h) / 1024, "js_kb": js / 1024})
        out["css_kb"] = max(out["css_kb"], css / 1024)
    return out


def check(m: dict) -> list[str]:
    errs = []
    for r in m["routes"]:
        is_post = r["route"].count("/") == 1 and r["route"] != "/"
        lim = BUDGET["html_post_kb"] if is_post else BUDGET["html_page_kb"]
        if r["html_kb"] > lim:
            errs.append(f"{r['route']}: HTML {r['html_kb']:.1f}KB > {lim}KB")
        if r["js_kb"] > BUDGET["js_kb"]:
            errs.append(f"{r['route']}: 첫 로드 JS {r['js_kb']:.1f}KB > {BUDGET['js_kb']}KB")
    if m["css_kb"] > BUDGET["css_kb"]:
        errs.append(f"인라인 CSS {m['css_kb']:.1f}KB > {BUDGET['css_kb']}KB")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="reports/사이트무게.md에 오늘 결과를 덧붙임")
    args = ap.parse_args(argv)
    if not (NEXT / "app-build-manifest.json").exists():
        print("web/.next 가 없습니다. 먼저 web에서 npm run build 를 실행하세요.")
        return 2
    m = measure()
    errs = check(m)
    worst_js = max((r["js_kb"] for r in m["routes"]), default=0)
    worst_html = max(m["routes"], key=lambda r: r["html_kb"], default={"route": "-", "html_kb": 0})
    print(f"페이지 {len(m['routes'])}개 · 최대 첫 로드 JS {worst_js:.1f}KB · 최대 HTML {worst_html['html_kb']:.1f}KB({worst_html['route']}) · 인라인 CSS {m['css_kb']:.1f}KB")
    for r in sorted(m["routes"], key=lambda r: -(r["html_kb"] + r["js_kb"]))[:8]:
        print(f"  {r['route']:<42} HTML {r['html_kb']:5.1f}KB  JS {r['js_kb']:6.1f}KB")
    for e in errs:
        print("예산 초과:", e)
    if args.record:
        today = datetime.now(KST).strftime("%Y-%m-%d")
        head = ("# 사이트 무게 기록\n\n빌드 결과 기준(gzip 근사). 예산: 첫 로드 JS 130KB · 글 HTML 60KB · 일반 HTML 80KB · 인라인 CSS 25KB.\n\n"
                "| 날짜 | 페이지 수 | 최대 JS(KB) | 최대 HTML(KB) | 인라인 CSS(KB) | 예산 |\n|---|---|---|---|---|---|\n")
        row = f"| {today} | {len(m['routes'])} | {worst_js:.1f} | {worst_html['html_kb']:.1f} ({worst_html['route']}) | {m['css_kb']:.1f} | {'초과' if errs else '통과'} |\n"
        old = REPORT.read_text(encoding="utf-8") if REPORT.exists() else head
        lines = [l for l in old.splitlines(keepends=True) if not l.startswith(f"| {today} |")]
        REPORT.write_text("".join(lines) + row, encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
