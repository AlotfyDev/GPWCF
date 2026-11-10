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
$ScriptPath = Join-Path $PSScriptRoot 'prefect_deployment_stage_qualification.py'
& $PythonExecutable $ScriptPath --deploy --work-pool $PoolName
if ($LASTEXITCODE -ne 0) { throw "Stage deployment registration failed with exit code $LASTEXITCODE." }
