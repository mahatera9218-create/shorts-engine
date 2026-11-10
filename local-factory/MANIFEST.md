# 집 PC 공장 — 설치 장바구니 (MANIFEST)

*집 PC에서 한 번에 깔 것들의 목록. 하나씩 확보해서 여기 체크. 설치 방법은 `README.md`.*
*상세 설계는 `../docs/집PC-공장-로드맵.md`.*

## ✅ 스킬 (repo에 이미 있음 — 저장소 열면 Claude Code가 자동 로드, 설치 불필요)
`.claude/skills/` 안:
- [x] `money-content-writer` — 블로그·사이트 글
- [x] `market-research-memo` — 틈새·투자 메모
- [x] `shorts-script` — 쇼츠 대본·장면
- [x] `blog-voice` — 말투·AI티 검사
- [ ] (추가 예정) 정책 간판 글 전용 스킬? — 지금은 money-content-writer + 프롬프트로 커버, 필요시 신설

## 🔌 MCP (Claude Code에 붙이는 "손")
| MCP | 용도 | 상태 | 비고 |
|---|---|---|---|
| **google-sheets** (`xing5/mcp-google-sheets`) | 틈새표·경제로그·인플로그·테스트지시 읽기/쓰기 | ✅ 확정 | uvx 실행, **서비스 계정** 인증(무인). 설정 `mcp.sample.json` |
| 파일시스템 | reports·원고 읽기/쓰기 | ✅ 불필요 | Claude Code 기본 도구(Read/Write/Edit/Bash)로 충분 — MCP 없음 |
| ComfyUI(이미지) | 썸네일 실사가공·경제 추상 생성 | ⏳ 다음 | MCP 아니고 **로컬 API를 Bash로 호출**하는 게 단순. 별도 세팅 |
| 네이버 임시저장 | 네이버에 글 넣기 | ✅ 어사이드 | MCP 아님, 기존 브라우저 자동화 유지 |

## 🖥️ 런타임
- [ ] **Claude Code** (집 PC 설치) + **Claude 구독(Max) 로그인** ← API 키 없이 정액
- [ ] **uv/uvx** (구글시트 MCP 실행에 필요)
- [ ] (선택) Codex + ChatGPT 구독 — 코드·엔진 보조

## 🎨 로컬 GPU (나중 단계)
- [ ] ComfyUI + 실사 체크포인트(Flux schnell / SDXL) + ControlNet — 3060 Ti 8GB

## 🔑 대표가 준비할 것 (계정·키 — 공장이 못 하는 것)
- [ ] **구글 서비스 계정** 1개 만들고 JSON 키 다운로드 → 집 PC `C:\factory\secrets\gsheets-key.json` 로 저장 (**repo·커밋에 절대 넣지 않음**)
- [ ] 그 서비스 계정 이메일을 **구글시트(쇼츠엔진-경제-로그 등)에 '편집자'로 공유**
- [ ] Claude Max 구독 / (선택) ChatGPT 구독

## 진행 순서
1. [진행중] 패키지 뼈대 + 구글시트 MCP ← **지금 여기**
2. [ ] 집 PC에 Claude Code + uv + 구글시트 MCP 연결 (플러그 도착 후)
3. [ ] 경제 생산 라인 1바퀴 자동 검증
4. [ ] ComfyUI 사진 라인
5. [ ] 라인 복제(패션·연예·쇼츠)
