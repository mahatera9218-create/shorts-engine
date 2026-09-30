"""쇼츠 벤치마크 (2026-09-30): 스포츠 돈 쇼츠 중 한국에서 잘 되는 것의 숫자를 모아 스타일 가설을 세운다.

- 유튜브 공식 API(YOUTUBE_API_KEY)로 메타데이터만 읽는다: 제목·조회수·길이·올린 날·채널 구독자. 영상·썸네일은 내려받지 않는다.
- 검색어마다 최근 1년, 짧은 영상, 조회수 순 → 3분 이하만 남긴다 (API에 '쇼츠' 표시가 없어 길이로 가른다).
- 결과: reports/쇼츠-벤치마크/<날짜>.md (길이·제목 패턴·하루 조회수·구독자 대비 튄 영상, 대표 캡처 부탁 목록)
사용법: python -m market.shorts_bench
"""
from __future__ import annotations

import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone

from .common import ROOT, load_yaml, missing_secrets
from .youtube import YouTube

DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
OUTLIER = 3.0  # 조회수 ÷ 구독자 ≥ 3이면 채널 힘보다 영상 힘으로 뜬 것


def seconds(iso: str) -> int:
    m = DUR.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def features(title: str) -> dict:
    return {"len": len(title), "digit": bool(re.search(r"\d", title)), "question": "?" in title,
            "rank": bool(re.search(r"TOP|top|Top|순위|위\b|\d+위", title)), "vs": bool(re.search(r"\bvs\b|VS|대결", title)),
            "money": bool(re.search(r"억|만원|달러|\$|원\b|연봉|몸값|상금", title)),
            "emoji": bool(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", title)),
            "shorts_tag": "#shorts" in title.lower()}


def collect(yt: YouTube, cfg: dict, today: date) -> list[dict]:
    after = (datetime.combine(today - timedelta(days=cfg["published_days"]), datetime.min.time(), timezone.utc)
             .strftime("%Y-%m-%dT%H:%M:%SZ"))
    seen: dict[str, dict] = {}
    for q in cfg["queries"]:
        found = yt._call("search", {"part": "snippet", "q": q, "type": "video", "videoDuration": "short",
                                    "order": "viewCount", "publishedAfter": after, "maxResults": cfg["per_query"],
                                    "regionCode": cfg["region"], "relevanceLanguage": cfg["language"]})
        ids = [it["id"]["videoId"] for it in found.get("items", []) if it.get("id", {}).get("videoId")]
        if not ids:
            continue
        vids = yt._call("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
        for v in vids.get("items", []):
            sec = seconds(v.get("contentDetails", {}).get("duration", ""))
            if not 0 < sec <= cfg["max_seconds"]:
                continue
            if v["id"] in seen:
                seen[v["id"]]["queries"].append(q)
                continue
            pub = v["snippet"].get("publishedAt", "")[:10]
            days = max(1, (today - date.fromisoformat(pub)).days) if pub else 1
            views = int(v.get("statistics", {}).get("viewCount", 0))
            seen[v["id"]] = {"id": v["id"], "title": v["snippet"].get("title", ""), "channel": v["snippet"].get("channelTitle", ""),
                             "channel_id": v["snippet"]["channelId"], "published": pub, "days": days, "sec": sec,
                             "views": views, "per_day": views / days,
                             "likes": int(v.get("statistics", {}).get("likeCount", 0) or 0),
                             "comments": int(v.get("statistics", {}).get("commentCount", 0) or 0),
                             "queries": [q], "url": f"https://www.youtube.com/shorts/{v['id']}"}
    chans = sorted({v["channel_id"] for v in seen.values()})
    subs: dict[str, int | None] = {}
    for i in range(0, len(chans), 50):
        r = yt._call("channels", {"part": "statistics", "id": ",".join(chans[i:i + 50])})
        for c in r.get("items", []):
            st = c.get("statistics", {})
            subs[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
    for v in seen.values():
        v["subs"] = subs.get(v["channel_id"])
        v["ratio"] = v["views"] / v["subs"] if v["subs"] else None
    return sorted(seen.values(), key=lambda v: -v["views"])


def _t(title: str, n: int) -> str:
    """표·링크 안에서 깨지지 않게."""
    return title[:n].replace("|", "/").replace("[", "(").replace("]", ")")


def _n(x: float) -> str:
    return f"{x / 10000:,.1f}만" if x >= 10000 else f"{x:,.0f}"


def report(vs: list[dict], cfg: dict, today: date, used: int) -> str:
    if not vs:
        return f"# 쇼츠 벤치마크 · {today}\n\n결과 없음 (검색어·기간을 넓혀 다시)\n"
    top = vs[:max(10, len(vs) // 4)]  # 조회수 상위 25%를 '잘 된 쇼츠'로 본다
    rest = vs[len(top):]
    feats = {k: [features(v["title"])[k] for v in top] for k in features("")}
    feats_rest = {k: [features(v["title"])[k] for v in rest] for k in features("")} if rest else {}

    def pct(xs):
        return f"{sum(xs) / len(xs):.0%}" if xs else "-"

    L = [f"# 쇼츠 벤치마크 · {today}", "",
         f"검색어 {len(cfg['queries'])}개, 최근 {cfg['published_days']}일, {cfg['max_seconds']}초 이하 → 쇼츠 {len(vs)}개 "
         f"(유튜브 API {used}단위). 상위 25%({len(top)}개)를 '잘 된 쇼츠'로 보고 나머지와 비교.", "",
         "## 1. 길이", "",
         f"- 잘 된 쇼츠 길이 중앙값 **{statistics.median(v['sec'] for v in top):.0f}초** "
         f"(나머지 {statistics.median(v['sec'] for v in rest):.0f}초)" if rest else
         f"- 길이 중앙값 {statistics.median(v['sec'] for v in top):.0f}초",
         "- 길이 분포 (잘 된 쇼츠): " + ", ".join(
             f"{a}~{b}초 {sum(a <= v['sec'] < b for v in top)}개" for a, b in ((0, 15), (15, 30), (30, 45), (45, 60), (60, 181))),
         "", "## 2. 제목 패턴 (잘 된 쇼츠 vs 나머지)", "",
         "| 패턴 | 잘 된 쇼츠 | 나머지 |", "| --- | --- | --- |"]
    names = {"digit": "숫자 있음", "question": "물음표", "rank": "순위·TOP", "vs": "대결(vs)", "money": "돈 단어(억·연봉·몸값)",
             "emoji": "이모지", "shorts_tag": "#shorts"}
    L += [f"| {names[k]} | {pct(feats[k])} | {pct(feats_rest.get(k, []))} |" for k in names]
    L += [f"| 제목 길이 중앙값 | {statistics.median(feats['len']):.0f}자 | "
          f"{statistics.median(feats_rest['len']):.0f}자 |" if rest else "",
          "", "## 3. 조회수 상위 20 (하루 조회수 = 조회수 ÷ 올린 뒤 날수)", "",
          "| 제목 | 조회수 | 하루 | 길이 | 올린 날 | 채널 (구독자) | 조회÷구독 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for v in vs[:20]:
        L.append(f"| [{_t(v['title'], 40)}]({v['url']}) | {_n(v['views'])} | {_n(v['per_day'])} | {v['sec']}초 | {v['published']} | "
                 f"{v['channel'][:14]} ({_n(v['subs']) if v['subs'] else '비공개'}) | {v['ratio']:.1f} |" if v["ratio"] else
                 f"| [{_t(v['title'], 40)}]({v['url']}) | {_n(v['views'])} | {_n(v['per_day'])} | {v['sec']}초 | {v['published']} | "
                 f"{v['channel'][:14]} (비공개) | - |")
    outl = sorted((v for v in vs if v["ratio"] and v["ratio"] >= OUTLIER), key=lambda v: -v["ratio"])
    L += ["", f"## 4. 채널 힘보다 영상 힘으로 뜬 쇼츠 (조회÷구독 ≥ {OUTLIER:.0f}, 새 채널이 따라 할 만한 것)", ""]
    L += [f"- [{_t(v['title'], 50)}]({v['url']}) · {_n(v['views'])}회 · 구독자 {_n(v['subs'])} · {v['sec']}초 · {v['ratio']:.0f}배"
          for v in outl[:15]] or ["- 없음"]
    chans: dict[str, list] = {}
    for v in top:
        chans.setdefault(v["channel"], []).append(v)
    L += ["", "## 5. 잘 된 쇼츠를 많이 낸 채널 (벤치마크 후보)", ""]
    L += [f"- {c}: {len(xs)}개, 조회수 합 {_n(sum(x['views'] for x in xs))}"
          for c, xs in sorted(chans.items(), key=lambda x: -len(x[1]))[:8]]
    cap = (outl[:2] + [v for v in vs if v not in outl[:2]])[:4]
    L += ["", "## 6. 대표님 캡처 부탁 (스타일 분석용)", "",
          "아래 쇼츠를 열어 각각 **시작 화면 · 중간 · 끝** 세 장씩 캡처해 주세요. 첫 1초 문구, 화면 구성, 자막 위치를 봅니다.", ""]
    L += [f"{i}. [{_t(v['title'], 50)}]({v['url']})" for i, v in enumerate(cap, 1)]
    L += ["", "## 7. 검색어별 상위 3", ""]
    for q in cfg["queries"]:
        xs = [v for v in vs if q in v["queries"]][:3]
        L.append(f"- **{q}**: " + (" / ".join(f"[{_t(v['title'], 28)}]({v['url']}) {_n(v['views'])}" for v in xs) or "없음"))
    L += ["", "숫자는 유튜브 공개 통계(조회수·구독자)이며, 끝까지 본 비율 같은 내부 지표는 API로 볼 수 없다."]
    return "\n".join(x for x in L if x is not None) + "\n"


def main() -> None:
    if missing_secrets("youtube"):
        print("YOUTUBE_API_KEY가 없어 쇼츠 벤치마크를 건너뜀 (GitHub Secrets에 등록 필요)")
        sys.exit(0)
    cfg = load_yaml("shorts_bench.yaml")
    today = date.today()
    yt = YouTube(budget=5000, region=cfg["region"], language=cfg["language"])
    vs = collect(yt, cfg, today)
    out = ROOT / "reports" / "쇼츠-벤치마크" / f"{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(vs, cfg, today, yt.used), encoding="utf-8")
    print(f"쇼츠 {len(vs)}개 분석 → {out.relative_to(ROOT)} (API {yt.used}단위)")


if __name__ == "__main__":
    main()
