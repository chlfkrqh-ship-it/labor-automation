@echo off
rem Encoding: CP949 (ANSI) + CRLF. cmd reads this file in code page 949; do not re-save as UTF-8.
title 녹취록 환경 설치
cd /d "%~dp0"

echo ============================================
echo   녹취록 환경 설치
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다.
  echo        파이썬 설치 시 "Add python.exe to PATH" 를 체크했는지 확인하십시오.
  echo.
  pause
  exit /b 1
)

echo 전사·화자분리 패키지를 설치합니다. 시간이 걸립니다. GPU 는 필요 없습니다.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

echo.
echo ============================================
echo   창을 닫으려면 아무 키나 누르십시오.
echo ============================================
pause >nul
