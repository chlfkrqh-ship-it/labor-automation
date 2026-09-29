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
rem The repo is looked up in three places, same order as receive.py.
rem USERPROFILE first: the Claude desktop app is a Store app, so its writes
rem under LOCALAPPDATA land in a private copy (Packages\Claude_*\LocalCache\Local)
rem that programs outside the app do not see. Older PCs have the repo there.
set "GD="
if exist "%USERPROFILE%\labor-automation\repo.git" set "GD=%USERPROFILE%\labor-automation\repo.git"
if not defined GD if exist "%LOCALAPPDATA%\labor-automation\repo.git" set "GD=%LOCALAPPDATA%\labor-automation\repo.git"
if not defined GD for /d %%P in ("%LOCALAPPDATA%\Packages\Claude_*") do if exist "%%~fP\LocalCache\Local\labor-automation\repo.git" set "GD=%%~fP\LocalCache\Local\labor-automation\repo.git"
for %%I in ("%~dp0..\..") do set "WT=%%~fI"

if not defined GD (
    echo Repository not found. Looked in USERPROFILE and LOCALAPPDATA labor-automation folders.
    echo Run setup first: powershell -ExecutionPolicy Bypass -File "%~dp0repo-setup.ps1"
    exit /b 1
)

git --git-dir="%GD%" --work-tree="%WT%" %*
exit /b %ERRORLEVEL%
