# 가상환경을 활성화하지 않고 transcribe.py 를 부른다.
#
#   .\녹취.ps1 김OO-면담                  ← 사건 폴더 (5_녹취록/사건/ 아래)
#   .\녹취.ps1 김OO-면담 -Speakers 2       ← 화자 수를 알면 지정 (권장)
#   .\녹취.ps1 "C:\경로\녹음.m4a"          ← 사건과 무관한 파일 하나 (간이)
#
# 화자 수를 지정하면 정확도가 크게 오른다. 통화는 2, 3자 면담은 3.
# 지정하지 않으면 자동 판단하는데 과분할하는 경향이 있다.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Target,

    [int]$Speakers = 0,
    [string]$Model = "large-v3-turbo",
    [switch]$NoDiarize,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $env:LOCALAPPDATA "노동사건자동화\venv-녹취\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "가상환경이 없습니다. 먼저 .\setup.ps1 을 실행하십시오." -ForegroundColor Red
    exit 1
}

# 대상 판별
#   경로 구분자나 드라이브 문자가 있으면 경로로 본다   → 간이 모드
#   그렇지 않으면 사건 폴더명으로 본다                → 사건/{이름}/원본/
$looksLikePath = [System.IO.Path]::IsPathRooted($Target) -or ($Target -match '[\\/]')

if ($looksLikePath) {
    if (-not (Test-Path -LiteralPath $Target)) {
        Write-Host "대상을 찾지 못했습니다: $Target" -ForegroundColor Red
        exit 1
    }
    $inputPath = $Target
    $outDir = $null
    Write-Host "[간이 모드] $Target" -ForegroundColor Cyan
}
else {
    $caseDir = Join-Path "사건" $Target
    $srcDir = Join-Path $caseDir "원본"

    if (Test-Path -LiteralPath $srcDir) {
        $inputPath = $srcDir
        $outDir = Join-Path $caseDir "전사"
        Write-Host "[사건 모드] $Target" -ForegroundColor Cyan
    }
    elseif (Test-Path -LiteralPath $caseDir) {
        Write-Host "사건 폴더는 있으나 원본/ 이 없습니다: $srcDir" -ForegroundColor Red
        Write-Host "음성파일을 $srcDir 에 넣으십시오." -ForegroundColor Yellow
        exit 1
    }
    else {
        Write-Host "사건 폴더를 찾지 못했습니다: $caseDir" -ForegroundColor Red
        Write-Host "5_녹취록\사건\$Target\원본\ 에 음성파일을 넣으십시오." -ForegroundColor Yellow
        exit 1
    }
}

# 파이썬이 한글 경로·출력을 UTF-8 로 다루도록 맞춘다.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$argv = @("transcribe.py", $inputPath, "--model", $Model)
if ($outDir) { $argv += @("--output-dir", $outDir) }
if (-not $NoDiarize) { $argv += "--diarize" }
if ($Speakers -gt 0) { $argv += @("--num-speakers", "$Speakers") }
if ($Rest) { $argv += $Rest }

if ($Speakers -le 0 -and -not $NoDiarize) {
    Write-Host "화자 수를 지정하지 않았습니다. 아는 경우 -Speakers 2 처럼 주면 정확해집니다." -ForegroundColor Yellow
}

& $py @argv
exit $LASTEXITCODE
