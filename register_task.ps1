# Fokus Laufen PC 동기화 — 작업 스케줄러 등록 (setup.bat 이 부름)
# PC 로그인 3분 뒤 + 매일 오전 9시(꺼져 있었으면 켜진 뒤) 실행. sync_today.bat auto 는 하루 한 번만 실제로 받음
$dir = $PSScriptRoot
$bat = Join-Path $dir 'sync_today.bat'
$log = Join-Path $dir 'data\sync.log'
$a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"`"$bat`" auto >> `"$log`" 2>&1`""
$t1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t1.Delay = 'PT3M'
$t2 = New-ScheduledTaskTrigger -Daily -At 9am
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$desc = 'Fokus Laufen: 가민 커넥트에서 최근 기록을 받아 Fokus Laufen 앱에 올립니다 (하루 한 번). 실행 기록: ' + $log
Register-ScheduledTask -TaskName 'Fokus Laufen 동기화' -Description $desc -Action $a -Trigger $t1, $t2 -Settings $s -Force | Out-Null
Write-Output '등록했어요. PC 로그인 3분 뒤 / 매일 오전 9시에 하루 한 번 실행돼요.'
