param(
  [switch]$SkipWatch,
  [switch]$Rebuild,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$script = Join-Path $root "scripts" "start_all.ps1"

$args = @{ Env = "prod" }
if ($SkipWatch) { $args.SkipWatch = $true }
if ($Rebuild) { $args.Rebuild = $true }
if ($NoBrowser) { $args.NoBrowser = $true }

& $script @args
