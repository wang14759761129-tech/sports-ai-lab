param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:LOCALAPPDATA 'PTTI-Web-Pro-Installer-Candidate\rc1'
$stage = $target + '.installing'
function Hash-File([string]$File) {
    $stream = [IO.File]::OpenRead($File); $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    $package = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package.json') -Raw | ConvertFrom-Json
    if ($package.contract -ne 'ptti.windows-installer/0.1') { throw 'Unsupported installation package.' }
    if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $stage)) { throw 'Candidate already exists or installation is incomplete. Nothing was overwritten. Use its uninstall entry or inspect the staging directory.' }
    $payload = Join-Path $PSScriptRoot 'payload'
    foreach ($entry in $package.files.PSObject.Properties) {
        $file = [IO.Path]::GetFullPath((Join-Path $payload $entry.Name))
        if (-not $file.StartsWith($payload + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe package path.' }
        if ((Hash-File $file) -ne $entry.Value) { throw ('Package integrity failure: ' + $entry.Name) }
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    foreach ($entry in $package.files.PSObject.Properties) {
        $dest = Join-Path $stage $entry.Name
        New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $payload $entry.Name) -Destination $dest
        if ((Hash-File $dest) -ne $entry.Value) { throw 'Installed copy integrity failure. Staging retained for inspection.' }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package.json') -Destination (Join-Path $stage 'installation-receipt.json')
    Move-Item -LiteralPath $stage -Destination $target
    Write-Output ('Installed candidate: ' + $target + '\Start-PTTI-RC.cmd')
    Write-Output 'No desktop shortcut, registry entry, service or browser was changed. Run Start-PTTI-RC.cmd when ready.'
    if (-not $Quiet) { Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show(('PTTI candidate installed. Open: ' + $target + '\Start-PTTI-RC.cmd'), 'PTTI Installer Candidate') | Out-Null }
} catch {
    if (-not $Quiet) { Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show($_.Exception.Message, 'PTTI installation failed') | Out-Null }
    Write-Error $_; exit 1
}
