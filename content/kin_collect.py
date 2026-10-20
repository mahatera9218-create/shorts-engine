"""지식iN 답변 후보 수집 — 네이버 공식 검색 API(API HUB /search/v1/kin)로 최신 질문을 모은다.

대표 결정 2026-10-20: 어사이드(브라우저 AI)는 토큰을 많이 써서 상시 가동이 어렵다.
→ 질문 '찾기'는 공식 검색 API로(크롤링 아님, AI 비용 0), 답변 '초안'은 새벽 Claude 예약 작업이,
   '게시'는 대표가 손으로 한다(자동 게시 금지: 스팸 판정·아이디 정지 위험, DECISIONS 2026-10-18).

결과: reports/지식인-후보.md (새 후보를 위에 쌓음, 이미 본 질문은 docId로 걸러 다시 넣지 않음)
답변이 많은 질문(붐빔)은 제외한다: 공식 검색은 답변 달린 글을 색인하므로 링크의 answerNo가
그 질문 답변 개수의 하한선이다. answerNo가 큰 질문은 우리 답이 묻히므로 담지 않는다(대표 지적 2026-10-20).
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
PER_KEYWORD = 3   # 키워드마다 담을 질문 최대 몇 개
KEEP = 60         # 파일에 남길 후보 수(오래된 건 아래로 밀려 잘림)
MAX_ANSWERS = 2   # 검색에 잡힌 답변 번호(answerNo)가 이보다 크면 '이미 답변 많음'으로 보고 제외.
                  # 공식 검색 API는 답변 달린 글을 색인하므로, answerNo는 그 질문의 답변 개수 하한선이다.
                  # 답변이 적은 질문이라야 우리 답이 채택·노출될 가능성이 있다(대표 지적 2026-10-20).


def _hub() -> tuple[str, dict] | None:
    if not (secret("NCP_APIGW_API_KEY_ID") and secret("NCP_APIGW_API_KEY")):
        return None
    base = load_yaml("global.yaml")["endpoints"]["naver_hub"]["base"].rstrip("/")
    return base + "/search/v1/kin", {"X-NCP-APIGW-API-KEY-ID": secret("NCP_APIGW_API_KEY_ID"),
                                     "X-NCP-APIGW-API-KEY": secret("NCP_APIGW_API_KEY")}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", s or ""))).strip()


def doc_id(link: str) -> str:
    """질문 링크에서 docId(질문 고유번호)를 뽑는다. 같은 질문은 답변 번호가 달라도 하나로 본다."""
    m = re.search(r"docId=(\d+)", link or "")
    return m.group(1) if m else (link or "")


def answer_no(link: str) -> int:
    """링크의 answerNo. 검색이 이 번호의 답변을 매칭했다는 뜻 → 답변 개수의 하한선."""
    m = re.search(r"answerNo=(\d+)", link or "")
    return int(m.group(1)) if m else 0


def question_link(link: str) -> str:
    """answerNo를 떼어 질문 맨 위로 열리는 링크로 만든다(특정 답변으로 스크롤되지 않게)."""
    return re.sub(r"[?&]answerNo=\d+", "", link or "")


def seen_doc_ids(text: str) -> set[str]:
    """이미 후보 파일에 있는 질문들의 docId(과거 링크 형식도 docId로 통일)."""
    return {doc_id(l) for l in re.findall(r"^- (?:링크|바로가기): (\S+)", text, re.M)}


def collect() -> int:
    hub = _hub()
    if not hub:
        print("NCP_APIGW 키가 없어 수집을 건너뜁니다.")
        return 0
    url, headers = hub
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    seen = seen_doc_ids(old)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    # 1차: 질문(docId)별로 모은다. 같은 질문의 answerNo 중 '최대'가 답변 개수의 하한선.
    agg: dict[str, dict] = {}
    errors = 0
    for kw, links in KEYWORDS.items():
        try:
            items = request_json("GET", url, headers=headers,
                                 params={"query": kw, "display": 20, "sort": "date"}).get("items", [])
        except Exception as e:
            errors += 1
            print(f"  실패 ({kw}): {str(e)[:200]}")
            continue
        for it in items:
            link = it.get("link") or ""
            did = doc_id(link)
            if not link or did in seen:
                continue
            ano = answer_no(link)
            cur = agg.get(did)
            if cur is None:
                agg[did] = {"kw": kw, "links": links, "title": clean(it.get("title")),
                            "desc": clean(it.get("description")), "max_ano": ano,
                            "qlink": question_link(link)}
            else:
                cur["max_ano"] = max(cur["max_ano"], ano)
    if errors == len(KEYWORDS):
        raise SystemExit("모든 키워드에서 API 호출 실패 — 지식iN 검색이 API HUB에 없거나 키 권한 문제일 수 있습니다.")
    # 2차: 답변 많은 질문(붐빔) 제외 → 키워드별로 최신순(sort=date 순서 유지) PER_KEYWORD개까지.
    blocks, per_kw, crowded = [], {}, 0
    for did, d in agg.items():
        if d["max_ano"] > MAX_ANSWERS:
            crowded += 1
            continue
        if per_kw.get(d["kw"], 0) >= PER_KEYWORD:
            continue
        per_kw[d["kw"]] = per_kw.get(d["kw"], 0) + 1
        seen.add(did)
        ans_txt = "0~1개" if d["max_ano"] <= 1 else f"{d['max_ano']}개"
        blocks.append(
            f"### [{today}] {d['title']}\n"
            f"- 키워드: {d['kw']}\n- 바로가기: {d['qlink']}\n"
            f"- 답변수(검색상): {ans_txt}\n- 요약: {d['desc']}\n"
            f"- 붙일 링크: {', '.join(d['links']) if d['links'] else '(관련 글 없음 — 링크 없이 답변)'}\n"
            f"- 상태: 후보\n"
        )
    for kw in KEYWORDS:
        print(f"  {kw}: 새 후보 {per_kw.get(kw, 0)}개")
    if crowded:
        print(f"  (답변 많아 제외: {crowded}개)")
    old_blocks = re.findall(r"^### .*?(?=^### |\Z)", old, re.M | re.S)
    allb = blocks + [b.rstrip() + "\n" for b in old_blocks]
    head = ("# 지식iN 답변 후보 (자동 수집)\n\n"
            "네이버 공식 검색 API(sort=date)로 모은 최신 질문 중 **답변이 적은(검색상 2개 이하) 것만** 담는다. "
            "Claude 예약 작업이 여기서 골라 `reports/지식인-답변-queue.md`에 답변 초안을 쌓는다. 게시는 대표가 직접(하루 2~3개).\n\n")
    OUT.write_text(head + "\n".join(allb[:KEEP]), encoding="utf-8")
    print(f"새 후보 {len(blocks)}개 추가 (총 {min(len(allb), KEEP)}개 보관)")
    return len(blocks)


if __name__ == "__main__":
    collect()
