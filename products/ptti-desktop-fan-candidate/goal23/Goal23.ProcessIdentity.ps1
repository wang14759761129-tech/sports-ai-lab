# Isolated GOAL23 process-identity helper. Not imported by or written into Start-PTTI.ps1.
function Get-Goal23R4ProcessState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$ExecutablePath,
        [Parameter(Mandatory=$true)][string]$ExpectedSha256,
        [Parameter(Mandatory=$true)][string]$VerifiedSha256,
        [object[]]$ProcessSnapshot,
        [scriptblock]$ProcessResolver,
        [scriptblock]$HashProvider
    )

    $target = [IO.Path]::GetFullPath($ExecutablePath)
    $actualHash = $VerifiedSha256.ToLowerInvariant()
    if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$' -or
        $actualHash -notmatch '^[0-9a-f]{64}$' -or
        -not [string]::Equals($actualHash, $ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject]@{ IdentityVerified=$false; IdentityFailure='TARGET_IMAGE_HASH_MISMATCH'; ActualSha256=$actualHash; RunningPids=@(); UnverifiedPids=@(); CanLaunch=$false }
    }

    if (-not $HashProvider) {
        $HashProvider = { param([string]$Path) (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() }
    }
    try {
        $diskHash = (& $HashProvider $target).ToLowerInvariant()
    } catch {
        return [pscustomobject]@{ IdentityVerified=$false; IdentityFailure='TARGET_IMAGE_UNREADABLE'; ActualSha256=$null; RunningPids=@(); UnverifiedPids=@(); CanLaunch=$false }
    }
    if (-not [string]::Equals($diskHash, $ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject]@{ IdentityVerified=$false; IdentityFailure='TARGET_IMAGE_HASH_MISMATCH'; ActualSha256=$diskHash; RunningPids=@(); UnverifiedPids=@(); CanLaunch=$false }
    }

    if ($null -eq $ProcessSnapshot) {
        try { $ProcessSnapshot = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop) }
        catch { return [pscustomobject]@{ IdentityVerified=$false; IdentityFailure='PROCESS_SNAPSHOT_UNAVAILABLE'; ActualSha256=$diskHash; RunningPids=@(); UnverifiedPids=@(); CanLaunch=$false } }
    }
    if (-not $ProcessResolver) {
        $ProcessResolver = {
            param([int]$ProcessId)
            $process = $null
            try {
                $process = [Diagnostics.Process]::GetProcessById($ProcessId)
                if ($process.HasExited) { return [pscustomobject]@{ Status='Exited'; ProcessId=$ProcessId } }
                $path = [IO.Path]::GetFullPath($process.MainModule.FileName)
                $startTicks = $process.StartTime.ToUniversalTime().Ticks
                if ($process.HasExited) { return [pscustomobject]@{ Status='Exited'; ProcessId=$ProcessId } }
                return [pscustomobject]@{ Status='Resolved'; ProcessId=$process.Id; Path=$path; StartTimeUtcTicks=$startTicks; HasExited=$false }
            } catch [ArgumentException] {
                return [pscustomobject]@{ Status='Exited'; ProcessId=$ProcessId }
            } catch {
                return [pscustomobject]@{ Status='Unreadable'; ProcessId=$ProcessId }
            } finally { if ($process) { $process.Dispose() } }
        }
    }

    $running = New-Object 'System.Collections.Generic.List[int]'
    $unverified = New-Object 'System.Collections.Generic.List[int]'
    $seen = @{}
    $targetName = [IO.Path]::GetFileName($target)
    foreach ($entry in @($ProcessSnapshot)) {
        try { $id = [int]$entry.ProcessId } catch { continue }
        if ($id -le 0 -or $seen.ContainsKey([string]$id)) { continue }
        $seen[[string]$id] = $true
        $snapshotPath = [string]$entry.ExecutablePath
        if (-not $snapshotPath) {
            if ([string]::Equals([string]$entry.Name, $targetName, [StringComparison]::OrdinalIgnoreCase)) { $unverified.Add($id) }
            continue
        }
        try { $snapshotFull = [IO.Path]::GetFullPath($snapshotPath) }
        catch {
            if ([string]::Equals([IO.Path]::GetFileName($snapshotPath), $targetName, [StringComparison]::OrdinalIgnoreCase)) { $unverified.Add($id) }
            continue
        }
        # A matching basename or PTTI prefix is never sufficient. Require this exact full path.
        if (-not [string]::Equals($snapshotFull, $target, [StringComparison]::OrdinalIgnoreCase)) { continue }

        $current = $null
        try { $current = & $ProcessResolver $id } catch { $current = $null }
        if (-not $current) { $unverified.Add($id); continue }
        if ([string]$current.Status -eq 'Exited') { continue }
        if ([string]$current.Status -ne 'Resolved') { $unverified.Add($id); continue }
        try {
            $currentId = [int]$current.ProcessId
            $currentPath = [IO.Path]::GetFullPath([string]$current.Path)
            $startTicks = [long]$current.StartTimeUtcTicks
            $hasExited = [bool]$current.HasExited
        } catch { $unverified.Add($id); continue }
        if ($hasExited) { continue }
        # PID reuse to another path is discarded; inaccessible or inconsistent identity fails closed.
        if ($currentId -ne $id -or $startTicks -le 0) { $unverified.Add($id); continue }
        if (-not [string]::Equals($currentPath, $target, [StringComparison]::OrdinalIgnoreCase)) { continue }
        if ($entry.CreationDate) {
            try {
                $snapshotTicks = ([datetime]$entry.CreationDate).ToUniversalTime().Ticks
                if ([Math]::Abs($snapshotTicks - $startTicks) -gt [TimeSpan]::FromSeconds(2).Ticks) { $unverified.Add($id); continue }
            } catch { $unverified.Add($id); continue }
        } else { $unverified.Add($id); continue }
        try { $liveHash = (& $HashProvider $currentPath).ToLowerInvariant() }
        catch { $unverified.Add($id); continue }
        if ([string]::Equals($liveHash, $ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) { $running.Add($id) }
        else { $unverified.Add($id) }
    }

    $runningPids = @($running.ToArray())
    $unverifiedPids = @($unverified.ToArray())
    return [pscustomobject]@{
        IdentityVerified=$true; IdentityFailure=$null; ActualSha256=$diskHash
        RunningPids=$runningPids; UnverifiedPids=$unverifiedPids
        CanLaunch=($runningPids.Count -eq 0 -and $unverifiedPids.Count -eq 0)
    }
}
