"""NAVER API HUB (네이버 클라우드) — 블로그 검색, 데이터랩 검색어 트렌드·쇼핑 인사이트.

KICKOFF 1주차 3번. 인증 헤더: X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY.
파라미터·응답은 기존 개발자센터 API와 같다고 안내되어 있다. 주소는 config/global.yaml.
"""
from __future__ import annotations

import html
import re
import time
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

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
            "description": clean(it.get("description")),
        } for it in data.get("items", [])]
        time.sleep(0.1)
        return {"total": int(count.get("total", 0)), "total_date_sort": int(data.get("total", 0)), "items": items}

    def news(self, query: str, display: int = 50) -> list[dict]:
        """뉴스 검색 최신순. 제목·요약문·원문 주소·발행일만 받는다 (허용된 통로, 기사 본문은 받지 않음)."""
        data = request_json("GET", self.base + self.paths["news_search"], headers=self._headers(),
                            params={"query": query, "display": display, "sort": "date"})
        time.sleep(0.1)
        out = []
        for it in data.get("items", []):
            try:
                day = parsedate_to_datetime(it.get("pubDate", "")).date().isoformat()
            except (TypeError, ValueError):
                day = ""
            out.append({"title": clean(it.get("title")), "description": clean(it.get("description")),
                        "link": it.get("originallink") or it.get("link", ""), "date": day})
        return out

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

    def relative_last_month(self, anchor: str, keywords: list[str]) -> dict[str, float]:
        """지난달 검색량을 기준 키워드 대비 비율로 돌려준다 (기준 = 1.0).

        데이터랩 값은 한 요청 안의 최댓값을 100으로 맞춘 상대값이라, 요청마다 기준 키워드를 함께 넣어 비율을 잰다.
        """
        end = date.today().replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        out: dict[str, float] = {}
        for i in range(0, len(keywords), MAX_GROUPS - 1):
            batch = keywords[i:i + MAX_GROUPS - 1]
            body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "month",
                    "keywordGroups": [{"groupName": k, "keywords": [k]} for k in [anchor] + batch]}
            data = request_json("POST", self.base + self.paths["search_trend"],
                                headers={**self._headers(), "Content-Type": "application/json"}, json=body)
            last = {r.get("title", ""): (float(r["data"][-1].get("ratio", 0)) if r.get("data") else 0.0)
                    for r in data.get("results", [])}
            base = last.get(anchor, 0.0)
            for k in batch:
                out[k] = last.get(k, 0.0) / base if base > 0 else 0.0
            time.sleep(0.1)
        return out

    def rise(self, keywords: list[str], recent: int = 3, base: int = 11) -> dict[str, dict]:
        """최근 며칠 검색 상승 (착장 도우미 '오늘 뜨는 연예인', 2026-10-10). 일 단위 검색어 트렌드 최근 recent+base일로
        {키워드: {"rise": 최근 recent일 평균 ÷ 그 전 base일 평균, "level": 최근 평균(그 요청 안 상대값)}}. 값이 없으면 빠짐."""
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=recent + base - 1)
        out: dict[str, dict] = {}
        for i in range(0, len(keywords), MAX_GROUPS):
            batch = keywords[i:i + MAX_GROUPS]
            body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "date",
                    "keywordGroups": [{"groupName": k, "keywords": [k]} for k in batch]}
            data = request_json("POST", self.base + self.paths["search_trend"],
                                headers={**self._headers(), "Content-Type": "application/json"}, json=body)
            for res in data.get("results", []):
                vals = [float(p.get("ratio", 0)) for p in res.get("data", [])]
                if len(vals) < recent + 1:
                    continue
                now, before = vals[-recent:], vals[:-recent]
                b = sum(before) / len(before) if before else 0.0
                n = sum(now) / len(now)
                out[res.get("title", "")] = {"rise": round(n / b, 2) if b > 0 else (9.9 if n > 0 else 0.0), "level": round(n, 1)}
            time.sleep(0.1)
        return out

    def shopping_rank(self, category: str, keywords: list[str], anchor: str, recent: int = 7, base: int = 21) -> dict[str, dict]:
        """쇼핑 인사이트 분야(category) 안에서 상품 키워드들의 '지금 많이 찾는 정도'(계절 인기)와 최근 상승률.
        데이터랩은 한 요청 안 키워드끼리만 상대값(최대 100)이라, 모든 배치에 anchor를 함께 넣어 anchor=100으로 맞춰 배치 간 비교 가능하게 한다.
        {상품: {"level": 지금 인기(anchor 기준), "rise": 최근 recent일 ÷ 그 전 base일}}. (대표 요청 2026-10-10 '계절 인기 상품 + 셀럽')."""
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=recent + base - 1)
        others = [k for k in keywords if k != anchor]
        out: dict[str, dict] = {}
        for i in range(0, len(others), MAX_GROUPS - 1):
            batch = [anchor] + others[i:i + MAX_GROUPS - 1]
            body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "date",
                    "category": category, "keyword": [{"name": k, "param": [k]} for k in batch]}
            data = request_json("POST", self.base + self.paths["shopping_keywords"],
                                headers={**self._headers(), "Content-Type": "application/json"}, json=body)
            levels = {}
            for res in data.get("results", []):
                vals = [float(p.get("ratio", 0)) for p in res.get("data", [])]
                title = res.get("title", "")
                now = sum(vals[-recent:]) / recent if len(vals) >= recent else (sum(vals) / len(vals) if vals else 0.0)
                before = sum(vals[:-recent]) / max(1, len(vals) - recent) if len(vals) > recent else 0.0
                levels[title] = (now, round(now / before, 2) if before > 0 else (9.9 if now > 0 else 0.0))
            an = levels.get(anchor, (0.0, 0.0))[0] or 1.0  # anchor를 100으로
            for k, (now, rise) in levels.items():
                if k == anchor:
                    continue
                out[k] = {"level": round(now / an * 100, 1), "rise": rise}
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
