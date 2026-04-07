param(
    [string]$League = "Liga 1 Peru",
    [int]$Season = 2025,
    [ValidateSet("full", "incremental")]
    [string]$Mode = "incremental",
    [switch]$OnlyMissing,
    [switch]$Force,
    [switch]$DryRun,
    [string]$PythonPath
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$logDir = Join-Path $repoRoot "logs\pipeline"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "pipeline_$stamp.log"

$pythonCandidates = @()
if ($PythonPath) {
    $pythonCandidates += $PythonPath
}
$python311 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
if (Test-Path $python311) {
    $pythonCandidates += $python311
}
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonCandidates += $pythonCommand.Source
}
$pythonCandidates = $pythonCandidates | Where-Object { $_ } | Select-Object -Unique

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path $candidate)) {
        continue
    }
    try {
        & $candidate -c "import pandas, pyarrow, openpyxl" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = $candidate
            break
        }
    }
    catch {
    }
}

if (-not $pythonExe) {
    throw "No se encontró un intérprete Python con pandas/pyarrow/openpyxl. Usa -PythonPath para indicarlo explícitamente."
}

$argsList = @(
    "-m", "gronestats.processing.pipeline",
    "run",
    "--league", $League,
    "--season", "$Season",
    "--mode", $Mode
)

if ($OnlyMissing) {
    $argsList += "--only-missing"
}
if ($Force) {
    $argsList += "--force"
}
if ($DryRun) {
    $argsList += "--dry-run"
}
$argsList += @("--publish-target", "all")

Push-Location $repoRoot
try {
    Write-Host "Python: $pythonExe"
    Write-Host "Log: $logPath"
    & $pythonExe @argsList 2>&1 | Tee-Object -FilePath $logPath
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
