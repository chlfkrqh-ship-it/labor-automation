# 시스템 파일만 zip으로 보관한다. 사건 자료와 파이썬 환경은 제외한다.
#   .\백업.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$dst = Join-Path (Split-Path $PSScriptRoot -Parent) "노동사건자동화-백업"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$zip = Join-Path $dst ("노동사건자동화-시스템_{0}.zip" -f (Get-Date -Format "yyyyMMdd-HHmm"))

$stage = Join-Path $env:TEMP ("백업_" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# 제외: 사건 자료, 작업 폴더, 완성본 샘플, 파이썬 캐시·환경, 음성·토큰
$exDirs = @(
    "사건", "결과", "샘플", "01_입력", "02_결과", "03_보관", "99_오류",
    "__pycache__", ".pytest_cache", ".venv", "models", "extract", "src_decompiled",
    "비교", "캐시", "추출캐시", "백업"
)
$exFiles = @("*.m4a","*.mp3","*.wav","*.flac","*.mp4","*.mov","*.log",".hf_token","_추출.txt","~`$*")

robocopy $PSScriptRoot $stage /E /XD @exDirs /XF @exFiles /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null

# 사건 원자료(법원에서 다시 받을 수 있는 PDF 등 19GB)는 위에서 제외했지만,
# 우리가 만든 산출물은 잃으면 되찾을 수 없으므로 담는다. 전부 합쳐 20MB 남짓이다.
$산출물 = @("*.md", "*.yaml", "*.yml", "최종서면*.docx", "서면_프레임*.docx", "서면초안*.docx")
$사건폴더 = @("1_검토의견\사건", "3_서면보강\사건", "4_서면작성\사건", "5_녹취록\사건", "6_손해배상계산\사건")
foreach ($folder in $사건폴더) {
    $source = Join-Path $PSScriptRoot $folder
    if (Test-Path $source) {
        robocopy $source (Join-Path $stage $folder) @산출물 `
            /E /XD "__pycache__" "추출캐시" "캐시" ".claude" /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    }
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
Remove-Item $stage -Recurse -Force

$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "백업 완료: $zip  ($mb MB)" -ForegroundColor Green

# 20개를 넘으면 오래된 것부터 지운다
$old = Get-ChildItem $dst -Filter "노동사건자동화-시스템_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 20
if ($old) {
    $old | Remove-Item -Force
    Write-Host "오래된 백업 $($old.Count)개 정리" -ForegroundColor DarkGray
}
