# 이 PC에 git 저장소를 붙인다. PC마다 한 번만 실행한다.
#
#   .\공통\scripts\repo-setup.ps1                     # 원격 없이 (이력만)
#   .\공통\scripts\repo-setup.ps1 -원격 https://github.com/{계정}/{저장소}.git
#
# .git 은 %USERPROFILE%\labor-automation\repo.git 에 둔다. OneDrive 안에 두면 두 PC의
# index·lock 파일이 충돌해 저장소가 깨진다. 작업본은 이 폴더 그대로이고 아무것도 옮기지 않는다.
# %LOCALAPPDATA% 에 두지 않는 까닭: Claude 데스크톱 앱(스토어 앱) 안에서 돌리면 그 아래 만든 파일이 앱 전용
# 가상 폴더(Packages\Claude_*\LocalCache\Local)로 가서 앱 밖 프로그램에는 보이지 않는다.
# 예전에 %LOCALAPPDATA% 나 그 가상 폴더에 만든 저장소가 있으면 그것을 그대로 쓴다(g.bat·receive.py 와 같은 순서).

param(
    [string]$원격 = "",
    [string]$이름 = "",
    [string]$메일 = ""
)

$ErrorActionPreference = "Stop"

$후보 = @((Join-Path $env:USERPROFILE "labor-automation\repo.git"), (Join-Path $env:LOCALAPPDATA "labor-automation\repo.git"))
$후보 += @(Get-ChildItem (Join-Path $env:LOCALAPPDATA "Packages") -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "LocalCache\Local\labor-automation\repo.git" })
$저장소 = $후보 | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $저장소) { $저장소 = $후보[0] }
$작업본 = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git 이 없다. winget install Git.Git 로 설치한다." -ForegroundColor Red; exit 1
}

$새로만듦 = $false
if (-not (Test-Path $저장소)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $저장소 -Parent) | Out-Null
    git init --bare $저장소 --initial-branch=main | Out-Null
    $새로만듦 = $true
    Write-Host "저장소 생성: $저장소" -ForegroundColor Green
} else {
    Write-Host "저장소가 이미 있다: $저장소" -ForegroundColor Yellow
}

git --git-dir=$저장소 config core.bare false
git --git-dir=$저장소 config core.worktree $작업본
git --git-dir=$저장소 config core.autocrlf false     # 한글 문서가 섞여 있어 줄끝을 건드리지 않는다
git --git-dir=$저장소 config core.quotepath false    # 한글 경로를 이스케이프하지 않고 그대로 보여 준다
if ($이름) { git --git-dir=$저장소 config user.name  $이름 }
if ($메일) { git --git-dir=$저장소 config user.email $메일 }

if ($원격) {
    $있음 = git --git-dir=$저장소 remote 2>$null
    if ($있음 -contains "origin") { git --git-dir=$저장소 remote set-url origin $원격 }
    else { git --git-dir=$저장소 remote add origin $원격 }
    Write-Host "원격 연결: $원격" -ForegroundColor Green

    if ($새로만듦) {
        Write-Host "원격에서 받아 온다..." -ForegroundColor Cyan
        git --git-dir=$저장소 fetch origin
        git --git-dir=$저장소 --work-tree=$작업본 reset --mixed origin/main   # 파일은 건드리지 않고 이력만 맞춘다
        git --git-dir=$저장소 branch --set-upstream-to=origin/main main 2>$null
        Write-Host "받았다. 작업본의 파일은 그대로 두었다(reset --mixed)." -ForegroundColor Green
        Write-Host "차이를 보려면:  공통\scripts\g.bat status" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "이제 git 은 사람이 치지 않는다. 시스템 파일을 고치면 작업을 맡은 AI 가 올린다." -ForegroundColor Cyan
Write-Host "받는 것도 AI 가 새 작업을 열 때 한다: 공통\scripts\receive.py . 절차: 공통\운영.md '시스템 파일 올리기'"
Write-Host "이력을 직접 볼 때만:  공통\scripts\g.bat log --oneline -10"
