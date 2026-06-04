# KMA 실외 날씨 스모크 (로컬 .env, KMA_SERVICE_KEY 필요)
# Usage: .\.cursor\scripts\weather-smoke.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

. (Join-Path $PSScriptRoot 'ensure-utf8.ps1')

$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
& $venvPython (Join-Path $PSScriptRoot 'weather-smoke.py')
exit $LASTEXITCODE
