@echo off
rem Fokus Laufen PC 동기화 — 지금 받고 올리기. 자동 실행(작업 스케줄러)은 "sync_today.bat auto"
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist data mkdir data

if /i "%~1"=="auto" goto auto

title Fokus Laufen - 가민 데이터 동기화
python fokus_sync.py run
echo.
pause
goto end

:auto
rem 작업 스케줄러가 출력을 data\sync.log 로 보내므로, 화면 안내는 con 으로 직접 씁니다
title Fokus Laufen - 가민 데이터 자동 동기화 (작업 스케줄러)
(
  echo.
  echo   ==================================================
  echo     Fokus Laufen  -  가민 데이터 자동 동기화
  echo   ==================================================
  echo.
  echo    가민 커넥트에서 최근 기록을 받아 Fokus Laufen 앱에 올리는 중이에요.
  echo    작업 스케줄러의 "Fokus Laufen 동기화" 작업이 연 창입니다.
  echo    끝나면 저절로 닫혀요. 창을 닫아도 PC에는 문제 없어요.
  echo.
  echo    기록 파일: %~dp0data\sync.log
  echo.
  echo    진행 중...
) > con
python fokus_sync.py run --auto
if errorlevel 1 goto autofail
echo    [완료] 5초 뒤 창이 닫혀요.> con
ping -n 6 127.0.0.1 >nul
goto end

:autofail
echo    [실패] 동기화하지 못했어요. 위 기록 파일을 확인하거나 sync_today.bat 을 직접 실행해 보세요.> con
echo    20초 뒤 창이 닫혀요.> con
ping -n 21 127.0.0.1 >nul

:end
endlocal
