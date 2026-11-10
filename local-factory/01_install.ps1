chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# 01_install.ps1 — 집 PC 공장 기본 런타임 자동 설치. 이미 있으면 건너뜀.

$ErrorActionPreference = "Stop"
function Step($t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function OK($t){ Write-Host "   [OK] $t" -ForegroundColor Green }
function Skip($t){ Write-Host "   [건너뜀] $t (이미 있음)" -ForegroundColor DarkGray }
function Need($cmd){ return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

$BRANCH = "claude/week-1-kickoff-3dzyb3"

Write-Host "================================================="
Write-Host "  집 PC 공장 — 기본 설치 시작"
Write-Host "  (윈도우가 '허용?' 물으면 예/허용)"
Write-Host "================================================="

if (-not (Need "winget")) {
  Write-Host "   [경고] winget(앱 설치기)이 없어요. Microsoft Store에서 '앱 설치 관리자' 업데이트 후 다시 실행하거나, 이 화면 캡처를 Claude에게." -ForegroundColor Yellow
  exit 1
}

Step "Git"
if (Need "git") { Skip "git" } else {
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  OK "git"
}

Step "Node.js (Claude Code 구동)"
if (Need "node") { Skip "node" } else {
  winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
  OK "node"
}

Step "Python"
if (Need "python") { Skip "python" } else {
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  OK "python"
}

Step "uv (구글시트 MCP 실행기)"
if (Need "uvx") { Skip "uv" } else {
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  OK "uv"
}

# 방금 깐 것들 이 창에서 바로 쓰게 PATH 새로고침
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Step "Claude Code"
if (Need "claude") { Skip "claude" } else {
  npm install -g @anthropic-ai/claude-code
  OK "Claude Code (안 되면 화면 캡처 Claude에게)"
}

Step "공장 폴더 · 저장소"
if (-not (Test-Path "C:\factory")) { New-Item -ItemType Directory -Path "C:\factory" | Out-Null; OK "C:\factory" }
if (-not (Test-Path "C:\factory\secrets")) { New-Item -ItemType Directory -Path "C:\factory\secrets" | Out-Null; OK "C:\factory\secrets (서비스계정 JSON 넣을 곳)" }
if (Test-Path "C:\factory\shorts-engine\.git") {
  Skip "저장소 (C:\factory\shorts-engine)"
} else {
  git clone --branch $BRANCH --single-branch https://github.com/mahatera9218-create/shorts-engine C:\factory\shorts-engine
  OK "저장소 받음 (가지: $BRANCH)"
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  기본 설치 끝! 다음은 '사람만 할 수 있는' 3가지:" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  1) Claude 로그인: 새 PowerShell 창 → cd C:\factory\shorts-engine → claude → Max 로그인"
Write-Host "  2) 구글 서비스계정 JSON → C:\factory\secrets\gsheets-key.json  (README 3단계)"
Write-Host "  3) 사진 라인은 사진설치.bat 더블클릭"
Write-Host ""
Write-Host "  막히면 빨간 글씨 캡처해서 Claude에게 주세요."
