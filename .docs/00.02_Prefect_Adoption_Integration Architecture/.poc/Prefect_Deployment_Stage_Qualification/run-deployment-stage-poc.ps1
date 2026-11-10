param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-deployment',
    [string]$ApiUrl = 'http://127.0.0.1:4210/api',
    [int]$Runs = 5,
    [double]$StageDelaySeconds = 2.0
)
$ErrorActionPreference = 'Stop'
$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_API_URL = $ApiUrl
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$health = Invoke-WebRequest -UseBasicParsing ($ApiUrl.TrimEnd('/') + '/health') -TimeoutSec 10
if ($health.StatusCode -ne 200) { throw "Prefect API health returned $($health.StatusCode)" }
$ScriptPath = Join-Path $PSScriptRoot 'prefect_deployment_stage_qualification.py'
& $PythonExecutable $ScriptPath --runs $Runs --stage-delay-seconds $StageDelaySeconds --evidence-root (Join-Path $PSScriptRoot 'evidence')
if ($LASTEXITCODE -ne 0) { throw "Deployment qualification failed with exit code $LASTEXITCODE." }
