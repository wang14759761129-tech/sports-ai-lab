$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\native-bridge\Start-PTTI.candidate.ps1'
$text = Get-Content -LiteralPath $source -Raw -Encoding UTF8
$startMarker = '# BEGIN PTTI_NATIVE_POINTER_LEASE_V1'
$endMarker = '# END PTTI_NATIVE_POINTER_LEASE_V1'
$start = $text.IndexOf($startMarker, [StringComparison]::Ordinal)
$end = $text.IndexOf($endMarker, $start, [StringComparison]::Ordinal)
if ($start -lt 0 -or $end -le $start) { throw 'Candidate pointer lease markers are missing or malformed.' }
Invoke-Expression $text.Substring($start, $end + $endMarker.Length - $start)

$root = Join-Path ([IO.Path]::GetTempPath()) ('ptti-pointer-lease-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
$lease = $null
try {
    $current = Join-Path $root 'current-preview.json'
    $previous = Join-Path $root 'previous-preview.json'
    [IO.File]::WriteAllText($current, '{"pointer":"current"}')
    [IO.File]::WriteAllText($previous, '{"pointer":"previous"}')
    $lease = Open-NativePointerLease $root
    if ($lease.Count -ne 2) { throw ('Expected two pointer leases; got ' + $lease.Count) }
    $writeBlocked = $false
    try {
        $writer = [IO.File]::Open($current, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        $writer.Dispose()
    } catch [IO.IOException] { $writeBlocked = $true }
    if (-not $writeBlocked) { throw 'An update could write a pinned pointer while launch identity was in use.' }
    $moveBlocked = $false
    try { [IO.File]::Move($current, ($current + '.moved')) } catch [IO.IOException] { $moveBlocked = $true }
    if (-not $moveBlocked) { throw 'An update could replace a pinned pointer while launch identity was in use.' }
    Write-Output 'PASS current and previous pointers are pinned against write and replacement'
} finally {
    if ($lease) { foreach ($item in $lease) { $item.Stream.Dispose() } }
    $writer = [IO.File]::Open($current, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
    $writer.Dispose()
    [IO.File]::Move($current, ($current + '.moved'))
    [IO.File]::Move(($current + '.moved'), $current)
    Remove-Item -LiteralPath $root -Recurse -Force
}
Write-Output 'PASS pointer files become writable after lease release'
