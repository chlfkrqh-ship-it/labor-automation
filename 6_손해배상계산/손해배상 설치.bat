@echo off
rem Encoding: CP949 (ANSI) + CRLF. cmd reads this file in code page 949; do not re-save as UTF-8.
title 손해배상 계산 설치
cd /d "%~dp0"

echo ============================================
echo   손해배상 계산 설치
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다.
  echo.
  pause
  exit /b 1
)

echo 필요한 패키지를 설치합니다.
python -m pip install -r requirements.txt
echo.
echo 테스트를 실행합니다. 실패(failed) 없이 모두 통과(passed)해야 정상입니다.
echo.
python -B -m pytest tests -q -p no:cacheprovider
if errorlevel 1 (
  echo.
  echo [확인 필요] 실패한 테스트가 있습니다. 위 failed 줄을 그대로 붙여 문의하십시오.
)

echo.
echo ============================================
echo   창을 닫으려면 아무 키나 누르십시오.
echo ============================================
pause >nul
