param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
function Resolve-Preview($pointerName) {
    $pointer = Get-Content -LiteralPath (Join-Path $root $pointerName) -Raw | ConvertFrom-Json
    $folder = [IO.Path]::GetFullPath((Join-Path $root $pointer.folder))
    $prefix = [IO.Path]::GetFullPath((Join-Path $root 'versions')) + '\'
    if (-not $folder.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid version path' }
    if ($pointer.manifest.channel -ne 'preview') { throw 'Invalid preview channel' }
    $actual = @(Get-ChildItem -LiteralPath $folder -Recurse -File | Where-Object FullName -ne (Join-Path $folder 'manifest.json'))
    if ($actual.Count -ne @($pointer.manifest.files.PSObject.Properties).Count) { throw 'Unexpected package files' }
    foreach ($entry in $pointer.manifest.files.PSObject.Properties) {
        $file = [IO.Path]::GetFullPath((Join-Path $folder $entry.Name))
        if (-not $file.StartsWith($folder + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path' }
        $stream = [IO.File]::OpenRead($file)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $stream.Dispose(); $sha.Dispose() }
        if ($hash -ne $entry.Value) { throw "Invalid package hash: $($entry.Name)" }
    }
    if (-not $pointer.manifest.files.PSObject.Properties[$pointer.manifest.exe]) { throw 'EXE not verified' }
    return (Join-Path $folder $pointer.manifest.exe)
}
try {
    try { $exe = Resolve-Preview 'current-preview.json' }
    catch { if (-not (Test-Path -LiteralPath (Join-Path $root 'previous-preview.json'))) { throw }; $exe = Resolve-Preview 'previous-preview.json' }
    $env:PTTI_DESKTOP_DEPLOY_ROOT = $root
    if ($VerifyOnly) { Write-Output $exe; exit 0 }
    Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe)
} catch {
    if ($VerifyOnly) { Write-Error $_; exit 1 }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('PTTI 启动完整性检查失败。现有录像与数据库未修改，请查看部署日志。', 'PTTI Cinema Launcher') | Out-Null
    exit 1
}
