param(
    [string]$TaskName = "GroneStatz Pipeline",
    [string]$League = "Liga 1 Peru",
    [int]$Season = 2025,
    [string]$At = "06:00",
    [switch]$Force
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$wrapper = Join-Path $repoRoot "scripts\run_gronestats_pipeline.ps1"

if (-not (Test-Path $wrapper)) {
    throw "No se encontró el wrapper: $wrapper"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$wrapper`"",
    "-League", "`"$League`"",
    "-Season", "$Season",
    "-Mode", "incremental",
    "-OnlyMissing"
)
if ($Force) {
    $arguments += "-Force"
}
$argumentText = $arguments -join " "

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentText -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Tarea registrada: $TaskName"
Write-Host "Ejecuta: powershell.exe $argumentText"
