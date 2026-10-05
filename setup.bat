@echo off
rem Fokus Laufen PC 동기화 — 처음 한 번 실행 (패키지 설치 + 동기화 키 + 가민 로그인 + 자동 실행 등록)
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

where python >nul 2>nul
if errorlevel 1 (
  echo [Python 없음] https://www.python.org/downloads/ 에서 설치하세요.
  echo 설치 첫 화면에서 "Add python.exe to PATH" 를 꼭 체크한 뒤, 이 파일을 다시 실행하세요.
  pause
  exit /b 1
)

echo [1/3] 필요한 프로그램 설치 중...
python -m pip install --upgrade --quiet -r requirements.txt
if errorlevel 1 (
  echo [설치 실패] 인터넷 연결을 확인하고 다시 실행하세요.
  pause
  exit /b 1
)

echo.
echo [2/3] 동기화 키 등록 + 가민 로그인
python fokus_sync.py setup
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo [3/3] PC를 켜고 로그인할 때마다 자동으로 받고 올릴까요? (하루 한 번만 실행돼요)
choice /c YN /m "자동 실행 등록"
if errorlevel 2 goto skiptask
if not exist data mkdir data
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1"
if errorlevel 1 echo [등록 실패] 자동 실행 없이도 sync_today.bat 을 더블클릭하면 됩니다.
:skiptask

echo.
echo 이제 첫 동기화를 시작할게요 (처음엔 최근 90일이라 10~20분 걸릴 수 있어요).
if not exist data mkdir data
python fokus_sync.py run
echo.
pause
endlocal
