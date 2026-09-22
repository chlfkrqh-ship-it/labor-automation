# 대법원 계산프로그램 폴더를 버전째로 박제한다.
# SUT.Updater.exe 가 ecfs.scourt.go.kr/psp/update 에서 자동 갱신하며 덮어쓰므로,
# 흡수 작업 전에 반드시 스냅샷을 떠 둔다.
#
# Logs\ 는 제외한다. log4net 이 DEBUG 레벨이라 사건 데이터가 남아 있을 수 있다.

$ver = (Select-String -Path 'C:\work\sut\sut_version.ini' -Pattern '^ver=(.+)$').Matches[0].Groups[1].Value
$dst = "C:\sut_snapshot\$ver"
robocopy C:\work\sut $dst /E /XD Logs /R:1 /W:1 | Out-Null
"스냅샷 완료: $dst"
