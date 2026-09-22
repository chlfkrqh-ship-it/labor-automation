# 5_녹취록 환경 설치 (PC마다 한 번씩 실행)
#
# 가상환경은 OneDrive 밖(%LOCALAPPDATA%)에 만든다.
# 용량이 수 GB이고 PC마다 따로 받아야 하므로 동기화 대상이 아니다.
#
# 전사와 화자 분리 모두 CPU 로 한다. GPU 도 HuggingFace 토큰도 필요 없다.
#   전사      faster-whisper (CTranslate2)
#   화자 분리 sherpa-onnx (ONNX Runtime)
# 화자 분리 모델 35MB 는 이 폴더의 models\ 에 들어 있어 따로 받지 않아도 된다.
# 없으면 download_diarization_models.py 가 GitHub 릴리스에서 받아 온다.
#
# 사용법:  cd "$env:OneDrive\노동사건자동화\5_녹취록" ;  .\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$envRoot = Join-Path $env:LOCALAPPDATA "노동사건자동화"
$venv    = Join-Path $envRoot "venv-녹취"
$models  = Join-Path $envRoot "models"
New-Item -ItemType Directory -Force -Path $envRoot, $models | Out-Null

function Invoke-Pip {
    # pip 은 실패해도 예외를 던지지 않으므로 종료코드를 직접 본다.
    param([string[]]$PipArgs, [string]$What)
    Write-Host "  pip $($PipArgs -join ' ')" -ForegroundColor DarkGray
    & $py -m pip @PipArgs
    if ($LASTEXITCODE -ne 0) { throw "$What 실패 (pip 종료코드 $LASTEXITCODE)" }
}

function YesNo($value) { if ($value) { return "예" } else { return "아니오" } }

Write-Host "== Python 확인 ==" -ForegroundColor Cyan
python --version

Write-Host "`n== 가상환경 ($venv) ==" -ForegroundColor Cyan
if (-not (Test-Path $venv)) { python -m venv $venv }
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet

Write-Host "`n== 패키지 설치 ==" -ForegroundColor Cyan
Invoke-Pip @("install", "-r", "requirements-cpu.txt") "requirements-cpu.txt 설치"

Write-Host "`n== 모델 캐시 위치 고정 ==" -ForegroundColor Cyan
[Environment]::SetEnvironmentVariable("HF_HOME", $models, "User")
$env:HF_HOME = $models
Write-Host "HF_HOME = $models  (사용자 환경변수로 등록. 새 셸에서 적용됩니다)"
Write-Host "전사 모델(large-v3-turbo)은 처음 실행할 때 여기에 자동으로 받아집니다."

Write-Host "`n== 화자 분리 모델 확인 ==" -ForegroundColor Cyan
$segModel = Join-Path $PSScriptRoot "models\sherpa-onnx-pyannote-segmentation-3-0\model.onnx"
$embModel = Join-Path $PSScriptRoot "models\3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx"
$diarModelsOk = (Test-Path $segModel) -and (Test-Path $embModel)
if ($diarModelsOk) {
    Write-Host "화자 분리 모델이 이미 있습니다 (models\)." -ForegroundColor Green
} else {
    Write-Host "화자 분리 모델이 없어 내려받습니다 (약 35MB)..." -ForegroundColor Yellow
    & $py download_diarization_models.py
    if ($LASTEXITCODE -eq 0) {
        $diarModelsOk = (Test-Path $segModel) -and (Test-Path $embModel)
    }
    if (-not $diarModelsOk) {
        Write-Host "모델 내려받기에 실패했습니다. 화자 분리 없이 전사만 됩니다." -ForegroundColor Yellow
        Write-Host "나중에 python download_diarization_models.py 를 다시 실행하면 됩니다." -ForegroundColor Yellow
    }
}

Write-Host "`n== ffmpeg 확인 ==" -ForegroundColor Cyan
# faster-whisper 와 diarize.py 는 PyAV 로 직접 디코딩하므로 ffmpeg 이 없어도 대개 돈다.
# 다만 드문 코덱에서 도움이 되므로 있으면 좋다.
$ffmpegOk = $false
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ffmpegOk = $true
    $ffver = & ffmpeg -version
    Write-Host (@($ffver) | Select-Object -First 1)
} else {
    Write-Host "ffmpeg 이 없습니다. 필수는 아니지만 두면 좋습니다:" -ForegroundColor Yellow
    Write-Host "  winget install Gyan.FFmpeg"
}

Write-Host "`n== 설치 검증 ==" -ForegroundColor Cyan

# pip 이 exit 0 을 내도 실제로 쓸 수 있는지는 별개다. 가상환경 안에서 직접 확인한다.
$checkPy  = Join-Path ([System.IO.Path]::GetTempPath()) "nokchwi_verify.py"
$checkSrc = @'
import json
r = {}
for mod in ("faster_whisper", "sherpa_onnx", "av", "numpy"):
    try:
        __import__(mod)
        r["mod_" + mod] = True
    except Exception as e:
        r["mod_" + mod] = False
        r["error_mod_" + mod] = "%s: %s" % (type(e).__name__, e)
print("RESULT:" + json.dumps(r))
'@
[System.IO.File]::WriteAllText($checkPy, $checkSrc, (New-Object System.Text.UTF8Encoding($false)))

$verifyOk = $true
$raw = $null
try { $raw = & $py $checkPy } catch { $raw = $null }

$line = $null
if ($raw) { $line = @($raw) | Where-Object { $_ -like "RESULT:*" } | Select-Object -First 1 }

if (-not $line) {
    Write-Host "검증 스크립트가 결과를 내지 못했습니다. 설치가 깨졌을 수 있습니다." -ForegroundColor Red
    if ($raw) { @($raw) | Select-Object -Last 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray } }
    $verifyOk = $false
} else {
    $v = $line.Substring(7) | ConvertFrom-Json

    Write-Host ""
    Write-Host ("  faster-whisper (전사)   : {0}" -f (YesNo $v.mod_faster_whisper))
    Write-Host ("  sherpa-onnx (화자분리)  : {0}" -f (YesNo $v.mod_sherpa_onnx))
    Write-Host ("  av / numpy              : {0}" -f (YesNo ($v.mod_av -and $v.mod_numpy)))
    Write-Host ("  화자 분리 모델          : {0}" -f (YesNo $diarModelsOk))
    Write-Host ("  ffmpeg (선택)           : {0}" -f (YesNo $ffmpegOk))
    $diarReady = $v.mod_sherpa_onnx -and $v.mod_av -and $v.mod_numpy -and $diarModelsOk
    if ($diarReady) {
        Write-Host ("  화자 분리 가능          : {0}" -f (YesNo $diarReady)) -ForegroundColor Green
    } else {
        Write-Host ("  화자 분리 가능          : {0}" -f (YesNo $diarReady)) -ForegroundColor Yellow
    }
    Write-Host ""

    if (-not $v.mod_faster_whisper) {
        $verifyOk = $false
        Write-Host "[경고] faster-whisper 를 불러오지 못합니다. 전사가 되지 않습니다." -ForegroundColor Red
        if ($v.error_mod_faster_whisper) { Write-Host ("       {0}" -f $v.error_mod_faster_whisper) -ForegroundColor DarkGray }
    }
    if (-not $diarReady) {
        Write-Host "[안내] 화자 분리를 쓸 수 없습니다. 전사는 되며 화자는 사용자가 붙여야 합니다." -ForegroundColor Yellow
        if ($v.error_mod_sherpa_onnx) { Write-Host ("       {0}" -f $v.error_mod_sherpa_onnx) -ForegroundColor DarkGray }
    }
}

Remove-Item $checkPy -Force -ErrorAction SilentlyContinue

Write-Host "`n실행은 가상환경을 활성화하지 않고 래퍼를 부릅니다:" -ForegroundColor Green
Write-Host "  .\녹취.ps1 {사건폴더명} -Speakers 2"
Write-Host "`n화자 수를 알면 -Speakers 로 지정하십시오. 지정하지 않으면 과분할합니다." -ForegroundColor Green

if ($verifyOk) {
    Write-Host "`n설치 완료. 검증에서 어긋난 항목이 없습니다." -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n설치는 끝났지만 검증에서 어긋난 항목이 있습니다. 위 [경고] 를 먼저 처리하십시오." -ForegroundColor Red
    exit 1
}
