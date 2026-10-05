# AI 키 이름과 결제 (억선생의 경제판, 2026-10-05)

키는 **GitHub Secrets에만** 넣어요. 대화창·메모·사진에는 절대 쓰지 마세요.
넣는 곳: https://github.com/mahatera9218-create/shorts-engine/settings/secrets/actions → **New repository secret**

| AI | Secret 이름 | 키 만드는 곳 | 결제 | 상태 |
|---|---|---|---|---|
| Claude | `ANTHROPIC_API_KEY` | (이미 있음) | 충전식 | ✅ |
| OpenAI (그림·목소리·사실 대조) | `OPENAI_API_KEY` | platform.openai.com/api-keys | 충전식, 자동충전 끄기 | ✅ |
| Gemini (대기 · 나중에 이미지 가공) | `GEMINI_API_KEY` | aistudio.google.com/apikey | 무료 한도(결제 연결 안 함) | ✅ 넣음 |
| Grok (X 화제) | `XAI_API_KEY` | console.x.ai → API Keys | 카드 등록 + 충전식, 자동 충전 끄기 | ✅ 넣음 |

이름은 **대문자·밑줄까지 그대로** 넣어야 코드가 찾아요.

## 결제할 때 지킬 것
- **자동 충전(Auto recharge)은 모두 끄기.** 다 쓰면 멈추게 두고, Claude가 주간 보고에 남은 금액과 쓴 금액을 적어요.
- 처음 충전은 **$10 이하**로. 1주 실제 사용량을 보고 다시 정해요.
- 월 예상(하루 2편): Grok 월 수천 원, OpenAI 월 1~2만원, Claude(취재 웹 검색 포함) 월 2~3만원.
- Perplexity는 쓰지 않기로 함(2026-10-05). 취재는 Claude 웹 검색이 맡아요.
