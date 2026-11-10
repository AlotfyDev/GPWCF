param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-deployment',
    [string]$ApiUrl = 'http://127.0.0.1:4210/api',
    [string]$PoolName = 'gpwcf-phase02-stage-qualified-pool'
)
$ErrorActionPreference = 'Stop'
$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_API_URL = $ApiUrl
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$PrefectExecutable = Join-Path (Split-Path -Parent $PythonExecutable) 'prefect.exe'
$health = Invoke-WebRequest -UseBasicParsing ($ApiUrl.TrimEnd('/') + '/health') -TimeoutSec 10
if ($health.StatusCode -ne 200) { throw "Prefect API health returned $($health.StatusCode)" }
& $PrefectExecutable work-pool create --type process $PoolName
if ($LASTEXITCODE -ne 0) { throw "Could not create Process work pool '$PoolName'." }
Write-Host "Created Process work pool: $PoolName"
