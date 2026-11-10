# 02_사진.ps1 — 로컬 GPU 사진 라인(ComfyUI) 설치 (3060 Ti 8GB)
# 01_설치.ps1 끝나고 실행. 용량 큼(합쳐 ~8GB 내려받음) — 집 PC·유선 권장.
# 이미 받은 건 건너뜀. 설치만 함(실행·캘리브레이션은 뒤 단계).

$ErrorActionPreference = "Stop"
function Step($t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function OK($t){ Write-Host "   ✅ $t" -ForegroundColor Green }

$root = "C:\factory"
$comfy = "$root\ComfyUI_windows_portable"

Write-Host "================================================="
Write-Host "  사진 라인(ComfyUI) 설치 — 3060 Ti 8GB"
Write-Host "  용량 큼. 중간에 멈춘 듯 보여도 받는 중이니 기다리기."
Write-Host "================================================="

# 1) 7-Zip (ComfyUI 압축 풀기용)
Step "7-Zip (압축 해제기)"
if (Test-Path "C:\Program Files\7-Zip\7z.exe") { Write-Host "   ⏭️  이미 있음" } else {
  winget install --id 7zip.7zip -e --accept-package-agreements --accept-source-agreements
  OK "7-Zip"
}
$7z = "C:\Program Files\7-Zip\7z.exe"

# 2) ComfyUI 포터블 내려받기 + 풀기
Step "ComfyUI (포터블 — NVIDIA)"
if (Test-Path "$comfy\run_nvidia_gpu.bat") {
  Write-Host "   ⏭️  이미 설치됨 ($comfy)"
} else {
  $url = "https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
  $dl  = "$root\ComfyUI_portable.7z"
  Write-Host "   ⬇️  내려받는 중... (1~2GB, 시간 걸림)"
  curl.exe -L $url -o $dl
  Write-Host "   📦 압축 푸는 중..."
  & $7z x $dl -o"$root" -y | Out-Null
  Remove-Item $dl -Force
  OK "ComfyUI 설치 ($comfy)"
}

# 3) 시작용 체크포인트 (SDXL base — 캘리브레이션 출발점)
Step "시작용 사진 모델 (SDXL base)"
$ckptDir = "$comfy\ComfyUI\models\checkpoints"
$ckpt = "$ckptDir\sd_xl_base_1.0.safetensors"
if (Test-Path $ckpt) {
  Write-Host "   ⏭️  이미 있음"
} elseif (Test-Path $ckptDir) {
  $murl = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
  Write-Host "   ⬇️  SDXL base 내려받는 중... (~6.9GB, 오래 걸림)"
  curl.exe -L $murl -o $ckpt
  OK "SDXL base (시작용 — 캘리브레이션 때 더 실사다운 모델로 교체 예정)"
} else {
  Write-Host "   ⚠️ 체크포인트 폴더를 못 찾음($ckptDir). ComfyUI 설치가 덜 된 듯 — 이 화면 Claude에게 주기." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  사진 라인 설치 끝!" -ForegroundColor Green
Write-Host "  ▶ 켜보기: $comfy\run_nvidia_gpu.bat 더블클릭 → 브라우저에 ComfyUI 뜨면 성공"
Write-Host "  다음: 운영총괄(Claude)과 '캘리브레이션' — 실제 경제 사진 3~4장 뽑아보고"
Write-Host "        8GB에 맞는 모델(SDXL 실사체크포인트 / Flux-fp8)·프롬프트 스타일·ControlNet 튜닝."
Write-Host "        (썸네일 원본 가공 = img2img+ControlNet / 본문 = text2img)"
