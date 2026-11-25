<#
  One-command LEGACY v1 demo start (Windows PowerShell). Docker-free.
  The legacy runtime lives in legacy\python (relocated from backend\). The v2 API is separate:
  use tools\dev_api.ps1 (port 8100, its own database and config).

    .\run_demo.ps1              # uses legacy\python\.env (Neon if DATABASE_URL is set, else SQLite)
    .\run_demo.ps1 -Offline     # venue wifi dead: SQLite + mock BMKG
    .\run_demo.ps1 -Live        # real BMKG
    .\run_demo.ps1 -Reset       # fresh demo data before starting
    .\run_demo.ps1 -CheckOnly   # resolve paths/interpreter and print them, start nothing
    .\run_demo.ps1 -NoBrowser   # do not open a browser tab (scripted smoke tests)
#>
param(
    [switch]$Offline,
    [switch]$Live,
    [switch]$Reset,
    [switch]$CheckOnly,
    [switch]$NoBrowser,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
# The project path contains spaces and an apostrophe: always quote, always use -LiteralPath and $PSScriptRoot.
$backend = Join-Path (Join-Path $PSScriptRoot "legacy") "python"
if (-not (Test-Path -LiteralPath (Join-Path $backend "app\main.py"))) {
    throw "Legacy backend not found at '$backend'. Expected legacy\python\app\main.py (see docs\runbooks\local-environments.md)."
}
Set-Location -LiteralPath $backend

$py = Join-Path $backend ".venv\Scripts\python.exe"
if ($CheckOnly) {
    Write-Host "repo:    $PSScriptRoot"
    Write-Host "backend: $backend"
    Write-Host "python:  $py (exists: $(Test-Path -LiteralPath $py))"
    Write-Host "web:     $(Join-Path $PSScriptRoot 'legacy\web\dist') (exists: $(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'legacy\web\dist')))"
    exit 0
}
if (-not (Test-Path -LiteralPath $py)) {
    # Recreate rather than copy: virtual environments are machine-local and never tracked.
    Write-Host "Creating legacy virtual environment in legacy\python\.venv ..."
    py -3.11 -m venv (Join-Path $backend ".venv")
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet -r (Join-Path $backend "requirements-dev.txt")
}

if ($Offline) {
    $env:DATABASE_URL = "sqlite:///demo.db"
    $env:WEATHER_MODE = "mock"
} elseif ($Live) {
    $env:WEATHER_MODE = "live"
}

$seedArgs = @()
if ($Reset) { $seedArgs += "--reset" }
& $py seed.py @seedArgs   # also pre-warms Neon (first query wakes a scaled-to-zero compute)
if ($LASTEXITCODE -ne 0) { throw "seed failed - check DATABASE_URL in legacy\python\.env, or use -Offline" }

if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port/" }
& $py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
