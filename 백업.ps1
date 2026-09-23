# 시스템 파일과 사건 산출물을 zip 으로 보관한다. 사건 원자료와 파이썬 환경은 제외한다.
#   .\백업.ps1
# 실행 정책이 Restricted 인 PC에서는  powershell -ExecutionPolicy Bypass -File .\백업.ps1
#
# 복사하지 못한 파일이 있으면 zip 이름 끝에 '_불완전' 을 붙이고 로그를 남긴 뒤 종료코드 1 로 끝난다.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$dst = Join-Path (Split-Path $PSScriptRoot -Parent) "노동사건자동화-백업"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$zip = Join-Path $dst ("노동사건자동화-시스템_{0}.zip" -f $stamp)
$log = Join-Path $dst ("노동사건자동화-시스템_{0}.log" -f $stamp)

$stage = Join-Path $env:TEMP ("백업_" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# robocopy 는 실패해도 예외를 던지지 않는다. 종료코드 0~7 은 정상(복사함·새 파일 없음·남는 파일
# 있음의 조합)이고 8 이상이면 복사하지 못한 파일이 있다. 모아 두었다가 끝에 알린다.
$실패 = @()
$공통옵션 = @("/R:1", "/W:1", "/NP", "/NFL", "/NDL", "/NJH", "/LOG+:$log")
function Test-Robocopy([string]$What) {
    if ($LASTEXITCODE -ge 8) { $script:실패 += "$What (robocopy 종료코드 $LASTEXITCODE)" }
}

# 제외: 사건 자료, 작업 폴더, 완성본 샘플, 파이썬 캐시·환경, 음성·토큰
$exDirs = @(
    "사건", "결과", "샘플", "01_입력", "02_결과", "03_보관", "99_오류",
    "__pycache__", ".pytest_cache", ".venv", "models", "extract", "src_decompiled",
    "캐시", "추출캐시", "백업"
)
# 음성·영상은 5_녹취록/transcribe.py 가 받는 형식을 모두 뺀다.
$exFiles = @("*.m4a","*.mp3","*.wav","*.flac","*.mp4","*.mov",
             "*.aac","*.ogg","*.opus","*.wma","*.amr","*.3gp","*.avi","*.mkv","*.webm",
             "*.log",".hf_token","_추출.txt","~`$*")

try {
    robocopy $PSScriptRoot $stage /E /XD @exDirs /XF @exFiles @공통옵션 | Out-Null
    Test-Robocopy "시스템 파일"

    # 사건 원자료(법원에서 다시 받을 수 있는 PDF 등 19GB)는 위에서 제외했지만,
    # 우리가 만든 산출물은 잃으면 되찾을 수 없으므로 담는다. 전부 합쳐 20MB 남짓이다.
    # '(' 로 시작하는 파일은 의뢰인 산출물이다(서면 _초안·_N차 수정안, 검토의견서. .gitignore 참고).
    $산출물 = @("*.md", "*.yaml", "*.yml", "(*)*.docx", "최종서면*.docx", "서면_프레임*.docx", "서면초안*.docx")
    # 2_판례검색 은 2026. 9. 22. 폴더 이름이 결과 → 사건 으로 바뀌었다. 옛 폴더가 남은 PC가 있어 둘 다 본다.
    $사건폴더 = @("1_검토의견\사건", "2_판례검색\사건", "2_판례검색\결과", "3_서면보강\사건",
                 "4_서면작성\사건", "5_녹취록\사건", "6_손해배상계산\사건")
    foreach ($folder in $사건폴더) {
        $source = Join-Path $PSScriptRoot $folder
        if (-not (Test-Path -LiteralPath $source)) { continue }
        robocopy $source (Join-Path $stage $folder) @산출물 `
            /E /XD "__pycache__" "추출캐시" "캐시" ".claude" /XF "~`$*" @공통옵션 | Out-Null
        Test-Robocopy "$folder 산출물"

        # 서면 docx 는 이름 규칙이 바뀌어 왔고(최종서면.docx → ({의뢰인명}) {서면명}_초안.docx,
        # 4_서면작성/CLAUDE.md 3-1절) 담당자가 고쳐 돌려준 파일은 이름이 제각각이다. 이름에 기대지
        # 않고 라운드N\출력\ 의 docx 를 모두 담는다. 병합 전 보관본(*.bak_merge_*)도 담는다.
        # 다시 병합하기 전의 담당자 수정본일 수 있기 때문이다.
        $출력폴더 = @(Get-ChildItem -LiteralPath $source -Directory -Recurse -Filter "출력" `
                        -ErrorAction SilentlyContinue -ErrorVariable scanErrors)
        if ($scanErrors) { $실패 += "$folder 의 출력 폴더 찾기 $($scanErrors.Count)건 실패(긴 경로·권한)" }
        foreach ($out in $출력폴더) {
            if (-not $out.FullName.StartsWith($source, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $rel = Join-Path $folder ($out.FullName.Substring($source.Length).TrimStart('\'))
            robocopy $out.FullName (Join-Path $stage $rel) "*.docx" /E /XF "~`$*" @공통옵션 | Out-Null
            Test-Robocopy "$rel 의 docx"
        }
    }

    # 판례검색·서면보강의 검색 기록은 채팅으로만 답하는 작업이 남기는 유일한 기록이다
    # (lbox-검색 스킬 7항). 공통\캐시 에 있어 위에서 빠지므로 따로 담는다.
    # 캐시의 나머지(법제처 응답·현황판 등)는 다시 받거나 다시 만들 수 있다.
    $검색기록 = Join-Path $PSScriptRoot "공통\캐시\판례검색기록"
    if (Test-Path -LiteralPath $검색기록) {
        robocopy $검색기록 (Join-Path $stage "공통\캐시\판례검색기록") "*.md" /E @공통옵션 | Out-Null
        Test-Robocopy "판례검색기록"
    }

    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
}
finally {
    # 압축이 실패해도 사건 산출물 사본이 %TEMP% 에 남지 않게 한다.
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
}

$mb = [math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)
if ($실패.Count -gt 0) {
    $불완전 = $zip -replace '\.zip$', '_불완전.zip'
    Move-Item -LiteralPath $zip -Destination $불완전 -Force
    Write-Host "백업을 만들었지만 복사하지 못한 파일이 있습니다: $불완전  ($mb MB)" -ForegroundColor Red
    foreach ($item in $실패) { Write-Host "  - $item" -ForegroundColor Red }
    Write-Host "어느 파일인지는 로그에 있습니다: $log" -ForegroundColor Yellow
    Write-Host "Word 로 열어 둔 파일, OneDrive 에서 아직 내려받지 않은 파일, 긴 경로가 흔한 원인입니다." -ForegroundColor Yellow
    $종료코드 = 1
} else {
    Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
    Write-Host "백업 완료: $zip  ($mb MB)" -ForegroundColor Green
    $종료코드 = 0
}

# 20개를 넘으면 오래된 것부터 지운다(실패했을 때만 남는 로그도 같은 수로)
foreach ($pattern in @("노동사건자동화-시스템_*.zip", "노동사건자동화-시스템_*.log")) {
    $old = Get-ChildItem $dst -Filter $pattern | Sort-Object LastWriteTime -Descending | Select-Object -Skip 20
    if ($old) {
        $old | Remove-Item -Force
        Write-Host "오래된 백업 $($old.Count)개 정리" -ForegroundColor DarkGray
    }
}
exit $종료코드
