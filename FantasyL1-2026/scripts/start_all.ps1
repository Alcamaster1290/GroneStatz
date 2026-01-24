param(
  [switch]$SkipWatch,
  [ValidateSet("local","test","prod")]
  [string]$Env = "local",
  [switch]$NoBrowser,
  [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$composeFile = Join-Path $root "docker-compose.yml"
$envFile = Join-Path $root ".env"
if ($Env -ne "local") {
  $candidate = Join-Path $root (".env." + $Env)
  if (Test-Path $candidate) {
    $envFile = $candidate
  } else {
    Write-Host "Env file not found: $candidate. Falling back to $envFile"
  }
}

$env:APP_ENV = $Env
$env:ENV_FILE = $envFile
$watcher = Join-Path (Join-Path $root "scripts") "watch_parquets.py"
$python = [System.IO.Path]::Combine($root, ".venv311", "Scripts", "python.exe")

if (-not (Test-Path $python)) {
  $python = "python"
}

Write-Host "Starting Postgres (Docker)..."
Write-Host "APP_ENV=$Env"
Write-Host "ENV_FILE=$envFile"
if (Test-Path $composeFile) {
  if (Test-Path $envFile) {
    & docker compose -f $composeFile --env-file $envFile up -d
  } else {
    & docker compose -f $composeFile up -d
  }
} else {
  Write-Error "docker-compose.yml not found: $composeFile"
  exit 1
}

if ($Rebuild) {
  Write-Host "Rebuilding DuckDB + Postgres caches..."
  $ingestScript = Join-Path (Join-Path $root "scripts") "ingest_to_duckdb.py"
  $syncScript = Join-Path (Join-Path $root "scripts") "sync_duckdb_to_postgres.py"
  $imagesScript = Join-Path (Join-Path $root "scripts") "convert_images_to_png.py"
  if (Test-Path $imagesScript) {
    Write-Host "Converting images to PNG..."
    & $python $imagesScript
  }
  & $python $ingestScript
  & $python $syncScript
}

Write-Host "Starting backend (FastAPI)..."
Start-Process -FilePath $python -WorkingDirectory $backendDir -ArgumentList "-m","uvicorn","app.main:app","--reload","--port","8000"

Write-Host "Starting frontend (Next.js)..."
Start-Process -FilePath "cmd.exe" -WorkingDirectory $frontendDir -ArgumentList "/c","npm run dev"

if (-not $SkipWatch -and (Test-Path $watcher)) {
  Write-Host "Starting parquet watcher..."
  Start-Process -FilePath $python -WorkingDirectory $root -ArgumentList $watcher,"--run-on-start"
} elseif (-not $SkipWatch) {
  Write-Host "Watcher not found at $watcher"
}

Write-Host "All services started."

if (-not $NoBrowser) {
  Start-Process "http://localhost:3000"
}
