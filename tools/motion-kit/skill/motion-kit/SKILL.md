---
name: motion-kit
description: 웹앱에 모션(애니메이션)을 넣거나 고칠 때 사용. 버튼 눌림·나타나기·화면 전환·로딩·스크롤 효과 요청, "더 살아 있게/부드럽게 해줘", Motion Kit 패널에서 복사한 지시문(data-motion 속성 목록)을 붙여넣었을 때. motion-kit.js 연결, data-motion 속성 적용, 효과별 권장 길이·곡선을 다룬다.
---

# Motion Kit

웹앱에 모션을 넣는 규칙과 도구다. 이 폴더의 `motion-kit.js` 하나로 동작하고, 의존성이 없다.

## 1. 연결 (프로젝트에 한 번)

1. 이 스킬 폴더의 `motion-kit.js`를 프로젝트의 정적 파일 폴더에 복사한다.
   - Next.js·Vite·CRA: `public/motion-kit.js`
   - 정적 HTML: HTML 파일 옆
2. 모든 페이지에서 불러온다.
   - Next.js App Router (`app/layout.tsx`):
     ```tsx
     import Script from 'next/script';
     // <body> 안 맨 끝
     <Script src="/motion-kit.js" strategy="afterInteractive" />
     ```
   - Next.js Pages Router: `pages/_app.tsx`에 같은 `<Script>`.
   - Vite·HTML: `</body>` 바로 위에 `<script src="/motion-kit.js"></script>`
3. 배포용으로 조절 패널을 끄려면 `data-panel="off"`를 붙인다. (켜 두면 주소 뒤 `?motion` 또는 Alt+M 으로만 열린다.)

이미 연결돼 있으면 다시 하지 않는다.

## 2. 효과 넣기: data-motion 속성

움직일 요소의 원래 코드(JSX/HTML)에 속성을 추가한다. 스크립트가 알아서 찾아 적용하고, 나중에 렌더링된 요소도 자동으로 잡는다.

```html
<button data-motion="press">결제하기</button>
<h1 data-motion="mask-up">제목</h1>
<p data-motion="fade-up" data-motion-delay="150">부제</p>
<ul data-motion="stagger" data-motion-stagger="50">…</ul>
<strong data-motion="count-up">3,240,000원</strong>
```

| 속성 | 값 | 기본 |
|---|---|---|
| `data-motion` | 아래 효과 이름 | (필수) |
| `data-motion-trigger` | `scroll`(화면에 보일 때) `load`(열릴 때) `press`(누를 때) `hover`(마우스 올릴 때) `loop`(반복) `scroll-link`(스크롤 연동) | 효과마다 다름 |
| `data-motion-duration` | ms | 효과마다 다름 |
| `data-motion-delay` | ms | 0 |
| `data-motion-ease` | `ease-out` `ease-in-out` `ease-in` `overshoot` `anticipation` `snap` `linear` 또는 `cubic-bezier(...)` | 효과마다 다름 |
| `data-motion-stagger` | 자식 사이 간격 ms (`stagger`만) | 60 |
| `data-motion-speed` | 0.05–0.8 (`parallax`만) | 0.3 |
| `data-motion-repeat` | `true` = 다시 보일 때마다 재생 | 한 번만 |

JSX에서도 같은 이름 그대로 쓴다 (`data-motion="press"`). 조건부 렌더링 요소에 붙여도 된다.

## 3. 효과 이름

| 묶음 | 이름 | 기본 언제 | 기본 길이·곡선 | 무엇 |
|---|---|---|---|---|
| 나타나기 | `fade` | scroll | 300 ease-out | 서서히 보임 |
| | `fade-up` | scroll | 400 ease-out | 아래 16px에서 올라옴 (카드·문단 기본값) |
| | `fade-down` | scroll | 400 ease-out | 위에서 내려옴 |
| | `slide-left` / `slide-right` | scroll | 450 ease-out | 오른쪽/왼쪽에서 들어옴 |
| | `scale-in` | scroll | 350 ease-out | 92%에서 커지며 보임 |
| | `pop` | scroll | 450 overshoot | 작게 시작해 살짝 넘었다 복귀 |
| | `blur-in` | scroll | 500 ease-out | 흐림 → 선명 |
| | `mask-up` | scroll | 600 ease-out | 아래부터 드러남 (큰 제목) |
| | `wipe-right` | scroll | 600 ease-in-out | 왼쪽→오른쪽으로 드러남 |
| | `iris` | scroll | 600 ease-in-out | 원형으로 열림 |
| | `stagger` | scroll | 400 ease-out · 간격 60 | 자식 요소가 차례로 올라옴 (목록·카드 묶음) |
| | `type-on` | scroll | 1200 linear | 글자가 한 자씩 (텍스트만 든 요소) |
| | `count-up` | scroll | 1200 ease-out | 숫자가 0부터 올라감 (숫자 든 요소) |
| 누르기 | `press` | press | 180 ease-out | 95%로 눌림 (버튼 기본값) |
| | `squash` | press | 450 ease-out | 말랑하게 눌림 |
| | `like-pop` | press | 450 | 130%로 튀었다 복귀 (좋아요·담기) |
| | `ripple` | press | 550 ease-out | 누른 자리에서 물결 |
| | `shake` | press | 400 linear | 좌우로 흔들림 (오류) |
| 마우스 | `lift` | hover | 200 ease-out | 4px 뜨며 그림자 |
| | `grow` | hover | 200 ease-out | 104%로 커짐 |
| 반복 | `pulse` | loop | 1200 ease-in-out | 두근두근 |
| | `float` | loop | 1800 ease-in-out | 둥둥 |
| | `spin` | loop | 800 linear | 회전 (로딩) |
| | `wiggle` | loop | 1600 | 가끔 흔들림 (알림 종) |
| 스크롤 | `parallax` | scroll-link | 속도 0.3 | 스크롤보다 느리게 움직임 (배경 사진) |

사용자가 한국어 이름으로 말하면 이렇게 고른다: 눌림→`press`, 물결→`ripple`, 좋아요/하트→`like-pop`, 흔들림/오류→`shake`, 나타나기/떠오르기→`fade-up`, 차례로→`stagger`, 숫자 올라가기→`count-up`, 타이핑→`type-on`, 로딩/빙글빙글→`spin`, 알림 흔들기→`wiggle`, 패럴랙스→`parallax`, 마스크 리빌→`mask-up`.

## 4. Motion Kit에 없는 효과

화면 전환(Push·Fade Through·Shared Element), 바텀 시트, 토글 스위치, 탭 밑줄, 스켈레톤, 토스트, 진행 막대, 체크 표시 그리기, 아이콘 모프, 당겨서 새로고침, 캐러셀, 밀어서 삭제는 컴포넌트 동작이라 data-motion으로 하지 않는다. 프로젝트가 이미 쓰는 방식(CSS transition, Framer Motion, View Transitions API 등)으로 직접 만들고, 아래 권장값을 따른다.

| 효과 | 길이 | 곡선 |
|---|---|---|
| Push(새 화면 밀고 들어오기) | 300–400ms | cubic-bezier(.32,.72,0,1) |
| Fade Through(관계없는 화면끼리) | 200–300ms | 투명도 + 크기 97% |
| Shared Element(사진이 커져 상세 화면) | 350–500ms | ease-in-out |
| Bottom Sheet | 열기 300ms / 닫기 200ms | 열기 ease-out, 닫기 ease-in |
| Toggle 스위치 | 200ms | ease-in-out |
| Tab 밑줄 | 250ms | ease-in-out |
| Skeleton 빛 | 1.2–1.6s 반복 | linear |
| Toast | 등장 250ms · 유지 3–4s | ease-out |
| Icon Morph(☰↔✕) | 250ms | ease-in-out |
| Success Check | 원 300ms(overshoot) → 체크 250ms | |
| Carousel 스냅 | 300ms | ease-out |
| Swipe to Delete 접힘 | 200ms | ease-in-out |

## 5. 지킬 것

- **짧게.** 앱 UI는 대부분 150–400ms. 0.5초 넘는 것은 큰 제목·첫 화면·완료 화면 정도만.
- **들어올 때 ease-out, 나갈 때 ease-in, 화면 안 이동은 ease-in-out.** linear는 회전·반복에만.
- **절제.** 한 화면에서 동시에 눈에 띄게 움직이는 것은 1–2개. 하루에 수십 번 누르는 버튼은 `press` 정도만.
- **동작 줄이기 존중.** motion-kit은 `prefers-reduced-motion`이면 효과를 자동으로 끈다. 직접 만든 효과도 같은 조건에서 끈다.
- **레이아웃을 흔들지 않는다.** 직접 만들 때 `transform`·`opacity` 위주로, `width`·`top` 애니메이션은 피한다.
- `type-on`·`count-up`은 요소의 글자를 잠깐 바꾸므로, 글자만 들어 있는 작은 요소(`<strong>`, `<span>`)에 붙인다.
- `parallax`는 요소의 `transform`을 덮어쓰므로 이미 transform을 쓰는 요소에는 감싼 바깥 요소에 붙인다.
- `stagger`는 자식들에 붙는다. 자식에 따로 `lift` 같은 hover 효과를 함께 붙여도 된다.

## 6. 패널에서 복사한 지시문을 받았을 때

사용자가 "Motion Kit 패널" 내보내기 내용을 붙여넣으면:

- **AI에게 부탁** 형식(`찾는 법:` / `추가:` 줄): 각 `찾는 법` 선택자와 설명("버튼 "구독"")으로 소스 코드에서 해당 요소를 찾아, `추가:`의 속성을 그 요소의 JSX/HTML에 그대로 넣는다. 선택자가 소스와 정확히 맞지 않으면 설명·글자로 찾는다. motion-kit.js가 연결 안 돼 있으면 1장대로 먼저 연결한다.
- **라이브러리 없이** 형식: motion-kit 없이 적힌 길이·곡선·동작대로 직접 구현한다.
- **규칙 코드** 형식(`MotionKit.rules([...])`): 가능하면 규칙 대신 각 요소에 data-motion 속성으로 옮겨 넣는다(선택자는 화면 구조가 바뀌면 깨지기 쉽다). 옮기기 어려우면 그 스크립트를 motion-kit.js 바로 다음에 넣는다.

끝나면 사용자에게 `?motion`을 주소 뒤에 붙이면 패널로 다시 조절할 수 있다고 알려 준다.
