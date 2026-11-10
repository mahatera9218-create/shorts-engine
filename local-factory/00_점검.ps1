# 00_점검.ps1 — 집 PC 사양 자동 점검 (설치 전 1단계)
# 더블클릭 말고 설치.bat가 자동 호출. 혼자 돌려도 안전(아무것도 설치/변경 안 함, 읽기만).
# 결과는 화면 + local-factory\점검결과.txt 에 저장.

$ErrorActionPreference = "SilentlyContinue"
$out = @()
function Say($t){ Write-Host $t; $script:out += $t }

Say "================================================="
Say "  집 PC 공장 — 사양 점검 (설치 전 확인)"
Say "  $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Say "================================================="
Say ""

# --- OS ---
$os = Get-CimInstance Win32_OperatingSystem
Say "[OS] $($os.Caption) ($($os.OSArchitecture))"

# --- CPU ---
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Say "[CPU] $($cpu.Name.Trim()) — 코어 $($cpu.NumberOfCores) / 스레드 $($cpu.NumberOfLogicalProcessors)"

# --- RAM ---
$ramGB = [math]::Round($os.TotalVisibleMemorySize/1MB, 0)
Say "[RAM] ${ramGB} GB"
if ($ramGB -lt 16) {
  Say "   ⚠️ 경고: RAM 16GB 미만 — 어사이드 3창 + ComfyUI + Claude 동시 돌리기 빡빡. 병렬 수를 줄여야 함(저장 1~2창, 사진 배치 작게)."
} elseif ($ramGB -lt 32) {
  Say "   ✅ 충분(빠듯하진 않음). 32GB면 더 편함. 병렬 보통으로 시작."
} else {
  Say "   ✅ 넉넉. 병렬 풀로 돌려도 됨."
}

# --- 디스크(C:) ---
$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeGB = [math]::Round($c.FreeSpace/1GB, 0)
$totGB  = [math]::Round($c.Size/1GB, 0)
Say "[디스크 C:] 빈 공간 ${freeGB} GB / 전체 ${totGB} GB"
if ($freeGB -lt 50) {
  Say "   ⚠️ 경고: 빈 공간 50GB 미만 — 사진 모델(7~24GB)+생성물 넣기 빠듯. 50GB 이상 비우길 권장."
} else {
  Say "   ✅ 충분."
}

# --- GPU ---
$gpus = Get-CimInstance Win32_VideoController
foreach ($g in $gpus) {
  $vramGB = [math]::Round($g.AdapterRAM/1GB, 0)
  if ($vramGB -le 0) { $vramGB = "?" }  # 윈도우가 8GB 이상을 0으로 잘못 읽는 버그 있음
  Say "[GPU] $($g.Name) — VRAM 약 ${vramGB} GB (드라이버 $($g.DriverVersion))"
}
Say "   ※ 3060 Ti = VRAM 8GB. 8GB면 사진 모델은 SDXL(안전) 또는 Flux-fp8(더 좋지만 느림) 권장 — 설치 때 자동 선택."

# --- 이미 깔린 도구 (있으면 설치 건너뜀) ---
Say ""
Say "[이미 있는 도구 확인]"
function Has($cmd){ if (Get-Command $cmd -ErrorAction SilentlyContinue) { Say "   ✅ $cmd 있음" } else { Say "   ⬜ $cmd 없음 → 설치 단계에서 깜" } }
Has "winget"; Has "git"; Has "node"; Has "python"; Has "uvx"; Has "claude"

Say ""
Say "================================================="
Say "  점검 끝. 위에 ⚠️ 경고가 없으면 바로 설치 가능."
Say "  경고가 있으면 이 화면을 캡처해서 운영총괄(Claude)에게 주세요."
Say "================================================="

# 파일로 저장
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$out | Out-File -FilePath (Join-Path $dir "점검결과.txt") -Encoding UTF8
Write-Host ""
Write-Host "→ 결과가 점검결과.txt 에도 저장됐어요."
