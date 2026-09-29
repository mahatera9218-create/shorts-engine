"""네이버 검색광고 API — 키워드 도구 (KICKOFF 1주차 2번).

씨앗 → 연관 키워드, 월간 검색량(PC·모바일), 월평균 클릭수, 경쟁도, 노출 광고 수.
서명: base64(HMAC-SHA256(비밀키, "{timestamp}.{METHOD}.{uri}")).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from .common import request_json, secret

URI = "/keywordstool"
MAX_HINTS = 5  # 한 번에 보낼 수 있는 씨앗 수 (공식 제한)

COMP_IDX = {"낮음": 1, "중간": 2, "높음": 3}


def sign(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}".encode()
    digest = hmac.new(secret_key.encode(), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def to_number(value) -> float:
    """검색량·클릭수는 숫자 또는 "< 10" 같은 문자열로 온다. "< 10"은 5로 본다."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.startswith("<"):
        return 5.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize(row: dict) -> dict:
    pc = to_number(row.get("monthlyPcQcCnt"))
    mobile = to_number(row.get("monthlyMobileQcCnt"))
    return {
        "keyword": row.get("relKeyword", ""),
        "volume_pc": pc,
        "volume_mobile": mobile,
        "volume": pc + mobile,
        "clicks": to_number(row.get("monthlyAvePcClkCnt")) + to_number(row.get("monthlyAveMobileClkCnt")),
        "ctr_mobile": to_number(row.get("monthlyAveMobileCtr")),
        "competition": row.get("compIdx", ""),
        "competition_level": COMP_IDX.get(row.get("compIdx", ""), 0),
        "ad_depth": to_number(row.get("plAvgDepth")),
    }


class KeywordTool:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = secret("NAVER_AD_API_KEY")
        self.secret_key = secret("NAVER_AD_SECRET_KEY")
        self.customer_id = secret("NAVER_AD_CUSTOMER_ID")

    def _headers(self, method: str) -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "X-Timestamp": ts,
            "X-API-KEY": self.api_key,
            "X-Customer": self.customer_id,
            "X-Signature": sign(ts, method, URI, self.secret_key),
        }

    def related(self, seeds: list[str]) -> list[dict]:
        """씨앗 최대 5개 → 연관 키워드 목록. 씨앗의 띄어쓰기는 API가 받지 않아 뺀다."""
        rows: list[dict] = []
        for i in range(0, len(seeds), MAX_HINTS):
            batch = [s.replace(" ", "") for s in seeds[i:i + MAX_HINTS]]
            data = request_json("GET", self.base_url + URI, headers=self._headers("GET"),
                                params={"hintKeywords": ",".join(batch), "showDetail": "1"})
            rows.extend(normalize(r) for r in data.get("keywordList", []))
            time.sleep(0.3)  # 호출 간격 (한도 보호)
        return rows
