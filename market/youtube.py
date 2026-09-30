"""유튜브 Data API v3 — 점수 상위 키워드만 조회 (KICKOFF 1주차 4번, 규칙 5).

쿼터: search.list 100단위, videos.list·channels.list 1단위(요청당 최대 50개).
예산(quota_budget)을 넘기 전에 멈춘다. 타인 영상은 다운로드하지 않는다(메타데이터만).
"""
from __future__ import annotations

from .common import request_json, secret

BASE = "https://www.googleapis.com/youtube/v3"
COST = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}


class QuotaExceeded(RuntimeError):
    pass


class YouTube:
    def __init__(self, budget: int, region: str = "KR", language: str = "ko"):
        self.key = secret("YOUTUBE_API_KEY")
        self.budget = budget
        self.used = 0
        self.region = region
        self.language = language

    def _call(self, kind: str, params: dict) -> dict:
        if self.used + COST[kind] > self.budget:
            raise QuotaExceeded(f"쿼터 예산 {self.budget}단위 도달")
        self.used += COST[kind]
        return request_json("GET", f"{BASE}/{kind}", params={**params, "key": self.key})

    def keyword(self, keyword: str, n: int = 10, outlier_ratio: float = 3.0) -> dict:
        """키워드 → 상위 영상 조회수, 채널 구독자, 이상치(조회수 ÷ 구독자 ≥ 기준)."""
        found = self._call("search", {
            "part": "snippet", "q": keyword, "type": "video", "maxResults": n,
            "regionCode": self.region, "relevanceLanguage": self.language, "order": "relevance",
        })
        video_ids = [it["id"]["videoId"] for it in found.get("items", []) if it.get("id", {}).get("videoId")]
        if not video_ids:
            return {"total": found.get("pageInfo", {}).get("totalResults", 0), "videos": []}
        vids = self._call("videos", {"part": "snippet,statistics", "id": ",".join(video_ids)})
        channel_ids = sorted({v["snippet"]["channelId"] for v in vids.get("items", [])})
        chans = self._call("channels", {"part": "statistics,snippet", "id": ",".join(channel_ids)})
        subs = {}
        for c in chans.get("items", []):
            st = c.get("statistics", {})
            # 구독자 수를 숨긴 채널은 비교에서 뺀다.
            subs[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
        videos = []
        for v in vids.get("items", []):
            views = int(v.get("statistics", {}).get("viewCount", 0))
            sub = subs.get(v["snippet"]["channelId"])
            ratio = views / sub if sub else None
            videos.append({
                "title": v["snippet"].get("title", ""),
                "channel": v["snippet"].get("channelTitle", ""),
                "published": v["snippet"].get("publishedAt", "")[:10],
                "views": views,
                "subscribers": sub,
                "views_per_sub": ratio,
                "outlier": ratio is not None and ratio >= outlier_ratio,
                "url": f"https://www.youtube.com/watch?v={v['id']}",
            })
        videos.sort(key=lambda x: x["views"], reverse=True)
        return {"total": found.get("pageInfo", {}).get("totalResults", 0), "videos": videos}
