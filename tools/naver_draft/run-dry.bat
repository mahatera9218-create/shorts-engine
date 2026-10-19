@echo off
chcp 65001 >nul
echo [테스트] 임시저장 직전까지만 (저장은 안 누름). 끝나면 debug 폴더 확인.
py draft_naver.py --dry
pause
