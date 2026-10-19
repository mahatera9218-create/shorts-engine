@echo off
chcp 65001 >nul
echo ============================================
echo  네이버 임시저장 프로그램 - 1회 세팅
echo ============================================
echo.
echo [1/2] Playwright 설치 중... (몇 분 걸려요)
py -m pip install --upgrade pip
py -m pip install playwright
if errorlevel 1 (
  echo.
  echo [!] 실패했어요. Python이 설치돼 있는지 확인하세요.
  echo     https://www.python.org/downloads/  에서 설치할 때
  echo     "Add python.exe to PATH" 체크 꼭 하세요.
  pause
  exit /b 1
)
echo.
echo [2/2] 설치 확인 완료.
echo.
echo 이제 "로그인 저장"을 한 번 하세요:
echo     py login_capture.py
echo.
pause
