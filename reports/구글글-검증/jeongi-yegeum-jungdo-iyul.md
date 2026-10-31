# 검증 보고서: 정기예금 중도해지 이율·세금 (jeongi-yegeum-jungdo-iyul)

- 검증일: 2026-10-31
- 대상 초안: reports/구글글-초안/92-jeongi-yegeum-jungdo-iyul.md
- **최종 판정: 확인됨** (이자소득세 15.4% = 소득세 14% + 지방소득세 1.4%, 예금자보호 한도 1억원(2025.9.1 시행·상호금융 포함), 금융소득종합과세 2,000만원 기준 모두 공식 출처로 확인. 중도해지이율은 법정 숫자가 아니라 은행별 약관 사항이므로 본문에서 특정 수치를 단정하지 않고 '구조'로만 설명.)

## 검증 방법과 한계
- WebSearch를 공식 도메인(nts.go.kr, law.go.kr, fsc.go.kr, korea.kr 등)으로 한정해 교차 확인. WebFetch 직접 열람은 이 세션의 네트워크 허용 밖(www.law.go.kr ENOTFOUND)이라 불가 → 공식 도메인 검색 결과 본문으로 확인.
- 중도해지이율은 은행·상품 약관 사항(법정 고정값 없음)이라 수치 검증 대상이 아님 → 본문은 예시 구조로만 서술.

## 숫자 주장 검증표

| 번호 | 초안 문구 | 숫자 | 판정 | 출처 URL |
|---|---|---|---|---|
| 1 | 이자소득세 15.4% = 소득세 14% + 지방소득세 1.4% | 15.4% | 일치 | 국세청 원천징수 세율 — https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=2291&cntntsId=7703 |
| 2 | 지방소득세는 소득세의 10% | 10% | 일치 | 국세청 원천징수 세율(소득세 14%+지방소득세 1.4%) — https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7703 |
| 3 | 금융소득 연 2,000만원 이하면 원천징수로 종결, 초과 시 종합과세 | 2,000만원 | 일치 | 국세청 자주묻는Q&A(금융소득 종합과세) — https://call.nts.go.kr/call/qna/selectQnaInfo.do?mi=1441&ctgId=CTG11775 |
| 4 | 예금자보호 한도 1인당·금융회사별 1억원(5천만원→1억원) | 1억원 | 일치 | 금융위 보도자료 '25.9.1일부터 1억원 보호 — https://www.fsc.go.kr/no010101/84974 ; 정책뉴스 — https://www.korea.kr/news/policyNewsView.do?newsId=148946400 |
| 5 | 상향 시행일 2025년 9월 1일 | 2025.9.1 | 일치 | 금융위 보도자료 — https://www.fsc.go.kr/no010101/85200 ; korea.kr 148943235 |
| 6 | 신협·농협·수협·새마을금고 등 상호금융도 1억원 적용 | 1억원 | 일치 | korea.kr 정책뉴스(상호금융권까지 상향) — https://www.korea.kr/news/policyNewsView.do?newsId=148946400 |
| 7 | 펀드 등 실적배당형은 예금자보호 제외 | - | 일치 | korea.kr 정책뉴스(펀드 등 금융투자상품 제외) — https://www.korea.kr/news/policyNewsView.do?newsId=148946400 |
| 8 | 세금은 원금이 아니라 받은 이자에만 부과 | - | 일치 | 국세청 이자소득 원천징수(이자소득 과세) — https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6469&cntntsId=7905 |

## 결론
핵심 수치(이자소득세 15.4%, 예금자보호 1억원·시행일, 종합과세 2,000만원)가 모두 공식 출처로 확인됨. 중도해지이율은 법정 수치가 아니라 은행 약관 사항이라 본문에서 단정하지 않고 구조로만 설명 → **확인됨**.
