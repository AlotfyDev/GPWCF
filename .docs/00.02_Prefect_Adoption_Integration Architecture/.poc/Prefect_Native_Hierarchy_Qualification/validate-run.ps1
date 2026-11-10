param(
    [Parameter(Mandatory = $true)]
    [string]$RunRoot,
    [string]$PythonExecutable = 'C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python executable not found: $PythonExecutable"
}
& $PythonExecutable (Join-Path $PSScriptRoot 'validate_evidence.py') $RunRoot --profile 'local-prefect-server-api-sqlite-single-worker'
exit $LASTEXITCODE
