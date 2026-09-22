@echo off
rem git wrapper for this repo. The .git lives outside OneDrive, so every
rem git call needs --git-dir/--work-tree. This batch supplies both.
rem
rem   g.bat status   g.bat add -A   g.bat commit -m "..."   g.bat push
rem
rem ASCII only, CRLF line endings. Korean text here breaks cmd parsing
rem because the file encoding and the console code page must match.
rem Why .git sits outside OneDrive: see ??/git-??-??.md

setlocal
set "GD=%LOCALAPPDATA%\labor-automation\repo.git"
for %%I in ("%~dp0..\..") do set "WT=%%~fI"

if not exist "%GD%" (
    echo Repository not found: %GD%
    echo Run setup first: powershell -ExecutionPolicy Bypass -File "%~dp0repo-setup.ps1"
    exit /b 1
)

git --git-dir="%GD%" --work-tree="%WT%" %*
exit /b %ERRORLEVEL%
