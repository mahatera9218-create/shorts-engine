"""NAVER API HUB (네이버 클라우드) — 블로그 검색, 데이터랩 검색어 트렌드·쇼핑 인사이트.

KICKOFF 1주차 3번. 인증 헤더: X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY.
파라미터·응답은 기존 개발자센터 API와 같다고 안내되어 있다. 주소는 config/global.yaml.
"""
from __future__ import annotations

import html
import re
import time
from datetime import date, timedelta

from .common import request_json, secret

TAG = re.compile(r"<[^>]+>")
MAX_GROUPS = 5  # 데이터랩 한 번에 보낼 수 있는 키워드 묶음 수


def clean(text: str) -> str:
    return html.unescape(TAG.sub("", text or "")).strip()


def trend_direction(ratios: list[float]) -> float:
    """최근 3개월 평균 ÷ 1년 전 같은 3개월 평균 − 1 (계절 효과 제거). 데이터가 15개월 미만이면 0."""
    if len(ratios) < 15:
        return 0.0
    recent = sum(ratios[-3:]) / 3
    year_ago = sum(ratios[-15:-12]) / 3
    if year_ago <= 0:
        return 0.0
    return recent / year_ago - 1


def seasonality(ratios: list[float]) -> float:
    """최근 12개월 최고 ÷ 평균. 1에 가까우면 사계절 수요, 크면 계절성이 강함."""
    ratios = ratios[-12:]
    if not ratios:
        return 0.0
    avg = sum(ratios) / len(ratios)
    return max(ratios) / avg if avg > 0 else 0.0


class ApiHub:
    def __init__(self, endpoints: dict):
        self.base = endpoints["base"].rstrip("/")
        self.paths = endpoints

    def _headers(self) -> dict:
        return {
            "X-NCP-APIGW-API-KEY-ID": secret("NCP_APIGW_API_KEY_ID"),
            "X-NCP-APIGW-API-KEY": secret("NCP_APIGW_API_KEY"),
        }

    def blog(self, keyword: str, display: int = 100) -> dict:
        """전체 문서 수 + 최신 글 N개(최신순) 제목·발행일·블로그명.

        정확도순 상위는 실제 검색 화면의 상위와 달라(2026-09-29 확인) 글 목록은 최신순으로 받는다.
        최신 글의 발행일로 '최근 새 글이 얼마나 올라오는가'(경쟁 활동량)를 잰다.
        문서 수(total)는 최신순이 정확도순보다 수백 배 작게 나와(같은 날 두 실행 비교) 정확도순 값을 쓴다.
        """
        url = self.base + self.paths["blog_search"]
        count = request_json("GET", url, headers=self._headers(),
                             params={"query": keyword, "display": 1, "sort": "sim"})
        time.sleep(0.1)
        data = request_json("GET", url, headers=self._headers(),
                            params={"query": keyword, "display": display, "sort": "date"})
        items = [{
            "title": clean(it.get("title")),
            "blogger": clean(it.get("bloggername")),
            "blog_link": it.get("bloggerlink", ""),
            "link": it.get("link", ""),
            "postdate": it.get("postdate", ""),
        } for it in data.get("items", [])]
        time.sleep(0.1)
        return {"total": int(count.get("total", 0)), "total_date_sort": int(data.get("total", 0)), "items": items}

    def trends(self, keywords: list[str], months: int = 12) -> dict[str, dict]:
        """키워드별 월간 상대 검색 추이 → 추세 방향·계절성. 값은 상대값(절대 검색량 아님)."""
        end = date.today().replace(day=1) - timedelta(days=1)  # 지난달 말
        start = (end.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
        out: dict[str, dict] = {}
        for i in range(0, len(keywords), MAX_GROUPS):
            batch = keywords[i:i + MAX_GROUPS]
            body = {
                "startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "month",
                "keywordGroups": [{"groupName": k, "keywords": [k]} for k in batch],
            }
            data = request_json("POST", self.base + self.paths["search_trend"],
                                headers={**self._headers(), "Content-Type": "application/json"},
                                json=body)
            for res in data.get("results", []):
                ratios = [float(p.get("ratio", 0)) for p in res.get("data", [])]
                out[res.get("title", "")] = {
                    "trend": trend_direction(ratios),
                    "seasonality": seasonality(ratios),
                    "months": len(ratios),
                }
            time.sleep(0.1)
        return out

    def shopping_category(self, name: str, category: str, months: int = 12) -> dict:
        """쇼핑 인사이트 분야별 클릭 추이. HUB 경로 미확인 → 카테고리 코드가 있을 때만 호출."""
        end = date.today().replace(day=1) - timedelta(days=1)
        start = (end.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "month",
                "category": [{"name": name, "param": [category]}]}
        data = request_json("POST", self.base + self.paths["shopping_category"],
                            headers={**self._headers(), "Content-Type": "application/json"}, json=body)
        results = data.get("results", [])
        ratios = [float(p.get("ratio", 0)) for p in (results[0].get("data", []) if results else [])]
        return {"trend": trend_direction(ratios), "seasonality": seasonality(ratios)}
