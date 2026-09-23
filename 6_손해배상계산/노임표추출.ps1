<#
노임표·생명표 추출 — 한 번에 끝낸다.

  탐색기에서 이 파일 우클릭 → "PowerShell에서 실행"
  또는  powershell -ExecutionPolicy Bypass -File .\노임표추출.ps1

하는 일
  1. 대법원 「손해배상 등 계산프로그램」 설치 위치를 찾는다
  2. 프로그램 폴더를 스냅샷으로 박제한다 (Updater가 덮어쓰기 전에)
  3. accdb 를 CSV 로 덤프한다  ← 32비트 프로세스가 필요하므로 자동으로 다시 띄운다
  4. data\ 의 CSV 4종으로 정규화한다
  5. scripts\점검.py 로 확인하고 테스트를 돌린다

설치 경로를 직접 지정하려면:
  .\노임표추출.ps1 -SutPath "D:\sut"
#>
param(
    [string]$SutPath = "",
    [switch]$NoSnapshot
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

trap {
    Write-Host "`n[예기치 못한 오류]" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "`n위 내용을 그대로 붙여 문의하십시오." -ForegroundColor Yellow
    exit 1
}

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function Head($msg) { Write-Host "`n== $msg ==" -ForegroundColor Cyan }

# ── 0. 준비 확인 ─────────────────────────────────────────────────────
Head "준비 확인"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Say "python 을 찾을 수 없습니다." "Red"
    Say "파이썬을 설치하고 설치 화면에서 'Add python.exe to PATH' 를 체크하십시오." "Yellow"
    exit 1
}
Say ("python  " + (python --version 2>&1))
if (-not (Test-Path "scripts\normalize.py")) {
    Say "여기가 6_손해배상계산 폴더가 아닙니다: $here" "Red"
    Say "이 스크립트는 6_손해배상계산 폴더 안에서 실행해야 합니다." "Yellow"
    exit 1
}
Say "폴더    $here"

# ── 1. 설치 위치 찾기 ────────────────────────────────────────────────
Head "대법원 계산프로그램 찾기"

function Find-Sut {
    param([string]$Given)
    if ($Given) {
        if (Test-Path (Join-Path $Given "DB")) { return $Given }
        throw "지정한 경로에 DB 폴더가 없습니다: $Given"
    }
    $cands = @("C:\work\sut", "D:\work\sut",
               "${env:ProgramFiles(x86)}\sut", "$env:ProgramFiles\sut",
               "C:\sut", "D:\sut")
    foreach ($c in $cands) {
        if (Test-Path (Join-Path $c "DB")) { return $c }
    }
    Say "표준 위치에 없습니다. 드라이브를 훑습니다 (1~2분)..." "Yellow"
    foreach ($root in @("C:\", "D:\")) {
        if (-not (Test-Path $root)) { continue }
        $hit = Get-ChildItem -Path $root -Filter "sut_version.ini" -Recurse -Depth 5 `
                 -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.Directory.FullName }
        $hit = Get-ChildItem -Path $root -Filter "SUT.SBGCalc.exe" -Recurse -Depth 5 `
                 -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.Directory.FullName }
    }
    return $null
}

$sut = Find-Sut -Given $SutPath
if (-not $sut) {
    Say "계산프로그램을 찾지 못했습니다." "Red"
    Say "바탕화면 바로가기 우클릭 > 속성 > [대상] 의 폴더를 확인한 뒤 다시 실행하십시오:" "Yellow"
    Say '  .\노임표추출.ps1 -SutPath "그 폴더 경로"' "Yellow"
    exit 1
}
Say "설치 위치: $sut" "Green"

$dbDir = Join-Path $sut "DB"
$found = Get-ChildItem $dbDir -Filter *.accdb -ErrorAction SilentlyContinue
if (-not $found) { Say "DB 폴더에 accdb 가 없습니다: $dbDir" "Red"; exit 1 }
Say ("DB 파일: " + (($found | ForEach-Object { $_.Name }) -join ", "))

# ── 2. 스냅샷 ────────────────────────────────────────────────────────
if (-not $NoSnapshot) {
    Head "프로그램 폴더 스냅샷"
    $ini = Join-Path $sut "sut_version.ini"
    $ver = "unknown"
    if (Test-Path $ini) {
        $m = Select-String -Path $ini -Pattern '^ver=(.+)$'
        if ($m) { $ver = $m.Matches[0].Groups[1].Value.Trim() }
    }
    $snap = "C:\sut_snapshot\$ver"
    if (Test-Path $snap) {
        Say "이미 있습니다: $snap  (건너뜁니다)" "DarkGray"
    } else {
        robocopy $sut $snap /E /XD Logs /R:1 /W:1 | Out-Null
        Say "스냅샷: $snap  (버전 $ver)" "Green"
    }
}

# ── 3. 32비트로 갈아타기 ─────────────────────────────────────────────
$extractRoot = "C:\sut_extract\db"

if ([Environment]::Is64BitProcess) {
    Head "32비트 PowerShell 로 전환"
    Say "ACE OLEDB 공급자가 x86 이라 64비트 프로세스에서는 accdb 를 열 수 없습니다."
    $ps32 = Join-Path $env:WINDIR "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path $ps32)) { Say "32비트 PowerShell 을 찾지 못했습니다: $ps32" "Red"; exit 1 }
    $self = $MyInvocation.MyCommand.Path
    & $ps32 -NoProfile -ExecutionPolicy Bypass -File $self -SutPath $sut -NoSnapshot
    exit $LASTEXITCODE
}

# ── 4. accdb → CSV ───────────────────────────────────────────────────
Head "accdb 를 CSV 로 덤프 (32비트)"

Add-Type -AssemblyName System.Data
$provider = "Microsoft.ACE.OLEDB.12.0"
$want = @("TB_SUT001","TB_SUT002","TB_SUT003","TB_SUT004")
$hitDir = $null

foreach ($db in $found) {
    $name = [IO.Path]::GetFileNameWithoutExtension($db.Name)
    $out  = Join-Path $extractRoot $name
    New-Item -ItemType Directory -Force -Path $out | Out-Null

    try {
        $conn = New-Object System.Data.OleDb.OleDbConnection("Provider=$provider;Data Source=$($db.FullName);")
        $conn.Open()
    } catch {
        Say "`n[ACE OLEDB 공급자 없음]" "Red"
        Say "Microsoft Access Database Engine 2016 (x86) 을 설치하십시오." "Yellow"
        Say "64비트 Office 가 깔려 있어 설치가 거부되면 다음처럼 우회합니다:" "Yellow"
        Say "  AccessDatabaseEngine_X86.exe /quiet" "Yellow"
        exit 1
    }

    Say "`n--- $name.accdb ---"
    $tables = $conn.GetSchema("Tables") | Where-Object TABLE_TYPE -eq "TABLE"
    foreach ($t in $tables) {
        $tbl = $t.TABLE_NAME
        if ($tbl -like "~TMPCLP*") { continue }
        $dt = New-Object System.Data.DataTable
        (New-Object System.Data.OleDb.OleDbDataAdapter("SELECT * FROM [$tbl]", $conn)).Fill($dt) | Out-Null
        $cols = $dt.Columns | ForEach-Object { $_.ColumnName }
        $dt | Select-Object $cols | Export-Csv (Join-Path $out "$tbl.csv") -NoTypeInformation -Encoding UTF8
        "{0,-22} {1,8} 행" -f $tbl, $dt.Rows.Count
    }
    $conn.Close()

    $have = @($want | Where-Object { Test-Path (Join-Path $out "$_.csv") })
    if ($have.Count -eq 4) { $hitDir = $out; Say "-> 노임표·생명표 4종 확인" "Green" }
}

if (-not $hitDir) {
    Say "`nTB_SUT001~004 를 한 폴더에서 모두 찾지 못했습니다." "Red"
    Say "$extractRoot 아래 폴더들을 열어 어디에 있는지 확인한 뒤 수동으로 실행하십시오:" "Yellow"
    Say "  python scripts\normalize.py <그 폴더>" "Yellow"
    exit 1
}

# ── 5. 정규화 ────────────────────────────────────────────────────────
Head "정규화"
python -B scripts\normalize.py $hitDir
if ($LASTEXITCODE -ne 0) { Say "normalize.py 실패" "Red"; exit 1 }

# ── 6. 확인 ──────────────────────────────────────────────────────────
# python 이 실패해도 PowerShell 은 멈추지 않으므로 종료코드를 직접 본다.
Head "확인"
Get-ChildItem "data" -Filter *.csv | ForEach-Object {
    "{0,-26} {1,8:N0} KB" -f $_.Name, ($_.Length / 1KB)
}
python -B scripts\점검.py
$checkFailed = ($LASTEXITCODE -ne 0)

Head "테스트"
python -B -m pytest tests -q -p no:cacheprovider
$testFailed = ($LASTEXITCODE -ne 0)

if ($checkFailed -or $testFailed) {
    Say "`n추출은 끝났지만 점검이나 테스트에서 실패가 있습니다. 위 [문제]·failed 줄을 그대로 붙여 문의하십시오." "Red"
    exit 1
}
Say "`n끝났습니다. 점검과 테스트가 실패(failed) 없이 모두 통과했습니다." "Green"
Say "data\ 의 CSV 4종은 OneDrive 로 다른 PC에도 넘어갑니다." "Green"
Say "C:\sut_extract 와 C:\sut_snapshot 은 저장소로 옮기지 마십시오." "DarkGray"
