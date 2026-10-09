$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $venvPython = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
    $python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
    & $python -m uvicorn src.app:app --host 127.0.0.1 --port 8002 --no-access-log
} finally {
    Pop-Location
}
