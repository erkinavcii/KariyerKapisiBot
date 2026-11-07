# Kariyer Kapisi botunu calistirir ve ciktiyi logs\bot_YYYY-MM.log dosyasina ekler.
# Windows Gorev Zamanlayici bu dosyayi cagirir:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File calistir.ps1
# Ek argumanlar (ornek: --dry-run --limit 2) oldugu gibi bota iletilir.

Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$python = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

New-Item -ItemType Directory -Force -Path 'logs' | Out-Null
$log = Join-Path 'logs' ("bot_{0}.log" -f (Get-Date -Format 'yyyy-MM'))

"===== {0} =====" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Out-File -FilePath $log -Append -Encoding utf8
$cikti = & $python kariyerkapisibot.py @args 2>&1 | ForEach-Object { "$_" }
$kod = $LASTEXITCODE
$cikti | Out-File -FilePath $log -Append -Encoding utf8
"(cikis kodu: $kod)" | Out-File -FilePath $log -Append -Encoding utf8
exit $kod
