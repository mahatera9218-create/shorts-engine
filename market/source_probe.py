"""경제 블로그 글감 소스 점검 (2026-10-04): 후보 통로가 GitHub에서 자동으로 받아지는지, 하루에 몇 건 나오는지 본다.

허용된 통로(공식 API·RSS)만 연다. 기사 본문은 받지 않고 제목·발행 시각만 센다.
결과: reports/경제-소스/소스-점검-<날짜>.md
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .common import ROOT, load_yaml, missing_secrets
from .naver_hub import ApiHub

UA = {"User-Agent": "Mozilla/5.0 (compatible; eoksori-source-check/1.0)"}
NOW = datetime.now(timezone.utc)


def _when(text: str) -> datetime | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def probe_rss(url: str) -> dict:
    t0 = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=20)
    except requests.RequestException as e:
        return {"ok": False, "why": f"연결 실패 {type(e).__name__}"}
    ms = int((time.time() - t0) * 1000)
    if r.status_code != 200:
        return {"ok": False, "why": f"HTTP {r.status_code}", "ms": ms}
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return {"ok": False, "why": "RSS 형식 아님", "ms": ms}
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    dates, titles = [], []
    for it in items:
        d = None
        for tag in ("pubDate", "{http://purl.org/dc/elements/1.1/}date",
                    "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"):
            el = it.find(tag)
            if el is not None and el.text:
                d = _when(el.text)
                if d:
                    break
        t = it.find("title") if it.find("title") is not None else it.find("{http://www.w3.org/2005/Atom}title")
        titles.append((t.text or "").strip() if t is not None else "")
        if d:
            dates.append(d)
    day = sum(1 for d in dates if NOW - d <= timedelta(hours=24))
    latest = max(dates).astimezone(timezone(timedelta(hours=9))).strftime("%m-%d %H:%M") if dates else "-"
    return {"ok": bool(items), "why": "" if items else "글 0건", "ms": ms, "n": len(items), "day": day,
            "latest": latest, "titles": [x for x in titles if x][:3]}


def probe_price(url: str) -> dict:
    try:
        r = requests.get(url, headers=UA, timeout=20)
    except requests.RequestException as e:
        return {"ok": False, "why": f"연결 실패 {type(e).__name__}"}
    if r.status_code != 200:
        return {"ok": False, "why": f"HTTP {r.status_code}"}
    return {"ok": True, "why": "", "sample": r.text[:160].replace("\n", " ").replace("|", "/")}


def probe_naver(queries: dict) -> dict:
    if missing_secrets("naver_hub"):
        return {}
    hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
    out = {}
    for asset, qs in queries.items():
        rows = []
        for q in qs:
            try:
                items = hub.news(q, display=100)
            except Exception as e:  # noqa: BLE001 — 점검 보고용
                rows.append({"q": q, "ok": False, "why": str(e)[:80]})
                continue
            today = datetime.now(timezone(timedelta(hours=9))).date()
            fresh = sum(1 for it in items if it.get("date") and (today - datetime.fromisoformat(it["date"]).date()).days <= 1)
            rows.append({"q": q, "ok": bool(items), "n": len(items), "day": fresh,
                         "titles": [it["title"] for it in items[:2]]})
        out[asset] = rows
    return out


def verdict(r: dict) -> str:
    if not r.get("ok"):
        return "❌ 안 됨"
    if r.get("day", 0) >= 5:
        return "✅ 충분"
    return "🟡 적음" if r.get("day", 0) else "🟡 오늘 글 없음"


def main() -> None:
    cfg = load_yaml("econ_sources.yaml")
    kst = datetime.now(timezone(timedelta(hours=9)))
    L = [f"# 경제 글감 소스 점검 ({kst:%Y-%m-%d %H:%M} 한국 시간)", "",
         "GitHub 서버에서 실제로 열어 본 결과예요. '최근 24시간'은 하루에 새 기사가 몇 건 나오는지예요.",
         "✅ 충분(하루 5건 이상) · 🟡 적음 · ❌ 자동으로 못 받음", ""]
    nav = probe_naver(cfg.get("naver_news", {}))
    L += ["## 1. 네이버 뉴스 검색 API (지금 쓰는 키)", ""]
    if not nav:
        L += ["키가 없어 점검 못 함", ""]
    for asset, rows in nav.items():
        L += [f"### {asset}", "", "| 검색어 | 결과 | 최근 1일 기사 수 (100건 중) | 예시 제목 |", "| --- | --- | --- | --- |"]
        for x in rows:
            L.append(f"| {x['q']} | {verdict(x)} | {x.get('day', '-')} | {' / '.join(x.get('titles', []))[:90].replace('|', '/')} |")
        L.append("")
    L += ["## 2. 언론사·전문매체 RSS", "", "| 자산 | 매체 | 결과 | 최근 24시간 | 최신 글 | 예시 제목 |", "| --- | --- | --- | --- | --- | --- |"]
    for s in cfg.get("rss", []):
        r = probe_rss(s["url"])
        L.append(f"| {s['asset']} | {s['name']} | {verdict(r)}{(' ' + r['why']) if r.get('why') else ''} | {r.get('day', '-')} | "
                 f"{r.get('latest', '-')} | {' / '.join(r.get('titles', [])[:2])[:90].replace('|', '/')} |")
        time.sleep(0.5)
    L += ["", "## 3. 가격 숫자 API (키 없이)", "", "| 자산 | 이름 | 결과 | 응답 앞부분 |", "| --- | --- | --- | --- |"]
    for s in cfg.get("price", []):
        r = probe_price(s["url"])
        L.append(f"| {s['asset']} | {s['name']} | {'✅' if r['ok'] else '❌ ' + r['why']} | {r.get('sample', '')[:80]} |")
    out = ROOT / "reports" / "경제-소스" / f"소스-점검-{kst:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
