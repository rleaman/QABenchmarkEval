$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH = "$PWD\src;$env:PYTHONPATH"
$config = if ($args.Count -gt 0) { $args[0] } else { "configs/config.yaml" }
python "$PWD\src\main.py" update $config
exit $LASTEXITCODE
