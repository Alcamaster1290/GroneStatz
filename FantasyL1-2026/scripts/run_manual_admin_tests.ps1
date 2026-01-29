param(
  [ValidateSet("test","prod")]
  [string]$Env = "prod"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $root (".env." + $Env)
if (-not (Test-Path $envFile)) {
  throw "Env file not found: $envFile"
}

$env:APP_ENV = $Env
$env:ENV_FILE = $envFile

$python = [System.IO.Path]::Combine($root, ".venv", "Scripts", "python.exe")
if (-not (Test-Path $python)) {
  $python = "python"
}

Write-Host "Running migrations ($Env)..."
& $python -m alembic -c (Join-Path $root "backend" "alembic.ini") upgrade head

Write-Host "Running manual admin tests ($Env)..."
& $python (Join-Path $root "scripts" "manual_admin_tests.py")
