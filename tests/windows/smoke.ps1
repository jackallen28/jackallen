# Starts the real CircuitPath.exe on Windows and uses it like the web app
# does: make a profile, autosave some code, read it back, and check that a
# second launch hands over to the running copy. Used by CI and releases.
#   pwsh tests/windows/smoke.ps1 -Exe dist/CircuitPath.exe
param([Parameter(Mandatory)] [string] $Exe)
$ErrorActionPreference = "Stop"

$Exe = (Resolve-Path $Exe).Path
$data = Join-Path ([IO.Path]::GetTempPath()) "circuitpath-smoke"
Remove-Item -Recurse -Force $data -ErrorAction SilentlyContinue
$base = "http://localhost:47820"

$p = Start-Process -FilePath $Exe -ArgumentList "-no-browser", "-data", $data -PassThru
try {
  $info = $null
  for ($i = 0; $i -lt 30 -and -not $info; $i++) {
    try { $info = Invoke-RestMethod "$base/api/info" } catch { Start-Sleep -Seconds 1 }
  }
  if ($info.app -ne "CircuitPath") { throw "CircuitPath.exe didn't start" }
  Write-Host "Started: CircuitPath $($info.version)"

  $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $write = @{ "X-CircuitPath" = "1" }
  $me = Invoke-RestMethod -Method Post "$base/api/students" -Headers $write -ContentType "application/json" `
    -Body '{"names":["ava"],"school":"Test School"}' -WebSession $session
  if ($me.student.names[0] -ne "Ava") { throw "profile wasn't made: $($me | ConvertTo-Json -Depth 5)" }
  Invoke-RestMethod -Method Put "$base/api/me/sketches/freeplay" -Headers $write -ContentType "application/json" `
    -Body '{"code":"// Hello from Windows"}' -WebSession $session | Out-Null
  $sketch = Invoke-RestMethod "$base/api/me/sketches/freeplay" -WebSession $session
  if ($sketch.code -ne "// Hello from Windows") { throw "autosave didn't come back" }
  Write-Host "Profile made, code saved and read back"

  # Another website can't use it: writes without the header are refused.
  try {
    Invoke-RestMethod -Method Post "$base/api/wipe" -ContentType "application/json" -Body '{"confirm":"WIPE"}' | Out-Null
    throw "a write without the X-CircuitPath header was allowed"
  } catch [Microsoft.PowerShell.Commands.HttpResponseException] {
    if ($_.Exception.Response.StatusCode.value__ -ne 403) { throw }
  }

  # Opening it again while it's running just hands over and stops.
  $second = Start-Process -FilePath $Exe -ArgumentList "-no-browser", "-data", "$data-2" -PassThru -Wait
  if ($second.ExitCode -ne 0) { throw "second launch exited with $($second.ExitCode)" }
  Write-Host "Second launch handed over to the running copy"

  if (-not (Test-Path (Join-Path $data "circuitpath.db"))) { throw "no database in $data" }
  Write-Host "Windows smoke test passed"
} finally {
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  Get-Content (Join-Path $data "circuitpath.log") -ErrorAction SilentlyContinue | Select-Object -Last 20
}
