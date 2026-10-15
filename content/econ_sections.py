"""경제 키워드 섹션 나누기 (대표 결정 2026-10-09: 국내주식 / 해외주식 / 금·비트코인, 섹션마다 3개).
2026-10-10 대표 요청으로 부동산 / 환율 / 생활경제(금리·물가·기름값·통계) 추가, 정부 지원금·정책 안내는 섹션에서 뺌.
판별은 코드(정규식)로 한다 (14장). 같은 회사(첫 단어)는 섹션마다 1개만 — 삼성전자·하이닉스만 나오지 않게."""
from __future__ import annotations

import re

COIN_GOLD = re.compile(r"비트코인|이더리움|리플|XRP|솔라나|도지|코인|가상자산|가상화폐|암호화폐|스테이블|업비트|빗썸|"
                       r"금값|금 ?시세|금 ?가격|^금 |금 투자|금ETF|골드|은값|은 ?시세|KRX ?금", re.I)
OVERSEAS = re.compile(r"미국|뉴욕|나스닥|S&P|다우|엔비디아|테슬라|애플|마이크로소프트|알파벳|구글|아마존|메타|팔란티어|브로드컴|"
                      r"아이온큐|마이크론|넷플릭스|AMD|인텔|TSMC|일라이릴리|노보노디스크|오픈AI|코인베이스|브로드컴|일본 ?증시|닛케이|중국 ?증시|항셍|해외주식|미국주식|서학개미|ADR", re.I)
DOMESTIC = re.compile(r"코스피|코스닥|주가|목표가|실적|영업이익|배당|공모주|상장|삼성|하이닉스|LG|현대|SK|카카오|네이버|셀트리온|"
                      r"한화|두산|포스코|POSCO|기아|한미약품|효성|알테오젠|에코프로|HLB|삼양|고려아연|유한양행|아모레|하이브|크래프톤|엔씨|"
                      r"레인보우|LS일렉트릭|KB금융|신한|하나금융|우리금융|메리츠|대한항공|한국전력|KT|외국인 ?매도|외국인 ?매수|국내주식|동학개미|ETF")
POLICY = re.compile(r"지원금|지원사업|보조금|바우처|수당|정책|신청 ?방법|신청 ?기간|대상자|지급일|소비쿠폰|민생")  # 대표 결정 2026-10-10: 정부 지원금·정책류는 안 씀
REALTY = re.compile(r"아파트|부동산|집값|전세|월세|청약|분양|재건축|재개발|매매가|실거래|공시가|주담대|주택담보|오피스텔|빌라|입주|미분양|토지거래|LTV|DSR")
# 세무·절세 (대표 결정 2026-10-14): 부동산 세금 / 금융 세금으로 나눠 순번에 쓴다.
TAX_REALTY_RE = re.compile(r"양도소득세|양도세|종합부동산세|종부세|재산세|취득세|상속세|증여세|1세대 ?1주택|비과세|양도차익|보유세")
TAX_FINANCE_RE = re.compile(r"ISA|개인종합자산관리|연금저축|IRP|퇴직연금|금융소득종합과세|금소세|배당소득세|이자소득세|세액공제|연말정산|분리과세|비과세종합저축", re.I)
FX = re.compile(r"환율|달러|엔화|엔저|원화|위안|유로화|환전|원/달러|원·달러", re.I)
LIVING = re.compile(r"금리|물가|CPI|기름값|휘발유|경유|유가|전기요금|가스요금|장바구니|외식비|라면값|최저임금|연봉|월급|통계|고용|실업률|가계부채|"
                    r"GDP|성장률|수출|FOMC|연준|국채|예금|적금|파킹통장|연금|건강보험료|생활비|평균|순자산|가계", re.I)
MACRO = LIVING  # 옛 이름
AREA = {"국내주식": "국내주식", "미국주식": "해외주식", "해외주식": "해외주식", "비트코인": "금·비트코인", "금": "금·비트코인",
        "코인": "금·비트코인", "부동산": "부동산", "환율": "환율", "생활경제": "생활경제", "거시·환율": "생활경제", "돈굴리기": "생활경제"}


def section(it: dict) -> str:
    """'국내주식' | '해외주식' | '금·비트코인' | '부동산' | '환율' | '생활경제' | '' (정부 지원금·정책·분류 안 되는 것)."""
    t = it.get("kw", "")
    if POLICY.search(t):
        return ""
    if COIN_GOLD.search(t):
        return "금·비트코인"
    if REALTY.search(t):
        return "부동산"
    if FX.search(t):
        return "환율"
    if LIVING.search(t):
        return "생활경제"
    if OVERSEAS.search(t):
        return "해외주식"
    area = AREA.get((it.get("area") or "").strip(), "")
    if area:
        return area
    return "국내주식" if DOMESTIC.search(t) else ""


def tax_kind(it: dict) -> str:
    """'세무-부동산' | '세무-금융' | '' (세무 키워드 판별; 순번 세무 블록용, 2026-10-14)."""
    t = it.get("kw", "")
    if TAX_REALTY_RE.search(t):
        return "세무-부동산"
    if TAX_FINANCE_RE.search(t):
        return "세무-금융"
    return ""


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
