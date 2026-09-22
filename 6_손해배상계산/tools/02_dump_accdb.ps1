# CortCalc.accdb 의 모든 테이블을 CSV로 덤프한다.
#
# 반드시 32비트 PowerShell 로 실행할 것:
#   C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe
# SUT 본체와 ACE 드라이버가 모두 x86 이라, 64비트 프로세스에서는
# 'Microsoft.ACE.OLEDB.12.0 공급자는 로컬 컴퓨터에 등록할 수 없습니다' 가 뜬다.

if ([Environment]::Is64BitProcess) {
  throw "32비트 PowerShell 로 실행하세요: C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
}

Add-Type -AssemblyName System.Data
$provider = 'Microsoft.ACE.OLEDB.12.0'
$outRoot  = 'C:\sut_extract\db'

foreach ($name in 'Common','CortCalc','DamgCalc') {
  $db  = "C:\work\sut\DB\$name.accdb"
  if (-not (Test-Path $db)) { continue }
  $out = Join-Path $outRoot $name
  New-Item -ItemType Directory -Force -Path $out | Out-Null

  $conn = New-Object System.Data.OleDb.OleDbConnection("Provider=$provider;Data Source=$db;")
  $conn.Open()
  "`n===== $name.accdb ====="
  foreach ($t in ($conn.GetSchema('Tables') | Where-Object TABLE_TYPE -eq 'TABLE')) {
    $tbl = $t.TABLE_NAME
    if ($tbl -like '~TMPCLP*') { continue }   # Access 임시 클립보드 테이블
    $dt  = New-Object System.Data.DataTable
    (New-Object System.Data.OleDb.OleDbDataAdapter("SELECT * FROM [$tbl]", $conn)).Fill($dt) | Out-Null
    $cols = $dt.Columns | ForEach-Object { $_.ColumnName }
    $dt | Select-Object $cols | Export-Csv (Join-Path $out "$tbl.csv") -NoTypeInformation -Encoding UTF8
    "{0,-20} {1,7} rows" -f $tbl, $dt.Rows.Count
  }
  $conn.Close()
}
"`n다음: python scripts/normalize.py $outRoot\CortCalc"
