@echo off
chcp 65001 > nul
title Factory - Claude (keep open)
cd /d C:\factory\shorts-engine

echo ============================================
echo   Factory ON - do NOT close this window
echo   (phone: open claude.ai/code to control)
echo ============================================
echo.

echo [1/2] getting latest...
git pull
echo.

echo [2/2] starting Claude remote-control...
echo   Keep this window open. Control from your phone.
echo.
claude remote-control

echo.
echo (remote-control stopped. press a key to close)
pause > nul
