# AI 키 이름과 결제 (억선생의 경제판, 2026-10-05)

키는 **GitHub Secrets에만** 넣어요. 대화창·메모·사진에는 절대 쓰지 마세요.
넣는 곳: https://github.com/mahatera9218-create/shorts-engine/settings/secrets/actions → **New repository secret**

| AI | Secret 이름 | 키 만드는 곳 | 결제 | 상태 |
|---|---|---|---|---|
| Claude | `ANTHROPIC_API_KEY` | (이미 있음) | 충전식 | ✅ |
| OpenAI (그림·목소리) | `OPENAI_API_KEY` | platform.openai.com/api-keys | 충전식, 자동충전 끄기 | ✅ |
| Perplexity (취재) | `PERPLEXITY_API_KEY` | perplexity.ai/account/api/keys | 카드 등록 필요. Pro 구독에 매달 1일 API 크레딧 $5 포함 → 우리 사용량이면 거의 추가 결제 없음 | 할 일 |
| Gemini (사실 대조) | `GEMINI_API_KEY` | aistudio.google.com/apikey | 처음엔 무료 한도로 시작(결제 연결 안 해도 됨) | 할 일 |
| Grok (X 화제) | `XAI_API_KEY` | console.x.ai → API Keys | 카드 등록 + 충전식. 가입 때 홍보 크레딧이 붙을 수 있음. 우선 $10 충전 | 할 일 |

이름은 **대문자·밑줄까지 그대로** 넣어야 코드가 찾아요.

## 결제할 때 지킬 것
- **자동 충전(Auto recharge)은 모두 끄기.** 다 쓰면 멈추게 두고, Claude가 주간 보고에 남은 금액과 쓴 금액을 적어요.
- 처음 충전은 **$10 이하**로. 1주 실제 사용량을 보고 다시 정해요.
- 월 예상(하루 2편): Perplexity 거의 0원(Pro 크레딧 안), Gemini 0원(무료 한도), Grok 월 수천 원, OpenAI 월 1~2만원.
