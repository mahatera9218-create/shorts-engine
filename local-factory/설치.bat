@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo =================================================
echo   집 PC 공장 - 점검 + 기본 설치 (한 방)
echo   창을 닫지 말고 끝까지 두세요.
echo =================================================
echo.
echo [1/2] 사양 점검...
powershell -NoProfile -ExecutionPolicy Bypass -File "00_점검.ps1"
echo.
echo -------------------------------------------------
echo  위에 빨간/노란 경고가 있으면 캡처해서 Claude에게 주고,
echo  없으면 아무 키나 눌러 설치를 계속하세요.
echo -------------------------------------------------
pause
echo.
echo [2/2] 기본 설치...
powershell -NoProfile -ExecutionPolicy Bypass -File "01_설치.ps1"
echo.
echo =================================================
echo  끝났습니다. 위 안내의 '사람만 할 수 있는 3가지'를 하세요.
echo  사진 라인은 '사진설치.bat'을 더블클릭.
echo =================================================
pause
