@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo =================================================
echo   Home PC Factory : Photo line (ComfyUI)
echo   Large download (~8GB). Wired internet recommended.
echo   Run the main install first.
echo =================================================
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "02_photo.ps1"
echo.
pause
