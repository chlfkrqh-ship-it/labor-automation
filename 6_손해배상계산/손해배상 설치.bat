@echo off
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
echo 테스트를 실행합니다. 62 passed 가 나와야 정상입니다.
echo.
python -m pytest tests -q

echo.
echo ============================================
echo   창을 닫으려면 아무 키나 누르십시오.
echo ============================================
pause >nul
