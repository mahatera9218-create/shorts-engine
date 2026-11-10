chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# 02_photo.ps1 — 로컬 GPU 사진 라인(ComfyUI) 설치 (3060 Ti 8GB). 용량 큼(~8GB).

$ErrorActionPreference = "Stop"
function Step($t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function OK($t){ Write-Host "   [OK] $t" -ForegroundColor Green }

$root = "C:\factory"
$comfy = "$root\ComfyUI_windows_portable"

Write-Host "================================================="
Write-Host "  사진 라인(ComfyUI) 설치 — 3060 Ti 8GB"
Write-Host "  용량 큼. 멈춘 듯 보여도 받는 중이니 기다리기."
Write-Host "================================================="

Step "7-Zip (압축 해제기)"
if (Test-Path "C:\Program Files\7-Zip\7z.exe") { Write-Host "   [건너뜀] 이미 있음" } else {
  winget install --id 7zip.7zip -e --accept-package-agreements --accept-source-agreements
  OK "7-Zip"
}
$7z = "C:\Program Files\7-Zip\7z.exe"

Step "ComfyUI (포터블 NVIDIA)"
if (Test-Path "$comfy\run_nvidia_gpu.bat") {
  Write-Host "   [건너뜀] 이미 설치됨"
} else {
  $url = "https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
  $dl  = "$root\ComfyUI_portable.7z"
  Write-Host "   [내려받기] 1~2GB, 시간 걸림..."
  curl.exe -L $url -o $dl
  Write-Host "   [압축 풀기]..."
  & $7z x $dl -o"$root" -y | Out-Null
  Remove-Item $dl -Force
  OK "ComfyUI 설치"
}

Step "시작용 사진 모델 (SDXL base)"
$ckptDir = "$comfy\ComfyUI\models\checkpoints"
$ckpt = "$ckptDir\sd_xl_base_1.0.safetensors"
if (Test-Path $ckpt) {
  Write-Host "   [건너뜀] 이미 있음"
} elseif (Test-Path $ckptDir) {
  $murl = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
  Write-Host "   [내려받기] SDXL base ~6.9GB, 오래 걸림..."
  curl.exe -L $murl -o $ckpt
  OK "SDXL base (시작용 — 캘리브레이션 때 교체)"
} else {
  Write-Host "   [경고] 체크포인트 폴더 못 찾음. 이 화면 캡처 Claude에게." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  사진 라인 설치 끝!" -ForegroundColor Green
Write-Host "  켜보기: $comfy\run_nvidia_gpu.bat 더블클릭 → 브라우저에 ComfyUI 뜨면 성공"
Write-Host "  다음: Claude와 캘리브레이션(사진 3~4장 뽑아 모델·프롬프트 튜닝)."
