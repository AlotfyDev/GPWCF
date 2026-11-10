param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-sqlite',
    [int]$Port = 4200,
    [int]$Workers = 1
)

$ErrorActionPreference = 'Stop'
if ($Workers -ne 1) {
    throw 'The SQLite qualification profile supports one Prefect API server worker. Multi-worker API-server mode requires PostgreSQL; it is not enabled by this runbook.'
}
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python executable not found: $PythonExecutable"
}

$ScriptsDirectory = Split-Path -Parent $PythonExecutable
$PrefectExecutable = Join-Path $ScriptsDirectory 'prefect.exe'
if (-not (Test-Path -LiteralPath $PrefectExecutable)) {
    throw "Prefect executable not found: $PrefectExecutable"
}

$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$env:PREFECT_LOGGING_LEVEL = 'WARNING'

New-Item -ItemType Directory -Force -Path $env:PREFECT_HOME | Out-Null
Write-Host "Prefect home (outside repository): $env:PREFECT_HOME"
Write-Host "API URL: http://127.0.0.1:$Port/api"
Write-Host "API server workers: 1 (SQLite-supported profile)"
Write-Host "Task runner thread-pool concurrency is configured separately in the PoC Flows."
Write-Host "Stop this foreground process with Ctrl+C when qualification is complete."

& $PrefectExecutable server start --host 127.0.0.1 --port $Port --analytics-off --no-ui --no-scheduler --workers 1
exit $LASTEXITCODE
