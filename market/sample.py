"""예시 모드용 가짜 클라이언트. API 키 없이 전체 흐름과 결과 모양을 확인하는 데만 쓴다.

숫자는 키워드 문자열로 만든 의사 난수라 실제 시장과 아무 관계가 없다.
결과 파일에는 항상 "예시 데이터" 경고가 붙는다 (report.banner).
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

SUFFIXES = ["추천", "비교", "가격", "후기", "방법", "신청", "조건", "순위", "2026", "계산"]


def _rng(text: str) -> random.Random:
    return random.Random(int(hashlib.md5(text.encode()).hexdigest()[:8], 16))


class FakeKeywordTool:
    def related(self, seeds: list[str]) -> list[dict]:
        rows = []
        for seed in seeds:
            for suf in [""] + [x for x in SUFFIXES if not seed.endswith(x)]:
                kw = f"{seed} {suf}".strip()
                r = _rng(kw)
                vol = r.choice([80, 400, 1200, 5000, 18000, 60000]) * r.uniform(0.6, 1.4)
                rows.append({
                    "keyword": kw, "volume_pc": vol * 0.3, "volume_mobile": vol * 0.7, "volume": vol,
                    "clicks": vol * r.uniform(0.002, 0.03), "ctr_mobile": r.uniform(0.1, 3),
                    "competition": r.choice(["낮음", "중간", "높음"]),
                    "competition_level": 0, "ad_depth": r.randint(1, 15),
                })
                rows[-1]["competition_level"] = {"낮음": 1, "중간": 2, "높음": 3}[rows[-1]["competition"]]
        return rows


class FakeHub:
    def blog(self, keyword: str, display: int = 100) -> dict:
        r = _rng("blog" + keyword)
        today = date.today()
        gap = r.choice([0.2, 1, 3, 10, 40])  # 글 사이 평균 간격(일): 작을수록 경쟁이 활발
        items = [{
            "title": f"[예시] {keyword} 정리 {i + 1}",
            "blogger": f"예시블로그{r.randint(1, 12)}",
            "blog_link": "", "link": "",
            "postdate": (today - timedelta(days=int(i * gap))).strftime("%Y%m%d"),
            "description": r.choice(["예시 요약이에요. 숫자가 꽤 크죠?", "예시 요약입니다. 순위를 정리했다.", "이게 말이 되나요?"]),
        } for i in range(display)]
        return {"total": int(r.choice([800, 5000, 30000, 200000, 900000])), "items": items}

    def trends(self, keywords: list[str], months: int = 12) -> dict:
        out = {}
        for k in keywords:
            r = _rng("trend" + k)
            out[k] = {"trend": r.uniform(-0.3, 0.3), "seasonality": r.uniform(1.0, 2.6), "months": months}
        return out


def _fake_relative(self, anchor: str, keywords: list[str]) -> dict:
    return {k: _rng("rel" + k).uniform(0.05, 3.0) for k in keywords}


FakeHub.relative_last_month = _fake_relative


class FakeYouTube:
    used = 0

    def keyword(self, keyword: str, n: int = 10, outlier_ratio: float = 3.0) -> dict:
        r = _rng("yt" + keyword)
        self.used += 102
        videos = []
        for i in range(n):
            subs = r.choice([900, 5000, 40000, 300000])
            views = int(subs * r.uniform(0.05, 6))
            videos.append({
                "title": f"[예시] {keyword} 영상 {i + 1}", "channel": f"예시채널{r.randint(1, 20)}",
                "published": "2026-01-01", "views": views, "subscribers": subs,
                "views_per_sub": views / subs, "outlier": views / subs >= outlier_ratio, "url": "",
            })
        videos.sort(key=lambda v: v["views"], reverse=True)
        return {"total": r.randint(1000, 100000), "videos": videos}
