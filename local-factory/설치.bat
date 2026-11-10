@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo =================================================
echo   Home PC Factory : Check + Install
echo   Keep this window open until it finishes.
echo =================================================
echo.
echo [1/2] Checking PC spec...
powershell -NoProfile -ExecutionPolicy Bypass -File "00_check.ps1"
echo.
echo -------------------------------------------------
echo  If you saw [warning], screenshot and send to Claude.
echo  Otherwise press any key to start install.
echo -------------------------------------------------
pause
echo.
echo [2/2] Installing...
powershell -NoProfile -ExecutionPolicy Bypass -File "01_install.ps1"
echo.
echo =================================================
echo  Finished. Follow the Korean guide shown above.
echo  For the photo line, double-click the photo-install bat.
echo =================================================
pause
