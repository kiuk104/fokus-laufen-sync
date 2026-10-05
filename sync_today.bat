@echo off
rem Fokus Laufen PC 동기화 — 지금 받고 올리기. 자동 실행(작업 스케줄러)은 "sync_today.bat auto"
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist data mkdir data

if /i "%~1"=="auto" (
  python fokus_sync.py run --auto
) else (
  python fokus_sync.py run
  echo.
  pause
)
endlocal
