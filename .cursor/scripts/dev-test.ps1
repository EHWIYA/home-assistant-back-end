# Install deps (if needed) and run pytest with UTF-8-safe console on Windows.
# Usage: .\.cursor\scripts\dev-test.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot 'ensure-utf8.ps1')

$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
$venvPip = Join-Path $Root '.venv\Scripts\pip.exe'

if (-not (Test-Path $venvPython)) {
    python -m venv .venv
}

& $venvPip install -q -r requirements.txt
& $venvPython -m pytest -q @args
exit $LASTEXITCODE
