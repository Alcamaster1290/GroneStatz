param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassthroughArgs
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = Join-Path $repoRoot "scripts\gronestats\run_gronestats_pipeline.ps1"

if (-not (Test-Path $target)) {
    throw "No se encontró el wrapper nuevo: $target"
}

Write-Warning "scripts\\run_gronestats_pipeline.ps1 está deprecado. Usa scripts\\gronestats\\run_gronestats_pipeline.ps1."
& $target @PassthroughArgs
exit $LASTEXITCODE

