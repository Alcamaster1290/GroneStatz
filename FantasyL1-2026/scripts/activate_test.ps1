param(
  [switch]$Rebuild,
  [switch]$NoBrowser,
  [switch]$SkipClearRounds
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $root "docker-compose.yml"
$envFile = Join-Path $root ".env.test"
$backendDir = Join-Path $root "backend"
$startAll = Join-Path (Join-Path $root "scripts") "start_all.ps1"

if (-not (Test-Path $envFile)) {
  Write-Error "Missing .env.test at $envFile"
  exit 1
}

$env:APP_ENV = "test"
$env:ENV_FILE = $envFile

$python = [System.IO.Path]::Combine($root, ".venv", "Scripts", "python.exe")
if (-not (Test-Path $python)) {
  $python = "python"
}

Write-Host "Starting Postgres (Docker)..."
& docker compose -f $composeFile --env-file $envFile up -d

Write-Host "Running migrations (test)..."
& $python -m alembic -c (Join-Path $backendDir "alembic.ini") upgrade head

if (-not $SkipClearRounds) {
  Write-Host "Clearing rounds and fixtures (test)..."
  & $python (Join-Path $root "scripts" "clear_rounds.py")
}

if ($Rebuild) {
  $imagesScript = Join-Path (Join-Path $root "scripts") "convert_images_to_png.py"
  if (Test-Path $imagesScript) {
    Write-Host "Converting images to PNG..."
    & $python $imagesScript
  }
  Write-Host "Rebuilding DuckDB + Postgres caches..."
  & $python (Join-Path (Join-Path $root "scripts") "ingest_to_duckdb.py")
  & $python (Join-Path (Join-Path $root "scripts") "sync_duckdb_to_postgres.py")
}

Write-Host "Starting services (test)..."
if ($NoBrowser) {
  & $startAll -Env test -SkipWatch -NoBrowser
} else {
  & $startAll -Env test -SkipWatch
}
