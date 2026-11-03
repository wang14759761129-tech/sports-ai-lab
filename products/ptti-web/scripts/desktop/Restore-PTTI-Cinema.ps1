param([Parameter(Mandatory=$true)][string]$BackupDirectory)
$ErrorActionPreference = 'Stop'
$meta = Get-Content -LiteralPath (Join-Path $BackupDirectory 'restore-metadata.json') -Raw | ConvertFrom-Json
$desktop = [Environment]::GetFolderPath('Desktop')
$destination = Join-Path $desktop 'PTTI Cinema.lnk'
if ($meta.shortcut -ine $destination) { throw 'Desktop location differs from the recorded backup. Review the metadata before restoring.' }
if (-not (Test-Path -LiteralPath $meta.old_launcher -PathType Leaf)) { throw 'Original R4 launcher is missing.' }
if ((Get-FileHash -LiteralPath $meta.old_launcher).Hash -ne $meta.old_launcher_sha256) { throw 'Original R4 launcher changed. Restore requires manual review.' }
if (Test-Path -LiteralPath $destination) { Copy-Item -LiteralPath $destination -Destination (Join-Path $BackupDirectory 'web-shortcut-before-restore.lnk') -Force }
Copy-Item -LiteralPath (Join-Path $BackupDirectory 'PTTI Cinema.lnk') -Destination $destination -Force
Write-Output ('Restored original R4 shortcut: ' + $destination)
