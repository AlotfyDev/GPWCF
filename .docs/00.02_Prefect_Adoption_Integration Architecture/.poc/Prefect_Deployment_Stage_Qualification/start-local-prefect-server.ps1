param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-deployment',
    [int]$Port = 4210
)
$ErrorActionPreference = 'Stop'
$PrefectExecutable = Join-Path (Split-Path -Parent $PythonExecutable) 'prefect.exe'
if (-not (Test-Path -LiteralPath $PrefectExecutable)) { throw "Prefect executable not found: $PrefectExecutable" }
$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$env:PREFECT_LOGGING_LEVEL = 'WARNING'
New-Item -ItemType Directory -Force -Path $PrefectHome | Out-Null
Write-Host "Prefect home (outside repository): $PrefectHome"
Write-Host "API URL: http://127.0.0.1:$Port/api"
Write-Host 'SQLite profile: one API-server worker; Process Worker concurrency is configured separately.'
& $PrefectExecutable server start --host 127.0.0.1 --port $Port --analytics-off --no-ui --no-scheduler --workers 1
exit $LASTEXITCODE
