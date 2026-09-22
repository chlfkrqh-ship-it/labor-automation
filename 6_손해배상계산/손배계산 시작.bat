@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo 손해배상 계산 - 입력서 감시
echo.
echo   00_양식\입력서.xlsx 를 복사해 노란 칸을 채운 뒤 01_입력\ 에 넣으면
echo   02_결과\ 에 계산표가 나옵니다.
echo.
python watch.py --loop
pause
