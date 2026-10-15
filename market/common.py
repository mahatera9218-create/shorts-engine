"""공통: 설정 읽기, 비밀 값 읽기, HTTP 호출.

비밀 값은 환경 변수(GitHub Secrets → 워크플로 env)로만 받는다.
값 자체는 절대 출력·저장하지 않는다. 있는지 없는지만 보고한다.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

# KICKOFF.md 규칙 2의 이름과 똑같이 맞춘다.
SECRET_GROUPS = {
    "naver_ad": ["NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY", "NAVER_AD_CUSTOMER_ID"],
    "naver_hub": ["NCP_APIGW_API_KEY_ID", "NCP_APIGW_API_KEY"],
    "youtube": ["YOUTUBE_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "wordpress": ["WP_URL", "WP_USER", "WP_APP_PASSWORD"],
}


class ApiError(RuntimeError):
    """API 호출 실패. 메시지에 비밀 값을 넣지 않는다."""


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def secret(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def missing_secrets(group: str) -> list[str]:
    return [n for n in SECRET_GROUPS[group] if not secret(n)]


def request_json(method: str, url: str, *, headers=None, params=None, json=None,
                 retries: int = 3, timeout: int = 20):
    """재시도(429·5xx)를 포함한 HTTP 호출. 실패하면 상태 코드와 응답 앞부분만 알린다."""
    last = None
    for attempt in range(retries):
        try:
            resp = requests.request(method, url, headers=headers, params=params,
                                    json=json, timeout=timeout)
        except requests.RequestException as e:
            last = f"연결 실패: {type(e).__name__}"
        else:
            if resp.status_code == 200:
                return resp.json()
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(2 ** attempt)
    # URL의 쿼리 문자열은 키가 들어갈 수 있으므로(유튜브) 경로까지만 남긴다.
    raise ApiError(f"{method} {url.split('?')[0]} → {last}")
