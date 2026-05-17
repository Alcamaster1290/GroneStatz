param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassthroughArgs
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = Join-Path $repoRoot "scripts\gronestats\register_gronestats_pipeline_task.ps1"

if (-not (Test-Path $target)) {
    throw "No se encontró el wrapper nuevo: $target"
}

Write-Warning "scripts\\register_gronestats_pipeline_task.ps1 está deprecado. Usa scripts\\gronestats\\register_gronestats_pipeline_task.ps1."
& $target @PassthroughArgs
exit $LASTEXITCODE

