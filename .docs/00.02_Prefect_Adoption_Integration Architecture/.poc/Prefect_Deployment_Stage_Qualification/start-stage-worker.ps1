param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-deployment',
    [string]$ApiUrl = 'http://127.0.0.1:4210/api',
    [string]$PoolName = 'gpwcf-phase02-stage-qualified-pool',
    [string]$WorkerName = 'gpwcf-stage-process-worker',
    [int]$ConcurrencyLimit = 1
)
$ErrorActionPreference = 'Stop'
if ($ConcurrencyLimit -lt 1) { throw 'Worker concurrency limit must be at least 1.' }
$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_API_URL = $ApiUrl
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$PrefectExecutable = Join-Path (Split-Path -Parent $PythonExecutable) 'prefect.exe'
Write-Host "Starting Process Worker '$WorkerName' for pool '$PoolName' with flow-run limit $ConcurrencyLimit."
Write-Host 'Keep this foreground process running while the Root PoC executes.'
& $PrefectExecutable worker start --pool $PoolName --type process --name $WorkerName --limit $ConcurrencyLimit --no-prompt
exit $LASTEXITCODE
