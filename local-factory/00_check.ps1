chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# 00_check.ps1 — 집 PC 사양 자동 점검 (설치 전 1단계). 읽기만, 아무것도 안 바꿈.

$ErrorActionPreference = "SilentlyContinue"
function Say($t){ Write-Host $t }

Say "================================================="
Say "  집 PC 공장 — 사양 점검"
Say "  $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Say "================================================="
Say ""

$os = Get-CimInstance Win32_OperatingSystem
Say "[OS] $($os.Caption) ($($os.OSArchitecture))"

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Say "[CPU] $($cpu.Name.Trim()) — 코어 $($cpu.NumberOfCores) / 스레드 $($cpu.NumberOfLogicalProcessors)"

$ramGB = [math]::Round($os.TotalVisibleMemorySize/1MB, 0)
Say "[RAM] ${ramGB} GB"
if ($ramGB -lt 16) {
  Say "   [경고] RAM 16GB 미만 — 어사이드 3창 + ComfyUI + Claude 동시엔 빡빡. 병렬 줄이기."
} elseif ($ramGB -lt 32) {
  Say "   [OK] 충분. 32GB면 더 편함."
} else {
  Say "   [OK] 넉넉. 병렬 풀로 가능."
}

$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeGB = [math]::Round($c.FreeSpace/1GB, 0)
$totGB  = [math]::Round($c.Size/1GB, 0)
Say "[디스크 C:] 빈 공간 ${freeGB} GB / 전체 ${totGB} GB"
if ($freeGB -lt 50) {
  Say "   [경고] 빈 공간 50GB 미만 — 사진 모델(7~24GB)+생성물엔 빠듯. 50GB 이상 권장."
} else {
  Say "   [OK] 충분."
}

$gpus = Get-CimInstance Win32_VideoController
foreach ($g in $gpus) {
  $vramGB = [math]::Round($g.AdapterRAM/1GB, 0)
  if ($vramGB -le 0) { $vramGB = "?" }
  Say "[GPU] $($g.Name) — VRAM 약 ${vramGB} GB"
}
Say "   ※ 3060 Ti = VRAM 8GB. 사진 모델은 SDXL(안전)/Flux-fp8 권장 — 설치 때 자동."

Say ""
Say "[이미 깔린 도구]"
function Has($cmd){ if (Get-Command $cmd -ErrorAction SilentlyContinue) { Say "   [있음] $cmd" } else { Say "   [없음] $cmd → 설치 단계에서 깜" } }
Has "winget"; Has "git"; Has "node"; Has "python"; Has "uvx"; Has "claude"

Say ""
Say "================================================="
Say "  점검 끝. [경고] 없으면 바로 설치 가능."
Say "  [경고] 있으면 이 화면 캡처해서 Claude에게 주세요."
Say "================================================="
