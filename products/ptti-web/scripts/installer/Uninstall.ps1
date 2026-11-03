param([switch]$ConfirmRemoval)
$ErrorActionPreference = 'Stop'
function Hash-File([string]$File) {
    $stream = [IO.File]::OpenRead($File); $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    $expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'PTTI-Web-Pro-Installer-Candidate\rc1'))
    if ($PSScriptRoot -ne $expected) { throw 'Uninstall is allowed only in the dedicated candidate installation directory.' }
    if (-not $ConfirmRemoval) { Add-Type -AssemblyName PresentationFramework; if ([System.Windows.MessageBox]::Show('Remove only this PTTI installer candidate? Unknown files, reports and logs are preserved.', 'PTTI candidate uninstall', 'YesNo') -ne 'Yes') { exit 0 } }
    $receiptPath = Join-Path $expected 'installation-receipt.json'
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    if ($receipt.contract -ne 'ptti.windows-installer/0.1') { throw 'Invalid installation receipt.' }
    $selfNames = @('Uninstall.ps1', 'Uninstall.cmd')
    $verified = @()
    foreach ($entry in $receipt.files.PSObject.Properties) {
        $file = [IO.Path]::GetFullPath((Join-Path $expected $entry.Name))
        if (-not $file.StartsWith($expected + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe receipt path.' }
        if (Test-Path -LiteralPath $file) {
            if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing redirected program file.' }
            if ((Hash-File $file) -ne $entry.Value) { throw ('Changed program file preserved; uninstall stopped: ' + $entry.Name) }
            $verified += $file
        }
    }
    & (Join-Path $expected 'runtime\node.exe') (Join-Path $expected 'app\stop.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Candidate stop failed; files retained.' }
    foreach ($file in $verified) { if ((Split-Path $file -Leaf) -notin $selfNames) { Remove-Item -LiteralPath $file } }
    foreach ($name in $selfNames) { $file = Join-Path $expected $name; if ($verified -contains $file) { Remove-Item -LiteralPath $file } }
    Remove-Item -LiteralPath $receiptPath
    Write-Output 'Candidate program files removed. Logs, unknown files and empty directories were preserved. Stable versions and desktop entry untouched.'
} catch { Write-Error $_; exit 1 }
