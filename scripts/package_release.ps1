$ErrorActionPreference = 'Stop'
$pttiRoot = Split-Path -Parent $PSScriptRoot
$pttiDist = Join-Path $pttiRoot 'dist'
$pttiRuntime = Join-Path $pttiDist 'PTTI'
$pttiPackage = Join-Path $pttiDist 'PTTI-v0.1.0-Windows'
$pttiArchive = Join-Path $pttiDist 'PTTI-v0.1.0-Windows-x64.zip'
if (-not (Test-Path -LiteralPath (Join-Path $pttiRuntime 'PTTI.exe'))) { throw 'Build PTTI first with build_windows.bat.' }
if (-not (Test-Path -LiteralPath (Join-Path $pttiRuntime '_internal'))) { throw 'Required runtime folder is missing.' }
if ((Test-Path -LiteralPath $pttiPackage) -or (Test-Path -LiteralPath $pttiArchive)) { throw 'Handoff output already exists. Preserve or move it before packaging again.' }
$null = New-Item -ItemType Directory -Path $pttiPackage
Copy-Item -LiteralPath $pttiRuntime -Destination $pttiPackage -Recurse
$null = New-Item -ItemType Directory -Path (Join-Path $pttiPackage 'sample'), (Join-Path $pttiPackage 'docs')
Copy-Item -LiteralPath (Join-Path $pttiRoot 'data/samples/synthetic.csv') -Destination (Join-Path $pttiPackage 'sample/synthetic.csv')
Copy-Item -LiteralPath (Join-Path $pttiRoot 'docs/release/START-HERE.txt') -Destination (Join-Path $pttiPackage 'START-HERE.txt')
foreach ($pttiDoc in @('QUICK-START.md', 'CSV-TEMPLATE.md')) {
    Copy-Item -LiteralPath (Join-Path $pttiRoot "docs/release/$pttiDoc") -Destination (Join-Path $pttiPackage "docs/$pttiDoc")
}
Copy-Item -LiteralPath (Join-Path $pttiRoot 'docs/USER-FEEDBACK.md') -Destination (Join-Path $pttiPackage 'docs/USER-FEEDBACK.md')
Compress-Archive -LiteralPath $pttiPackage -DestinationPath $pttiArchive -CompressionLevel Optimal
$pttiHash = (Get-FileHash -LiteralPath $pttiArchive -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($pttiArchive + '.sha256') -Value "$pttiHash  PTTI-v0.1.0-Windows-x64.zip" -Encoding ASCII
Write-Output $pttiArchive
Write-Output "SHA256: $pttiHash"
