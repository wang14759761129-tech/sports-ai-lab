param(
    [string]$InstallDirectory = (Join-Path $env:USERPROFILE 'PTTI\Web-Pro'),
    [switch]$Activate
)
$ErrorActionPreference = 'Stop'
$install = [IO.Path]::GetFullPath($InstallDirectory)
$userRoot = [IO.Path]::GetFullPath($env:USERPROFILE) + '\'
if (-not $install.StartsWith($userRoot, [StringComparison]::OrdinalIgnoreCase) -or $install -match '\\AppData\\|\\\.codex\\|\\OneDrive\\') { throw 'Choose a dedicated stable user directory outside AppData, Codex and OneDrive.' }
if (Test-Path -LiteralPath $install) { throw 'Candidate directory already exists. Review it before updating; no files were overwritten.' }
$desktop = [Environment]::GetFolderPath('Desktop')
$desktopLink = Join-Path $desktop 'PTTI Cinema.lnk'
if (-not (Test-Path -LiteralPath $desktopLink)) { throw 'Existing desktop entry is missing; installation will not create a competing entry.' }
$shell = New-Object -ComObject WScript.Shell
$oldLink = $shell.CreateShortcut($desktopLink)
$oldLinkHash = (Get-FileHash -LiteralPath $desktopLink).Hash
$match = [regex]::Match($oldLink.Arguments, '(?i)-File\s+"([^"]+)"')
if (-not $match.Success) { throw 'Cannot resolve the existing launcher from the desktop shortcut.' }
$oldLauncher = $match.Groups[1].Value
$oldRoot = Split-Path -Parent $oldLauncher
$configPath = Join-Path $oldRoot 'web-pro.json'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
if ($config.project -ine $project) { throw 'Existing configuration points to a different Web worktree.' }
if (-not (Test-Path -LiteralPath $config.playback_core_source -PathType Leaf)) { throw 'Configured Playback Core is unavailable.' }
$iconParts = $oldLink.IconLocation -split ',(?=-?\d+$)'
$icon = $iconParts[0]
if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) { throw 'Existing application icon cannot be backed up.' }

New-Item -ItemType Directory -Path $install | Out-Null
$backup = Join-Path $install ('backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -LiteralPath $desktopLink -Destination (Join-Path $backup 'PTTI Cinema.lnk')
Copy-Item -LiteralPath $oldLauncher -Destination (Join-Path $backup 'old-web-launcher.ps1')
Copy-Item -LiteralPath $configPath -Destination (Join-Path $backup 'old-web-pro.json')
Copy-Item -LiteralPath (Join-Path $oldRoot 'Start-PTTI-Web-Service.ps1') -Destination (Join-Path $backup 'old-web-service.ps1')
Copy-Item -LiteralPath $icon -Destination (Join-Path $install 'ptti-cinema.ico')
foreach ($name in @('Start-PTTI-Web-Pro.ps1','Start-PTTI-Web-Service.ps1','Restore-PTTI-Cinema.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $install $name)
}
# Preserve the exact existing service configuration; no global environment changes.
Copy-Item -LiteralPath $configPath -Destination (Join-Path $install 'web-pro.json')
$r4Backup = Join-Path $oldRoot 'backups\20261015-165114'
if (-not (Test-Path -LiteralPath (Join-Path $r4Backup 'restore-metadata.json'))) { throw 'Existing R4 recovery metadata is missing. Original desktop link is unchanged.' }
$r4Copy = Join-Path $backup 'r4-origin'
New-Item -ItemType Directory -Path $r4Copy | Out-Null
foreach ($name in @('PTTI Cinema.lnk','R4-launcher.ps1','R4-launcher-standard-AppData.ps1','current-preview.json','restore-metadata.json')) {
    Copy-Item -LiteralPath (Join-Path $r4Backup $name) -Destination (Join-Path $r4Copy $name)
}
$receipt = [ordered]@{ install_directory=$install; desktop_shortcut=$desktopLink; backup_directory=$backup; prior_shortcut_sha256=$oldLinkHash; prior_launcher=$oldLauncher; state='CANDIDATE'; service_config_sha256=(Get-FileHash -LiteralPath $configPath).Hash; cold_start_at_new_location='NOT_TESTED_EXISTING_SERVICE_PRESERVED' }
$receiptPath = Join-Path $install 'installation-receipt.json'
function Save-Receipt { [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($true))) }
Save-Receipt
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$candidateLauncher = Join-Path $install 'Start-PTTI-Web-Pro.ps1'
& $powershell -NoProfile -ExecutionPolicy Bypass -File $candidateLauncher -NoBrowser
if ($LASTEXITCODE -ne 0) { throw 'Candidate service validation failed. Original desktop link is unchanged.' }
$candidate = $shell.CreateShortcut((Join-Path $install 'PTTI Cinema.lnk'))
$candidate.TargetPath = $powershell
$candidate.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $candidateLauncher + '"'
$candidate.WorkingDirectory = $install
$candidate.IconLocation = (Join-Path $install 'ptti-cinema.ico') + ',0'
$candidate.Description = 'PTTI Cinema - local Web Pro'
$candidate.Save()
$receipt.state = 'CANDIDATE_SERVICE_VERIFIED'
Save-Receipt
if ($Activate) {
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    if ($ram -lt 2.5) { throw 'Candidate is ready, but browser validation is BLOCKED below 2.5 GiB. Original desktop link is unchanged.' }
    $priorLog = (Get-Item -LiteralPath (Join-Path $install 'launcher.log')).Length
    Start-Process -FilePath (Join-Path $install 'PTTI Cinema.lnk')
    $deadline = (Get-Date).AddSeconds(12)
    $opened = $false
    do {
        Start-Sleep -Milliseconds 400
        $logFile = Join-Path $install 'launcher.log'
        if ((Get-Item -LiteralPath $logFile).Length -gt $priorLog) { $opened = (Get-Content -LiteralPath $logFile -Tail 1) -like '*default-browser-open-request http://127.0.0.1:4174/*' }
    } while (-not $opened -and (Get-Date) -lt $deadline)
    if (-not $opened) { throw 'Candidate browser invocation was not confirmed. Original desktop link is unchanged.' }
    if ((Get-FileHash -LiteralPath $desktopLink).Hash -ne $oldLinkHash) { throw 'Desktop entry changed during validation; refusing to overwrite it.' }
    Copy-Item -LiteralPath (Join-Path $install 'PTTI Cinema.lnk') -Destination $desktopLink -Force
    $receipt.state = 'ACTIVATED_AFTER_CANDIDATE_SHELL_VALIDATION'
    $receipt.activated_at = (Get-Date -Format o)
    Save-Receipt
}
Write-Output ($receipt | ConvertTo-Json -Depth 5)
