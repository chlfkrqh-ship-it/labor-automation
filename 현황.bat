@echo off
chcp 65001 >nul
title 사건 현황
cd /d "%~dp0"
python -B "공통\scripts\dashboard.py" --open
if errorlevel 1 (
    echo.
    echo 현황판을 만들지 못했습니다. 위 메시지를 확인하십시오.
    pause
)
