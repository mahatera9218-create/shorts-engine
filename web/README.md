# web — 헤드리스 프론트엔드 (Next.js)

워드프레스(astacgroup.com)는 **글 쓰는 관리실(headless CMS)**, 이 Next.js 앱이
**고객이 보는 빠른 화면**이다. WP REST(`/wp-json/wp/v2`)에서 글·페이지를 읽어
정적 생성(ISR, 10분마다 갱신)으로 렌더한다.

- 운영자는 평소처럼 워드프레스에서 글 발행 → 10분 안에 이 사이트에 자동 반영.
- 프레임워크: Next.js 14(App Router) · React 18 · TypeScript.

## 로컬 실행
```bash
cd web
npm install
WP_API_BASE=https://astacgroup.com/wp-json/wp/v2 npm run dev   # http://localhost:3000
npm run build && npm start                                      # 배포와 같은 빌드
```

## 환경변수 (`.env.example` 참고 — 모두 공개 값, 비밀 아님)
| 이름 | 값 |
|---|---|
| `WP_API_BASE` | `https://astacgroup.com/wp-json/wp/v2` |
| `NEXT_PUBLIC_SITE_NAME` | 억선생의 경제판 |
| `NEXT_PUBLIC_SITE_URL` | 최종 사이트 주소 |
| `NEXT_PUBLIC_SITE_DESC` | 사이트 한 줄 소개 |
| `NEXT_PUBLIC_ADSENSE_CLIENT` | `ca-pub-...` (게재 시) |

## Vercel 배포 (스테이징 → 나중에 도메인 전환)
1. vercel.com 가입(깃허브로 로그인, 무료 Hobby).
2. **Add New → Project → 이 저장소 import**.
3. **Root Directory = `web`** 로 지정 (중요 — 앱이 web/ 안에 있음).
4. 환경변수에 위 표를 넣고 **Deploy**.
5. `*.vercel.app` 스테이징 주소가 나옴 → PageSpeed Insights로 점수 확인.
6. 만족하면 그때 도메인(astacgroup.com)을 Vercel로 전환(별도 안내).

빌드는 WP가 잠깐 안 떠도 실패하지 않는다(런타임 ISR로 채움).
