param(
  [Parameter(Mandatory=$true)][string]$Dir,
  [string]$Filter = '*.jpg',
  [string]$Out = 'ocr.json'
)
# Windows 기본 문자인식(한국어)으로 폴더의 그림을 읽어 ocr.json 하나로 쓴다: [{file, lines:[{t,x,y,w,h}]}]
# 쓰는 곳: 4_서면작성/scripts/evidence_cite_review.py (글자층이 없는 호증 면). -Out 은 파일 이름만 준다(경로를 주면 실패).
# 그림은 긴 변 2,600px 안팎으로 만든다. 한국어 문자인식 언어가 깔려 있지 않으면 'no ko ocr engine' 으로 멈춘다.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$lang = New-Object Windows.Globalization.Language 'ko'
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) { throw 'no ko ocr engine' }
$files = Get-ChildItem -LiteralPath $Dir -Filter $Filter | Sort-Object Name
$all = New-Object System.Collections.ArrayList
foreach ($f in $files) {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $lines = New-Object System.Collections.ArrayList
  foreach ($line in $result.Lines) {
    $x0 = [double]::MaxValue; $y0 = [double]::MaxValue; $x1 = 0.0; $y1 = 0.0
    foreach ($w in $line.Words) {
      $r = $w.BoundingRect
      if ($r.X -lt $x0) { $x0 = $r.X }
      if ($r.Y -lt $y0) { $y0 = $r.Y }
      if (($r.X + $r.Width) -gt $x1) { $x1 = $r.X + $r.Width }
      if (($r.Y + $r.Height) -gt $y1) { $y1 = $r.Y + $r.Height }
    }
    [void]$lines.Add([ordered]@{ t = $line.Text; x = [int]$x0; y = [int]$y0; w = [int]($x1 - $x0); h = [int]($y1 - $y0) })
  }
  [void]$all.Add([ordered]@{ file = $f.Name; lines = $lines })
  $stream.Dispose()
  $bitmap.Dispose()
}
$json = $all | ConvertTo-Json -Depth 6 -Compress
[System.IO.File]::WriteAllText((Join-Path $Dir $Out), $json, (New-Object System.Text.UTF8Encoding($false)))
'done ' + $files.Count
