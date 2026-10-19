@echo off
chcp 65001 >nul
echo 오늘 건강 초안을 네이버에 임시저장합니다. (발행은 안 함)
py draft_naver.py
pause
