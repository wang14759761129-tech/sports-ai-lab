param([Parameter(Mandatory=$true)][string]$ConfigPath)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
Set-Location -LiteralPath $config.project
$env:PTTI_PLAYBACK_CORE_SOURCE = $config.playback_core_source
$npm = Join-Path (Split-Path -Parent $config.node) 'npm.cmd'
# Detached launcher worker: the actual package command remains the source of truth.
& $npm run dev:review *> (Join-Path $PSScriptRoot 'service.log')
exit $LASTEXITCODE
