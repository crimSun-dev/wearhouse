<#
  Start the Wearhouse v2 API for local development (port 8100). Separate from the legacy demo (port 8000).

    .\tools\dev_api.ps1                 # uses WEARHOUSE_* variables already set in this shell
    .\tools\dev_api.ps1 -Migrate        # run the explicit migration first (WEARHOUSE_MIGRATION_DATABASE_URL)
    .\tools\dev_api.ps1 -CheckOnly      # config + read-only startup checks, start nothing

  Startup never migrates or seeds. Required variables are listed in apps\api\.env.example.
  Paths contain spaces and an apostrophe: everything below is quoted / -LiteralPath.
#>
param(
    [switch]$Migrate,
    [switch]$CheckOnly,
    [int]$Port = 8100
)
$ErrorActionPreference = "Stop"
$api = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) "apps") "api"
$py = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Host "Creating v2 virtual environment in apps\api\.venv ..."
    py -3.11 -m venv (Join-Path $api ".venv")
    & $py -m pip install --quiet -r (Join-Path $api "requirements-dev.lock")
    & $py -m pip install --quiet --no-deps -e $api
}
if (-not $env:WEARHOUSE_ENV) { $env:WEARHOUSE_ENV = "development" }
if ($Migrate) {
    & $py -m wearhouse.bootstrap.cli migrate --environment $env:WEARHOUSE_ENV
    if ($LASTEXITCODE -ne 0) { throw "migration failed" }
}
& $py -m wearhouse.bootstrap.cli check
if ($LASTEXITCODE -ne 0) { throw "v2 is not ready (see message above). Startup never migrates: use -Migrate." }
if ($CheckOnly) { exit 0 }
& $py -m uvicorn wearhouse.bootstrap.asgi:app --host 127.0.0.1 --port $Port
