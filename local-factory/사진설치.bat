@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo =================================================
echo   집 PC 공장 - 사진 라인(ComfyUI) 설치
echo   용량 큼(~8GB). 유선 인터넷 권장. 오래 걸립니다.
echo   먼저 '설치.bat'을 끝냈어야 합니다.
echo =================================================
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "02_사진.ps1"
echo.
pause
