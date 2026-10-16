# web — 사이트 프론트엔드 (Next.js)

**워드프레스를 쓰지 않는다.** 글은 저장소 안의 파일(`web/content/posts/*.md`,
`web/content/pages/*.md` — frontmatter + 변환된 HTML)에서 직접 읽어 정적 생성한다.
발행기(`content/publish_fs.py`)가 대기 초안을 이 파일로 바꿔 커밋하면, Vercel이
자동 배포해 사이트에 반영된다. (가비아 방화벽이 WP 쓰기를 막아 워드프레스를 폐기 — DECISIONS 2026-10-16.)

- 발행: GitHub Actions `구글 글 드립 공개`(자동, 하루 2~3편) 또는 `글 1편 발행`(수동).
- 프레임워크: Next.js 14(App Router) · React 18 · TypeScript. 외부 서버·비밀값 불필요.

## 로컬 실행
```bash
cd web
npm install
npm run dev                          # http://localhost:3000
npm run build && npm start           # 배포와 같은 빌드(content/ 파일을 읽어 정적 생성)
```

## 환경변수 (`.env.example` 참고 — 모두 공개 값, 비밀 아님. 전부 선택)
| 이름 | 값 |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | 최종 사이트 주소 |
| `NEXT_PUBLIC_INTRO_TITLE` | 소개 카드 제목(운영자 수정용, 선택) |
| `NEXT_PUBLIC_INTRO_DESC` | 소개 카드 한 줄 설명(운영자 수정용, 선택) |
| `UNSPLASH_ACCESS_KEY` | 글 대표 실사진용(없으면 사진 생략) |
| `NEXT_PUBLIC_ADSENSE_CLIENT` | `ca-pub-...` (게재 시) |

> 브랜드명(Yield Briefing)과 사이트 설명은 코드(`web/lib/site.ts`)에 고정. 이름 변경은 그 줄을 고친다.

## Vercel 배포 (스테이징 → 나중에 도메인 전환)
1. vercel.com 가입(깃허브로 로그인, 무료 Hobby).
2. **Add New → Project → 이 저장소 import**.
3. **Root Directory = `web`** 로 지정 (중요 — 앱이 web/ 안에 있음).
4. 환경변수에 위 표를 넣고 **Deploy**.
5. `*.vercel.app` 스테이징 주소가 나옴 → PageSpeed Insights로 점수 확인.
6. 만족하면 그때 도메인(astacgroup.com)을 Vercel로 전환(별도 안내).

빌드는 WP가 잠깐 안 떠도 실패하지 않는다(런타임 ISR로 채움).
