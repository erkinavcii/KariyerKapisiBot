# Windows Gorev Zamanlayici'ya "KariyerKapisiBot" gorevini ekler (veya gunceller).
# Her gun saat $Saat'te calisir; bilgisayar o saatte kapaliysa acildiginda calisir.
# Kullanim (proje klasorunde):
#   powershell -ExecutionPolicy Bypass -File gorev_kur.ps1            # 15:00
#   powershell -ExecutionPolicy Bypass -File gorev_kur.ps1 -Saat 09:00
# Kaldirmak icin:
#   Unregister-ScheduledTask -TaskName KariyerKapisiBot -Confirm:$false
param([string]$Saat = '15:00')

$dir = $PSScriptRoot
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\calistir.ps1`"" `
    -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At $Saat
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'KariyerKapisiBot' -Force `
    -Description "Kariyer Kapisi ilan botu - her gun $Saat, kacirilirsa acilista" `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null

$t = Get-ScheduledTask -TaskName 'KariyerKapisiBot'
$i = $t | Get-ScheduledTaskInfo
Write-Host "Gorev kuruldu. Durum: $($t.State) | Sonraki calisma: $($i.NextRunTime)"
Write-Host "Hemen denemek icin:  Start-ScheduledTask -TaskName KariyerKapisiBot"
Write-Host "Loglar:              $dir\logs\"
