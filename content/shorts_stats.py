"""쇼츠 성과 수집 (docs/운영-계획.md 6장): 우리 채널의 공개 통계를 매일 모아 형식(A·B·C)별로 판정한다.

- 통로: 유튜브 Data API(YOUTUBE_API_KEY)의 공개 통계만 — 채널 구독자·조회수, 올린 영상의 조회·좋아요·댓글.
  끝까지 본 비율·노출 클릭률은 공개 API에 없다 → 주간 점검 때 유튜브 스튜디오 캡처로 받는다.
- 짝 찾기: 올린 영상 제목 = 쇼츠 모음의 제목(shorts/log.yaml). 대표가 제목을 고쳤으면 '미확인'으로 두고 보고서에 적는다.
- 매일 스냅숏을 reports/쇼츠-성과/stats.yaml에 쌓는다 → 올린 뒤 3일·7일 조회수로 판정.
- 결과: reports/쇼츠-성과/LATEST.md (목표 진척, 형식별 성과, 상위·하위, 올린 비율)
사용법: python -m content.shorts_stats
"""
from __future__ import annotations

import re
import statistics
import sys
from datetime import date, timedelta

import yaml

from market.common import ROOT, load_yaml, missing_secrets

OUT = ROOT / "reports" / "쇼츠-성과"
STATS = OUT / "stats.yaml"
LOG = ROOT / "shorts" / "log.yaml"
KINDS = {"A": "A 통장형", "B": "B 비교형", "C": "C 한 장 반복형"}
GOAL_SUBS, GOAL_VIEWS_90 = 500, 3_000_000  # 1차 목표: 확대 파트너 (쇼핑 제휴)
MIN_GROUP = 5  # 형식 비교는 올린 지 3일 지난 영상이 형식마다 5개 이상일 때


def _norm(s: str) -> str:
    return re.sub(r"[\s#?!.,·]", "", s)


def load(path, default):
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or default) if path.exists() else default


def fetch(yt, handle: str) -> tuple[dict, list[dict]]:
    """채널 통계 + 최근 올린 영상(최대 50개)의 공개 통계."""
    ch = yt._call("channels", {"part": "contentDetails,statistics", "forHandle": handle})
    items = ch.get("items", [])
    if not items:
        raise RuntimeError(f"채널을 찾지 못함: {handle}")
    c = items[0]
    st = c.get("statistics", {})
    channel = {"subs": int(st.get("subscriberCount", 0) or 0), "views": int(st.get("viewCount", 0) or 0),
               "videos": int(st.get("videoCount", 0) or 0)}
    up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = yt._call("playlistItems", {"part": "contentDetails", "playlistId": up, "maxResults": 50})
    ids = [x["contentDetails"]["videoId"] for x in pl.get("items", [])]
    vids = []
    if ids:
        r = yt._call("videos", {"part": "snippet,statistics", "id": ",".join(ids)})
        for v in r.get("items", []):
            s = v.get("statistics", {})
            vids.append({"id": v["id"], "title": v["snippet"].get("title", ""), "published": v["snippet"].get("publishedAt", "")[:10],
                         "views": int(s.get("viewCount", 0) or 0), "likes": int(s.get("likeCount", 0) or 0),
                         "comments": int(s.get("commentCount", 0) or 0)})
    return channel, vids


def update(channel: dict, vids: list[dict], today: str) -> dict:
    """스냅숏을 쌓고, 로그의 쇼츠와 짝을 짓는다 (log.yaml에 video_id·uploaded 기록)."""
    stats = load(STATS, {"channel": {}, "videos": {}})
    stats["channel"][today] = channel
    log = load(LOG, [])
    by_title = {_norm(x["title"]): x for x in log}
    for v in vids:
        rec = stats["videos"].setdefault(v["id"], {"title": v["title"], "published": v["published"], "snaps": {}})
        m = by_title.get(_norm(v["title"]))
        if m:
            rec |= {"kind": m["kind"], "key": m["key"]}
            m |= {"video_id": v["id"], "uploaded": v["published"]}
        rec["title"] = v["title"]
        rec["snaps"][today] = {"views": v["views"], "likes": v["likes"], "comments": v["comments"]}
    OUT.mkdir(parents=True, exist_ok=True)
    STATS.write_text(yaml.safe_dump(stats, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if log:
        LOG.write_text(yaml.safe_dump(log, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return stats


def views_at(rec: dict, days: int) -> int | None:
    """올린 뒤 days일째(그 뒤 가장 가까운 스냅숏)의 조회수. 아직 안 됐으면 None."""
    pub = date.fromisoformat(rec["published"])
    snaps = sorted((date.fromisoformat(d), s["views"]) for d, s in rec["snaps"].items())
    later = [v for d, v in snaps if (d - pub).days >= days]
    return later[0] if later else None


def summary(stats: dict, today: str) -> list[str]:
    t = date.fromisoformat(today)
    ch = stats["channel"].get(today) or (stats["channel"][max(stats["channel"])] if stats["channel"] else {})
    vids = stats["videos"]
    latest = {k: r["snaps"][max(r["snaps"])]["views"] for k, r in vids.items() if r["snaps"]}
    v90 = sum(v for k, v in latest.items() if (t - date.fromisoformat(vids[k]["published"])).days <= 90)
    log = load(LOG, [])
    made = [x for x in log if (t - date.fromisoformat(x["date"])).days < 7]
    L = ["## 목표 진척 (1차: 확대 파트너 = 구독자 500 + 90일 쇼츠 조회 300만)", "",
         f"- 구독자 **{ch.get('subs', 0):,}** / {GOAL_SUBS:,} ({ch.get('subs', 0) / GOAL_SUBS:.0%})",
         f"- 최근 90일 올린 쇼츠 조회수 합 **{v90:,}** / {GOAL_VIEWS_90:,} ({v90 / GOAL_VIEWS_90:.1%})",
         f"- 최근 7일: 만든 쇼츠 {len(made)}개 · 올린 쇼츠 {sum(bool(x.get('video_id')) for x in made)}개",
         "", "## 형식별 성과 (올린 지 3일·7일 조회수)", "",
         "| 형식 | 올린 수 | 3일 평균 | 7일 평균 | 최고 |", "| --- | --- | --- | --- | --- |"]
    for k, name in KINDS.items():
        rs = [r for r in vids.values() if r.get("kind") == k]
        d3 = [x for x in (views_at(r, 3) for r in rs) if x is not None]
        d7 = [x for x in (views_at(r, 7) for r in rs) if x is not None]
        best = max(rs, key=lambda r: r["snaps"][max(r["snaps"])]["views"], default=None)
        cells = [name, str(len(rs)),
                 f"{statistics.mean(d3):,.0f} ({len(d3)}개)" if d3 else "-",
                 f"{statistics.mean(d7):,.0f} ({len(d7)}개)" if d7 else "-",
                 f"{best['title'][:24]} {best['snaps'][max(best['snaps'])]['views']:,}" if best else "-"]
        L.append("| " + " | ".join(cells) + " |")
    ready = {k: [views_at(r, 3) for r in vids.values() if r.get("kind") == k and views_at(r, 3) is not None] for k in KINDS}
    if all(len(v) >= MIN_GROUP for v in ready.values()):
        avg = {k: statistics.mean(v) for k, v in ready.items()}
        top = max(avg, key=avg.get)
        L += ["", f"→ 판정: 3일 평균이 가장 높은 형식은 **{KINDS[top]}** (운영 계획 6장 규칙으로 비중 조정)"]
    else:
        L += ["", "→ 판정 보류: 형식마다 올린 지 3일 지난 영상이 5개 이상 모이면 비교"]
    ranked = sorted(vids.values(), key=lambda r: -r["snaps"][max(r["snaps"])]["views"]) if vids else []
    L += ["", "## 조회수 상위 5 · 하위 5", ""]
    L += [f"- ▲ {r['title'][:36]} · {KINDS.get(r.get('kind'), '미확인')} · {r['snaps'][max(r['snaps'])]['views']:,}회 · 좋아요 "
          f"{r['snaps'][max(r['snaps'])]['likes']:,} · 댓글 {r['snaps'][max(r['snaps'])]['comments']:,}" for r in ranked[:5]]
    L += [f"- ▼ {r['title'][:36]} · {KINDS.get(r.get('kind'), '미확인')} · {r['snaps'][max(r['snaps'])]['views']:,}회"
          for r in ranked[5:][-5:]]
    unk = [r["title"] for r in vids.values() if not r.get("kind")]
    if unk:
        L += ["", f"- 짝을 못 찾은 영상 {len(unk)}개 (제목을 고쳐 올렸거나 직접 만든 영상): " + ", ".join(x[:20] for x in unk[:5])]
    return L


def main() -> None:
    handle = (load_yaml("youtube.yaml").get("channel") or {}).get("handle", "")
    if not handle or missing_secrets("youtube"):
        print("쇼츠 성과: 채널 주소(config/youtube.yaml) 또는 YOUTUBE_API_KEY가 없어 건너뜀")
        sys.exit(0)
    from market.youtube import YouTube
    today = str(date.today())
    yt = YouTube(budget=200)
    channel, vids = fetch(yt, handle)
    stats = update(channel, vids, today)
    text = "\n".join([f"# 쇼츠 성과 · {today}", "", f"채널 {handle} · 공개 통계 기준 (끝까지 본 비율은 주간 캡처로)", ""]
                     + summary(stats, today)) + "\n"
    (OUT / "LATEST.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
