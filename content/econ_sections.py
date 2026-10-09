"""경제 키워드 섹션 나누기 (대표 결정 2026-10-09: 국내주식 / 해외주식 / 금·비트코인, 섹션마다 3개, 75점 미만은 안 보임).
판별은 코드(정규식)로 한다 (14장). 같은 회사(첫 단어)는 섹션마다 1개만 — 삼성전자·하이닉스만 나오지 않게."""
from __future__ import annotations

import re

COIN_GOLD = re.compile(r"비트코인|이더리움|리플|XRP|솔라나|도지|코인|가상자산|가상화폐|암호화폐|스테이블|업비트|빗썸|"
                       r"금값|금 ?시세|금 ?가격|^금 |금 투자|금ETF|골드|은값|은 ?시세|KRX ?금", re.I)
OVERSEAS = re.compile(r"미국|뉴욕|나스닥|S&P|다우|엔비디아|테슬라|애플|마이크로소프트|알파벳|구글|아마존|메타|팔란티어|브로드컴|"
                      r"아이온큐|마이크론|넷플릭스|AMD|인텔|TSMC|일본 ?증시|닛케이|중국 ?증시|항셍|해외주식|미국주식|서학개미|ADR", re.I)
DOMESTIC = re.compile(r"코스피|코스닥|주가|목표가|실적|영업이익|배당|공모주|상장|삼성|하이닉스|LG|현대|SK|카카오|네이버|셀트리온|"
                      r"한화|두산|포스코|기아|외국인 ?매도|외국인 ?매수|국내주식|동학개미|ETF")
MACRO = re.compile(r"국채|금리|환율|FOMC|CPI|물가|연준|기준금리|고용지표")  # 거시는 섹션 없음
AREA = {"국내주식": "국내주식", "미국주식": "해외주식", "해외주식": "해외주식", "비트코인": "금·비트코인", "금": "금·비트코인",
        "코인": "금·비트코인"}


def section(it: dict) -> str:
    """'국내주식' | '해외주식' | '금·비트코인' | '' (그 밖: 거시·환율·돈굴리기는 섹션 없음)."""
    t = it.get("kw", "")
    if COIN_GOLD.search(t):
        return "금·비트코인"
    if MACRO.search(t) or (it.get("area") or "") in ("거시·환율", "돈굴리기"):
        return ""
    if OVERSEAS.search(t):
        return "해외주식"
    area = AREA.get((it.get("area") or "").strip(), "")
    if area:
        return area
    return "국내주식" if DOMESTIC.search(t) else ""


def company(it: dict) -> str:
    """같은 회사 판별용 첫 단어 (삼성전자 3분기 실적 / 삼성전자 성과급 → 삼성전자)."""
    return re.sub(r"\s+", " ", (it.get("core") or it.get("kw", ""))).split(" ")[0].lower()


def pick(items: list[dict], sections: list[str], n: int = 3, min_score: int = 75) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {s: [] for s in sections}
    seen: dict[str, set[str]] = {s: set() for s in sections}
    for it in sorted(items, key=lambda x: -x.get("score", 0)):
        s = section(it)
        if s not in out or it.get("score", 0) < min_score or len(out[s]) >= n or company(it) in seen[s]:
            continue
        seen[s].add(company(it))
        out[s].append(it)
    return out
