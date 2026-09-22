# 저장소 루트에서 .\공통\시스템.ps1 check 처럼 실행한다.
# Codex 번들 Python을 먼저 사용하고, 없으면 PATH의 Python을 사용한다.
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$TaskArguments)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) {
    $taskCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $taskCommand) { throw 'Python 실행 환경이 없습니다. Codex 번들 환경 또는 Python을 설치한 뒤 실행하십시오.' }
    $taskPython = $taskCommand.Source
}
& $taskPython (Join-Path $PSScriptRoot 'scripts\system.py') @TaskArguments
exit $LASTEXITCODE
