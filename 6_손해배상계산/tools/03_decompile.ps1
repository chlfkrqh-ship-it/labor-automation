# 계산 로직 어셈블리를 C# 소스로 복원한다.
# .pdb 가 함께 배포되고 난독화도 없어서 변수명까지 복원된다.
#
# 사전 준비:
#   winget install Microsoft.DotNet.SDK.8
#   dotnet tool install -g ilspycmd --version 8.2.0.7535
#
# ilspycmd 8.2 는 .NET 6 타깃이라 8만 설치된 PC에서는 롤포워드가 필요하다.

$env:DOTNET_ROLL_FORWARD = 'Major'
$src = 'C:\sut_extract\src'

foreach ($a in 'SUT.SBGCalc.exe','SUT.DamgCalcLib.dll','SBCalc.dll','SUT.Common.dll') {
  $n = [IO.Path]::GetFileNameWithoutExtension($a)
  ilspycmd "C:\work\sut\$a" -o "$src\$n" -p --use-varnames-from-pdb
}

Get-ChildItem $src -Recurse -Filter *.cs |
  Select-Object @{n='File';e={$_.FullName.Replace("$src\",'')}},
                @{n='KB';e={[math]::Round($_.Length/1KB,1)}} |
  Sort-Object KB -Descending | Select-Object -First 40 | Format-Table -AutoSize
