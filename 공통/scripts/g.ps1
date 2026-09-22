# git 래퍼. 이 저장소는 .git 을 OneDrive 밖에 두므로 매번 --git-dir 을 줘야 한다.
# 이 스크립트가 그것을 대신한다. git 에 주는 인자를 그대로 넘긴다.
#
#   .\공통\scripts\g.ps1 status
#   .\공통\scripts\g.ps1 add -A
#   .\공통\scripts\g.ps1 commit -m "지침 수정"
#   .\공통\scripts\g.ps1 push
#
# 자주 쓰면 PowerShell 프로필에 등록해 두고 `g status` 로 쓴다. 등록 방법은 시작하기.md.
# 저장소가 없으면 같은 폴더의 repo-setup.ps1 을 먼저 실행한다.

$ErrorActionPreference = "Stop"

$저장소 = Join-Path $env:LOCALAPPDATA "labor-automation\repo.git"
$작업본 = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent   # …\공통\scripts → 저장소 루트

if (-not (Test-Path $저장소)) {
    Write-Host "저장소가 없다: $저장소" -ForegroundColor Yellow
    Write-Host "먼저 실행한다:  .\공통\scripts\repo-setup.ps1" -ForegroundColor Yellow
    exit 1
}

& git --git-dir=$저장소 --work-tree=$작업본 @args
exit $LASTEXITCODE
