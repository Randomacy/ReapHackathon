param(
    [ValidateSet('simulator', 'live')]
    [string]$Mode = 'simulator'
)

$ErrorActionPreference = 'Stop'
$env:BCI_MODE = $Mode
if (-not $env:BCI_EVENT_TOKEN) {
    Write-Warning 'BCI_EVENT_TOKEN is unset. The API will run, but events will not reach the agent.'
}
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $venvPython = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
    $python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
    & $python -m uvicorn src.app:app --host 127.0.0.1 --port 8001 --no-access-log
} finally {
    Pop-Location
}
