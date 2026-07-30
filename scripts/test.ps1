$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Join-Path $PSScriptRoot "..")
python -m pytest -q tests
exit $LASTEXITCODE
