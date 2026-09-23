@echo off
rem Encoding: CP949 (ANSI) + CRLF. cmd reads this file in code page 949; do not re-save as UTF-8.
title 손해배상 계산 점검
cd /d "%~dp0"

echo ============================================
echo   손해배상 계산 점검
echo ============================================

python -B scripts\점검.py
echo.
echo --- 계산 엔진 테스트 ---
python -B -m pytest tests -q -p no:cacheprovider
echo.
echo --- 견본 사건 계산 (실제 사건 아님) ---
python -B cli.py cases\sample.yaml -o "%TEMP%\점검_계산표.xlsx"

echo.
echo ============================================
echo   창을 닫으려면 아무 키나 누르십시오.
echo ============================================
pause >nul
