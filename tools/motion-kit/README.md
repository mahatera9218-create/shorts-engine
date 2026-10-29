# Motion Kit

바이브코딩으로 웹앱을 만들 때 버튼·카드·제목에 모션을 넣는 도구입니다. 설치할 프로그램도, 가입도 필요 없습니다.

## 제일 쉬운 방법 두 가지

### ① 도구 없이: 프롬프트만 복사
`motion-graphics-pack.html`을 열고, 원하는 효과 액자를 누르세요. 나온 프롬프트의 `[ ]` 부분만 바꿔서 AI 코딩 도구에 붙여넣으면 끝입니다. 설치도, 연결도 없습니다.

### ② 눈으로 보면서 조절: 북마크 하나
1. `bookmarklet.html`을 PC의 Chrome(또는 Edge)으로 엽니다.
2. 파란 **모션 패널** 버튼을 북마크바로 끌어다 놓습니다. (처음 한 번만)
3. 개발 중인 내 웹앱을 브라우저로 열고, 북마크 **모션 패널**을 누릅니다. → 화면 옆에 패널이 뜹니다.
4. **요소 선택** → 화면에서 버튼·카드를 누르고 → 효과·길이·곡선을 고릅니다.
5. **복사** → VS Code의 AI 채팅창에 붙여넣기. AI가 코드로 만들어 줍니다.

프로젝트에 파일을 넣거나 연결할 필요가 없습니다. 복사되는 내용은 "라이브러리 없이 이렇게 만들어줘"라는 지시문이라, 어떤 프로젝트·어떤 AI 도구에서도 통합니다.

## 들어 있는 파일

| 파일 | 무엇 |
|---|---|
| `bookmarklet.html` | 북마크 만들기 안내(②번 방법) |
| `motion-graphics-pack.html` | 모션 50가지 견본집(영상용·웹앱용 탭). 액자를 누르면 프롬프트가 나옵니다(①번 방법). |
| `demo.html` | 체험용 가짜 앱 화면. 열면 패널이 바로 뜹니다. |
| `motion-kit.js` | 본체. 아래 ③번 방법에서 씁니다. |
| `skill/motion-kit/` | Claude Code 스킬. AI가 이 도구를 정확히 쓰게 해 줍니다. |

## ③ 프로젝트에 넣어서 쓰기 (효과 이름으로 관리하고 싶을 때)

1. `motion-kit.js`를 내 프로젝트에 넣습니다. 위치는 `public` 폴더가 있으면 그 안이고, 없으면 HTML 파일 옆입니다.
2. AI 코딩 도구에 이렇게 말합니다.

   > motion-kit.js를 모든 페이지에 불러오게 연결해줘. 그다음 메인 버튼에 `data-motion="press"`, 카드 목록에 `data-motion="stagger"`, 큰 제목에 `data-motion="mask-up"`을 붙여줘.

3. 내 웹앱 주소 뒤에 `?motion`을 붙여서 엽니다. 예: `http://localhost:3000/?motion`
4. 패널에서 **요소 선택** → 화면에서 요소를 누르고 → 효과를 고릅니다.
5. 다 고쳤으면 패널 아래 **코드로 남기기 → AI에게 부탁 → 복사**를 누릅니다. 복사한 글을 AI 코딩 도구에 그대로 붙여넣으면 코드에 반영됩니다.

> 패널에서 바꾼 내용은 그 브라우저에만 임시로 남습니다. 5번을 해야 다른 사람 화면에도 적용됩니다.

## Claude Code를 쓴다면: 스킬로 설치

`skill/motion-kit` 폴더를 통째로 복사해 넣으면 됩니다.

- 이 프로젝트에서만 쓸 때: `내프로젝트/.claude/skills/motion-kit/`
- 모든 프로젝트에서 쓸 때: `~/.claude/skills/motion-kit/`

그다음부터는 "버튼에 눌림 효과 넣어줘"나 "목록이 차례로 나오게 해줘"라고만 말해도 됩니다. Claude가 motion-kit을 연결하고 맞는 효과 이름과 권장 속도를 골라 줍니다. 패널에서 복사한 글을 붙여넣어도 알아서 적용합니다.

다른 AI 도구(Cursor 등)를 쓴다면 `SKILL.md` 내용을 그 도구의 규칙(rules) 파일에 붙여넣어도 같은 효과가 납니다.

## 직접 쓰기 (코드를 아는 경우)

```html
<script src="/motion-kit.js"></script>

<button data-motion="press">결제하기</button>
<h1 data-motion="mask-up">제목</h1>
<p data-motion="fade-up" data-motion-delay="150">부제</p>
<ul data-motion="stagger" data-motion-stagger="50"><li>…</li></ul>
<strong data-motion="count-up">3,240,000원</strong>
<div data-motion="lift">카드</div>
```

Next.js(App Router)에서는 `app/layout.tsx`의 `<body>` 안 맨 끝에 다음을 넣습니다.

```tsx
import Script from 'next/script';
<Script src="/motion-kit.js" strategy="afterInteractive" />
```

### 효과 이름 (26가지)

- **나타나기:** `fade` `fade-up` `fade-down` `slide-left` `slide-right` `scale-in` `pop` `blur-in` `mask-up` `wipe-right` `iris` `stagger` `type-on` `count-up`
- **누르기:** `press` `squash` `like-pop` `ripple` `shake`
- **마우스 올리기:** `lift` `grow`
- **반복:** `pulse` `float` `spin` `wiggle`
- **스크롤:** `parallax`

### 조절 속성

| 속성 | 값 |
|---|---|
| `data-motion-trigger` | `scroll` 화면에 보일 때 · `load` 열릴 때 · `press` 누를 때 · `hover` 마우스 올릴 때 · `loop` 반복 · `scroll-link` 스크롤 연동 |
| `data-motion-duration` | 길이(ms) |
| `data-motion-delay` | 시작 지연(ms) |
| `data-motion-ease` | `ease-out` `ease-in-out` `ease-in` `overshoot` `anticipation` `snap` `linear` 또는 `cubic-bezier(...)` |
| `data-motion-stagger` | `stagger`의 항목 간격(ms) |
| `data-motion-speed` | `parallax` 속도(0.05–0.8) |
| `data-motion-repeat` | `true`면 다시 보일 때마다 재생 |

### 자바스크립트로

```js
MotionKit.rules([{ selector: '.hero h1', motion: 'mask-up' }]); // 선택자로 한꺼번에
MotionKit.play('.hero h1');   // 다시 재생
MotionKit.open();             // 패널 열기 (Alt+M 도 됨)
```

## 배포할 때

패널을 아예 끄려면 `<script src="/motion-kit.js" data-panel="off"></script>`로 바꿉니다. 끄지 않아도 패널은 주소에 `?motion`을 붙이거나 Alt+M을 눌렀을 때만 열립니다.

## 알아 두면 좋은 점

- 휴대폰이나 PC에서 '동작 줄이기' 설정을 켠 사람에게는 효과가 자동으로 꺼집니다(패널을 연 상태는 예외).
- 화면 전환, 바텀 시트, 토스트처럼 부품 단위의 동작은 data-motion으로 하지 않습니다. 견본집 웹앱 탭의 프롬프트로 AI에게 만들어 달라고 하면 됩니다.
- `type-on`·`count-up`은 글자를 잠깐 바꾸므로, 글자만 든 작은 요소에 붙이세요.
- `parallax`는 요소의 transform을 덮어씁니다.
- 최신 Chrome·Safari·Edge·Firefox에서 동작합니다(Web Animations API).

라이선스: MIT (자유롭게 쓰고 고쳐서 나눠도 됩니다).
