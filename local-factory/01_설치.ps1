# 01_설치.ps1 — 집 PC 공장 기본 런타임 자동 설치 (2단계)
# 설치.bat가 점검 다음에 자동 호출. 깨끗한 윈도우 새 PC 기준.
# 이미 깔린 건 건너뜀(여러 번 돌려도 안전). 키·비번은 안 건드림(대표 몫).

$ErrorActionPreference = "Stop"
function Step($t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function OK($t){ Write-Host "   ✅ $t" -ForegroundColor Green }
function Skip($t){ Write-Host "   ⏭️  $t (이미 있음)" -ForegroundColor DarkGray }
function Need($cmd){ return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Host "================================================="
Write-Host "  집 PC 공장 — 기본 설치 시작"
Write-Host "  (중간에 윈도우가 '허용?' 물으면 예/허용)"
Write-Host "================================================="

# 0) winget 확인 (윈도우 10/11 기본 탑재)
if (-not (Need "winget")) {
  Write-Host "   ⚠️ winget(앱 설치기)이 없어요. Microsoft Store에서 '앱 설치 관리자' 업데이트 후 다시 실행하거나, 이 화면을 Claude에게 주세요." -ForegroundColor Yellow
  exit 1
}

# 1) Git
Step "Git (저장소 받기용)"
if (Need "git") { Skip "git" } else {
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  OK "git 설치"
}

# 2) Node.js (Claude Code 실행용)
Step "Node.js (Claude Code 구동)"
if (Need "node") { Skip "node" } else {
  winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
  OK "node 설치"
}

# 3) Python (스크립트·ComfyUI용)
Step "Python"
if (Need "python") { Skip "python" } else {
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  OK "python 설치"
}

# 4) uv/uvx (구글시트 MCP 실행용)
Step "uv (구글시트 MCP 실행기)"
if (Need "uvx") { Skip "uv" } else {
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  OK "uv 설치"
}

# PATH 새로고침(방금 깐 것들 이 창에서 바로 쓰게)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# 5) Claude Code
Step "Claude Code"
if (Need "claude") { Skip "claude" } else {
  npm install -g @anthropic-ai/claude-code
  OK "Claude Code 설치 (※ 실행 명령이 바뀌었으면 공식 안내 확인 — 안 되면 Claude에게 화면 주기)"
}

# 6) 폴더 + 저장소
Step "공장 폴더 · 저장소"
if (-not (Test-Path "C:\factory")) { New-Item -ItemType Directory -Path "C:\factory" | Out-Null; OK "C:\factory 생성" }
if (-not (Test-Path "C:\factory\secrets")) { New-Item -ItemType Directory -Path "C:\factory\secrets" | Out-Null; OK "C:\factory\secrets 생성 (서비스계정 JSON 넣을 곳)" }
if (Test-Path "C:\factory\shorts-engine\.git") {
  Skip "저장소 (C:\factory\shorts-engine)"
} else {
  git clone https://github.com/mahatera9218-create/shorts-engine C:\factory\shorts-engine
  OK "저장소 받음"
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  기본 설치 끝! 다음은 '사람만 할 수 있는' 3가지:" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  1) Claude 로그인:  새 PowerShell 창 → 'cd C:\factory\shorts-engine' → 'claude' → Max 계정 로그인"
Write-Host "  2) 구글 서비스계정 JSON → C:\factory\secrets\gsheets-key.json  (README 3단계)"
Write-Host "  3) 사진 라인(ComfyUI)은 → 02_사진.ps1 실행"
Write-Host ""
Write-Host "  막히면 빨간 글씨 캡처해서 운영총괄(Claude)에게 주세요."
