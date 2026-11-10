# 집 PC 공장 — 설치 가이드

집 PC(윈도우)에서 **더블클릭 두 번**이면 기본이 깔려요. 막히면 그 화면(빨간 글씨)을 저한테 주세요.
준비물·전체 그림은 `MANIFEST.md`, 설계는 `../docs/집PC-공장-로드맵.md`.

> ⚠️ **키는 절대 repo·커밋·채팅에 넣지 않음.** 서비스계정 JSON 키는 집 PC `C:\factory\secrets\` 안에만.

---

## ⭐ 빠른 길 (더블클릭 — 깨끗한 새 PC 기준)

**준비:** 이 저장소를 집 PC에 받아야 해요. 둘 중 하나 —
- (쉬움) GitHub 저장소 페이지 → `Code ▾` → `Download ZIP` → 풀기 → `local-factory` 폴더로 들어가기.
- (git 있으면) `git clone https://github.com/mahatera9218-create/shorts-engine`

그다음 `local-factory` 폴더에서:
1. **`설치.bat` 더블클릭** → ① 사양 점검(경고 있으면 캡처해서 저에게) → ② 기본 자동 설치(git·Node·Python·uv·Claude Code·저장소).
   - 윈도우가 "이 앱이 변경…허용?" 물으면 **예/허용**.
2. 끝나면 화면이 **"사람만 할 수 있는 3가지"**를 알려줘요 → Claude 로그인 / 구글 JSON 키 / 사진설치.
3. **`사진설치.bat` 더블클릭** → ComfyUI(사진) 설치. (용량 커서 오래 걸림)

> 이 빠른 길은 **새 PC에서 처음 돌리는 게 곧 테스트**예요. 한 줄이라도 빨간 글씨 나오면 그 화면 캡처해서 저에게 주면 바로 고쳐요. (아래 수동 단계는 비상용.)

---

## 0단계 · 저장소 받기 (집 PC)
PowerShell 열고:
```powershell
git clone https://github.com/mahatera9218-create/shorts-engine C:\factory\shorts-engine
```
(`git` 없다고 뜨면 알려주세요.)

## 1단계 · Claude Code + 구독 로그인
- Claude Code 설치(공식 안내대로) → **Claude 계정(Max 구독)으로 로그인.** API 키 X.
- `C:\factory\shorts-engine` 폴더에서 Claude Code를 열면 **우리 스킬 4개가 자동 로드**돼요(설치 불필요).

## 2단계 · uv 설치 (구글시트 MCP 실행용)
PowerShell에 복붙:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
→ 설치 후 PowerShell 새로 열고 `uvx --version` 쳐서 숫자 나오면 OK.

## 3단계 · 구글 서비스 계정 (대표 — 한 번만)
공장이 시트를 혼자 읽고 쓰려면 "로봇 계정"이 필요해요(매일 로그인 안 하게):
1. Google Cloud Console → 프로젝트 만들고 → **서비스 계정** 생성 → **JSON 키 다운로드**
2. 그 JSON 파일을 **`C:\factory\secrets\gsheets-key.json`** 로 저장 (폴더 없으면 만들기)
3. JSON 안에 있는 **서비스계정 이메일**(…@….iam.gserviceaccount.com)을 복사
4. 구글시트 **「쇼츠엔진-경제-로그」(및 공장이 쓸 시트들)** → 공유 → 그 이메일을 **편집자**로 추가
5. 그 시트들이 든 **드라이브 폴더 ID** 확인(폴더 URL 끝 부분) — 4단계에서 씀

※ 이 단계가 어려우면 화면 캡처 주세요. 단계별로 같이 할게요.

## 4단계 · 구글시트 MCP 연결
PowerShell(집 PC), `C:\factory\shorts-engine` 안에서:
```powershell
claude mcp add google-sheets --scope user --env SERVICE_ACCOUNT_PATH=C:\factory\secrets\gsheets-key.json --env DRIVE_FOLDER_ID=여기에_폴더ID -- uvx mcp-google-sheets@latest
```
(`DRIVE_FOLDER_ID=` 뒤를 3단계의 폴더 ID로 교체)
→ 안 되면 `mcp.sample.json` 블록을 집 PC `~/.claude.json`에 직접 넣어도 돼요.

## 5단계 · 연결 확인
Claude Code에서:
```
/mcp
```
→ `google-sheets`가 떠 있고 도구가 보이면 성공. "시트 OO탭 1행 읽어줘" 시켜보면 끝.

---

## 다음 (이 세션에서 이어서)
- ComfyUI(이미지) 세팅 — 로컬 GPU 사진 라인
- 경제 생산 라인 1바퀴 자동 돌려보기
- (유튜브/쇼츠 세션과 공유 인프라 — 자동종료 순서 조정)

## 막히면
빨간 글씨나 안 되는 화면을 캡처해서 주세요. 바로 고쳐드려요.
