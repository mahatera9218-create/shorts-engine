"""지식iN 답변 후보 수집 — 네이버 공식 검색 API(API HUB /search/v1/kin)로 최신 질문을 모은다.

대표 결정 2026-10-20: 어사이드(브라우저 AI)는 토큰을 많이 써서 상시 가동이 어렵다.
→ 질문 '찾기'는 공식 검색 API로(크롤링 아님, AI 비용 0), 답변 '초안'은 새벽 Claude 예약 작업이,
   '게시'는 대표가 손으로 한다(자동 게시 금지: 스팸 판정·아이디 정지 위험, DECISIONS 2026-10-18).

결과: reports/지식인-후보.md (새 후보를 위에 쌓음, 이미 본 링크는 다시 넣지 않음)
API는 질문 제목과 요약 몇 줄만 준다. 게시 전 링크를 열어 원문 확인은 사람이 한다.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market.common import load_yaml, request_json, secret

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "지식인-후보.md"
KST = timezone(timedelta(hours=9))
TAG = re.compile(r"<[^>]+>")

# 키워드 → 우리 글/도구 주소(초안에 붙일 링크). 지시문 docs/prompts/aside-지식인-답변.md 의 주소표와 같은 것.
KEYWORDS: dict[str, list[str]] = {
    "피부양자 자격": ["https://astacgroup.com/tools/dependent-nhis"],
    "피부양자 탈락": ["https://astacgroup.com/tools/dependent-nhis"],
    "1주택 양도세 비과세": ["https://astacgroup.com/yangdose-1jutaek-bigwase"],
    "취득세 계산": ["https://astacgroup.com/chwideukse-seyul-jutaek"],
    "생애최초 취득세 감면": ["https://astacgroup.com/iljose-gamse-saengae-choecho"],
    "종부세 1주택": ["https://astacgroup.com/jongbuse-gibon-gongje"],
    "재산세 납부": ["https://astacgroup.com/jaesan-se-nap-gi"],
    "증여세 공제 한도": [],
    "ISA 계좌 비과세": ["https://astacgroup.com/isa-gyejwa-hyetaek-2026"],
    "연금저축 세액공제": ["https://astacgroup.com/yeongeum-irp-semuchul-gongje-2026"],
    "주택 임대소득 신고": ["https://astacgroup.com/tools/rental-income"],
    "스마트스토어 간이과세": ["https://astacgroup.com/tools/seller-vat"],
    "블로그 수익 사업자등록": ["https://astacgroup.com/tools/creator-business"],
}
PER_KEYWORD = 3   # 키워드마다 최신 질문 최대 몇 개
KEEP = 60         # 파일에 남길 후보 수(오래된 건 아래로 밀려 잘림)


def _hub() -> tuple[str, dict] | None:
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    base = load_yaml("global.yaml")["endpoints"]["naver_hub"]["base"].rstrip("/")
    return base + "/search/v1/kin", {"X-NCP-APIGW-API-KEY-ID": secret("NCP_APIGW_API_KEY_ID"),
                                     "X-NCP-APIGW-API-KEY": secret("NCP_APIGW_API_KEY")}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", s or ""))).strip()


def seen_links(text: str) -> set[str]:
    return set(re.findall(r"^- 링크: (\S+)", text, re.M))


def collect() -> int:
    hub = _hub()
    if not hub:
        print("NCP_APIGW 키가 없어 수집을 건너뜁니다.")
        return 0
    url, headers = hub
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    seen = seen_links(old)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    blocks, errors = [], 0
    for kw, links in KEYWORDS.items():
        try:
            items = request_json("GET", url, headers=headers,
                                 params={"query": kw, "display": 20, "sort": "date"}).get("items", [])
        except Exception as e:
            errors += 1
            print(f"  실패 ({kw}): {str(e)[:200]}")
            continue
        n = 0
        for it in items:
            link = it.get("link") or ""
            if not link or link in seen:
                continue
            seen.add(link)
            blocks.append(
                f"### [{today}] {clean(it.get('title'))}\n"
                f"- 키워드: {kw}\n- 링크: {link}\n- 요약: {clean(it.get('description'))}\n"
                f"- 붙일 링크: {', '.join(links) if links else '(관련 글 없음 — 링크 없이 답변)'}\n"
                f"- 상태: 후보\n"
            )
            n += 1
            if n >= PER_KEYWORD:
                break
        print(f"  {kw}: 새 후보 {n}개")
    if errors == len(KEYWORDS):
        raise SystemExit("모든 키워드에서 API 호출 실패 — 지식iN 검색이 API HUB에 없거나 키 권한 문제일 수 있습니다.")
    old_blocks = re.findall(r"^### .*?(?=^### |\Z)", old, re.M | re.S)
    allb = blocks + [b.rstrip() + "\n" for b in old_blocks]
    head = ("# 지식iN 답변 후보 (자동 수집)\n\n"
            "네이버 공식 검색 API로 매일 모은 최신 질문. 새벽 Claude 예약 작업이 여기서 골라 "
            "`reports/지식인-답변-queue.md`에 답변 초안을 쌓는다. 게시는 대표가 직접(하루 2~3개).\n\n")
    OUT.write_text(head + "\n".join(allb[:KEEP]), encoding="utf-8")
    print(f"새 후보 {len(blocks)}개 추가 (총 {min(len(allb), KEEP)}개 보관)")
    return len(blocks)


if __name__ == "__main__":
    collect()
