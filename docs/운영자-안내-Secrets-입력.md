# 운영자 안내 · API 키 입력과 시장조사 실행 (휴대폰 기준)

대표님이 하실 일은 **① 키 발급 → ② GitHub에 키 넣기 → ③ 실행 버튼** 세 가지입니다.
키는 **GitHub Secrets에만** 넣습니다. 채팅·메모·사진으로 저에게 보내지 마세요.

> 휴대폰 **GitHub 앱에는 Secrets 입력 화면이 없습니다.** 크롬·사파리 같은 **브라우저**로 github.com에 들어가세요.
> 네이버 광고 시스템·구글 콘솔 화면이 잘리면 브라우저 메뉴에서 **"데스크톱 사이트"**를 켜세요. 태블릿이 더 편합니다.

---

## ① 키 발급 (한 번만)

### A. 네이버 검색광고 API → 키 3개 (필수)

1. searchad.naver.com 로그인 (검색광고 계정이 없으면 가입 — **계정 생성은 대표님 결정**)
2. **광고시스템** 들어가기
3. 위쪽 메뉴 **도구 → API 사용 관리**
4. **네이버 검색광고 API 서비스 신청** 누르기
5. 화면에 나온 세 값을 확인 (복사는 ②단계에서 하나씩)
   - 액세스라이선스 → `NAVER_AD_API_KEY`
   - 비밀키 (보기 버튼) → `NAVER_AD_SECRET_KEY`
   - CUSTOMER_ID (숫자) → `NAVER_AD_CUSTOMER_ID`

광고비를 쓰지 않아도 키워드 도구 API는 쓸 수 있습니다.

### B. NAVER API HUB (네이버 클라우드) → 키 2개 (필수)

1. ncloud.com 회원가입·로그인 — **가입 시 결제 수단 등록을 요구할 수 있습니다.** 지금은 한시적 무료이며, 유료 전환 시 사전 공지됩니다. 결제 수단 등록이 필요하면 진행 여부를 먼저 정해주세요.
2. **콘솔** → Services → Application Services → **NAVER API HUB**
3. **이용 신청** → **Application 등록**
4. 사용할 API 선택 (세 개 모두 체크)
   - 검색 → **블로그**
   - 데이터랩 → **검색어 트렌드**
   - 데이터랩 → **쇼핑 인사이트**
5. 등록한 Application의 **인증 정보** 확인
   - Client ID → `NCP_APIGW_API_KEY_ID`
   - Client Secret → `NCP_APIGW_API_KEY`

### C. 유튜브 Data API → 키 1개 (없어도 실행은 됨)

없으면 유튜브 조회만 건너뛰고 네이버 데이터로 점수를 냅니다. 여유 있을 때 하셔도 됩니다.

1. console.cloud.google.com 로그인 → 위쪽 **프로젝트 선택 → 새 프로젝트** (이름 아무거나)
2. 왼쪽 메뉴 **API 및 서비스 → 라이브러리** → "YouTube Data API v3" 검색 → **사용**
3. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키**
4. 만든 키의 **키 수정 → API 제한사항 → 키 제한 → YouTube Data API v3만 선택 → 저장** (키가 새도 다른 곳에 못 쓰게)
5. 키 값 → `YOUTUBE_API_KEY`

무료 한도(하루 10,000단위) 안에서만 씁니다. 결제 정보는 필요 없습니다.

---

## ② GitHub에 키 넣기 (키마다 반복)

1. 브라우저로 **github.com/mahatera9218-create/shorts-engine** 열기
2. 저장소 위쪽 탭 줄을 옆으로 밀어 **Settings** 누르기 (안 보이면 **⋯** 안에 있음)
3. 왼쪽(또는 아래) 메뉴 **Secrets and variables → Actions**
4. 초록 버튼 **New repository secret**
5. **Name** 칸에 아래 표의 이름을 **글자 그대로** 입력 (대문자·밑줄 포함)
6. **Secret** 칸에 발급받은 값 붙여넣기 → **Add secret**
7. 다음 키로 4번부터 반복

| Name (그대로 입력) | 넣을 값 | 필수 |
| --- | --- | --- |
| `NAVER_AD_API_KEY` | 검색광고 액세스라이선스 | ✅ |
| `NAVER_AD_SECRET_KEY` | 검색광고 비밀키 | ✅ |
| `NAVER_AD_CUSTOMER_ID` | 검색광고 CUSTOMER_ID | ✅ |
| `NCP_APIGW_API_KEY_ID` | API HUB Client ID | ✅ |
| `NCP_APIGW_API_KEY` | API HUB Client Secret | ✅ |
| `YOUTUBE_API_KEY` | 유튜브 API 키 | 선택 |
| `ANTHROPIC_API_KEY` | Claude API 키 | 2주차부터 |

넣은 값은 다시 볼 수 없습니다(정상). 잘못 넣었으면 이름 옆 **연필 → 새 값 입력**으로 덮어씁니다.

---

## ③ 시장조사 실행

1. 저장소 위쪽 **Actions** 탭
2. 왼쪽 목록에서 **시장조사**
3. **Run workflow** → 실행 방식 **실제** → 초록 **Run workflow**
4. 3~10분 뒤 실행 항목에 ✅가 뜨면 완료
   - 항목을 누르면 **Summary**에 주제 순위와 점수표가 바로 보입니다
   - 파일은 저장소 **reports/LATEST.md**에서 최신 결과로 이동
5. ❌가 뜨면: 항목 → Summary의 **실행 중단** 문구를 그대로 저에게 알려주세요 (키 값은 보내지 마세요)

키 입력 전에 결과 모양만 보고 싶으면 실행 방식 **예시**를 고르세요. 가짜 숫자라 판단에는 쓰지 않습니다.

매주 **월요일 오전 8시 47분**에는 자동으로 실행됩니다.

## 결과가 나온 다음

메모에 "Claude 검토 대기" 칸이 있습니다. Claude에게 **"이번 시장조사 메모 검토해줘"**라고 하면 결론·예상 매출·차별화 칸을 채웁니다. 그 3개를 보고 **파일럿 주제 1개를 골라주세요** (대표님 결정).
