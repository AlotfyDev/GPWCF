param(
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe',
    [string]$PrefectHome = 'C:\poc\GPWCF\prefect-home-sqlite',
    [string]$ApiUrl = 'http://127.0.0.1:4200/api'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python executable not found: $PythonExecutable"
}

$env:PREFECT_HOME = $PrefectHome
$env:PREFECT_API_URL = $ApiUrl
$env:PREFECT_SERVER_ANALYTICS_ENABLED = 'false'
$env:PREFECT_TELEMETRY_ENABLED = 'false'
$env:PREFECT_LOGGING_LEVEL = 'WARNING'

& $PythonExecutable -c "import sys, prefect; assert sys.version_info[:3] == (3, 15, 1), sys.version; assert prefect.__version__ == '3.9.2', prefect.__version__; print('Python', sys.version.split()[0], '| Prefect', prefect.__version__)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

try {
    $health = Invoke-WebRequest -UseBasicParsing ($ApiUrl.TrimEnd('/') + '/health') -TimeoutSec 10
    if ($health.StatusCode -ne 200) { throw "Prefect API health returned $($health.StatusCode)" }
} catch {
    throw "Prefect API server is not reachable at $ApiUrl. Start start-local-prefect-server.ps1 in a separate terminal. $($_.Exception.Message)"
}

& $PythonExecutable (Join-Path $PSScriptRoot 'prefect_native_hierarchy.py') --evidence-root (Join-Path $PSScriptRoot 'evidence')
exit $LASTEXITCODE
