@echo off
rem Encoding: CP949 (ANSI) + CRLF. cmd reads this file in code page 949; do not re-save as UTF-8.
title 노임표·생명표 추출
cd /d "%~dp0"

echo ============================================
echo   노임표·생명표 추출
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다.
  echo        파이썬을 설치하고 "Add python.exe to PATH" 를 체크했는지 확인하십시오.
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0노임표추출.ps1" %*

echo.
echo ============================================
echo   창을 닫으려면 아무 키나 누르십시오.
echo ============================================
pause >nul
