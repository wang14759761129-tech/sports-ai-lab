$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Goal23.ProcessIdentity.ps1')

function Assert-Case([string]$Name, [scriptblock]$Action) {
    & $Action
    Write-Output ('PASS ' + $Name)
}
function Assert-State($State, [int[]]$Running, [int[]]$Unknown, [bool]$CanLaunch, [string]$Name) {
    $actualRunning = (@($State.RunningPids) | Sort-Object) -join ','
    $actualUnknown = (@($State.UnverifiedPids) | Sort-Object) -join ','
    $expectedRunning = (@($Running) | Sort-Object) -join ','
    $expectedUnknown = (@($Unknown) | Sort-Object) -join ','
    if ($actualRunning -ne $expectedRunning -or $actualUnknown -ne $expectedUnknown -or $State.CanLaunch -ne $CanLaunch) {
        throw ("{0}: running=[{1}] unknown=[{2}] canLaunch={3}; expected running=[{4}] unknown=[{5}] canLaunch={6}" -f $Name,$actualRunning,$actualUnknown,$State.CanLaunch,$expectedRunning,$expectedUnknown,$CanLaunch)
    }
}
function New-Snapshot([int]$Id, [string]$Name, [AllowNull()][string]$Path, [datetime]$Created) {
    [pscustomobject]@{ ProcessId=$Id; Name=$Name; ExecutablePath=$Path; CreationDate=$Created }
}
function Add-Resolved([object]$Snapshot, [string]$Path, [string]$Status='Resolved', [int]$PidOverride=0, [datetime]$StartOverride=[datetime]::MinValue) {
    $id = if ($PidOverride -gt 0) { $PidOverride } else { [int]$Snapshot.ProcessId }
    $start = if ($StartOverride -ne [datetime]::MinValue) { $StartOverride } else { [datetime]$Snapshot.CreationDate }
    $script:processMap[[string]$Snapshot.ProcessId] = @{ Status=$Status; ProcessId=$id; Path=$Path; StartTimeUtcTicks=$start.ToUniversalTime().Ticks; HasExited=$false }
}
function Invoke-State([string]$ExecutablePath, [string]$Expected, [string]$Verified, [object[]]$Snapshot, [scriptblock]$Resolver) {
    Get-Goal23R4ProcessState -ExecutablePath $ExecutablePath -ExpectedSha256 $Expected -VerifiedSha256 $Verified -ProcessSnapshot $Snapshot -ProcessResolver $Resolver -HashProvider $script:hashProvider
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('ptti-goal23-process-id-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $r4 = Join-Path $root 'PTTI-Video-First-R4-Preview.exe'
    $fan = Join-Path $root 'PTTI-Desktop-Fan.exe'
    $otherDir = Join-Path $root 'other'
    New-Item -ItemType Directory -Path $otherDir | Out-Null
    $sameNameOther = Join-Path $otherDir 'PTTI-Video-First-R4-Preview.exe'
    [IO.File]::WriteAllText($r4, 'synthetic-r4-binary')
    [IO.File]::WriteAllText($fan, 'synthetic-fan-binary')
    Copy-Item -LiteralPath $r4 -Destination $sameNameOther
    $hash = (Get-FileHash -LiteralPath $r4 -Algorithm SHA256).Hash.ToLowerInvariant()
    $script:hashProvider = { param([string]$Path) (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() }
    $resolver = { param([int]$Id) return $script:processMap[[string]$Id] }

    Assert-Case 'Fan-only is not R4' {
        $script:processMap = @{}
        $snap = New-Snapshot 101 'PTTI-Desktop-Fan.exe' $fan ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $snap $fan
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @() $true 'Fan-only'
    }
    Assert-Case 'exact R4 path plus current PID and SHA is detected' {
        $script:processMap = @{}
        $snap = New-Snapshot 201 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $snap $r4
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @(201) @() $false 'exact R4'
    }
    Assert-Case 'Fan and R4 together report only R4' {
        $script:processMap = @{}
        $fanSnap = New-Snapshot 301 'PTTI-Desktop-Fan.exe' $fan ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $fanSnap $fan
        $r4Snap = New-Snapshot 302 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $r4Snap $r4
        Assert-State (Invoke-State $r4 $hash $hash @($fanSnap,$r4Snap) $resolver) @(302) @() $false 'Fan plus R4'
    }
    Assert-Case 'same basename and same hash from another path is not R4' {
        $script:processMap = @{}
        $snap = New-Snapshot 401 'PTTI-Video-First-R4-Preview.exe' $sameNameOther ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $snap $sameNameOther
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @() $true 'alternate path'
    }
    Assert-Case 'unreadable exact R4 path fails closed' {
        $script:processMap = @{ '501'=@{Status='Unreadable';ProcessId=501} }
        $snap = New-Snapshot 501 'PTTI-Video-First-R4-Preview.exe' $null ([datetime]::UtcNow.AddSeconds(-1))
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @(501) $false 'unreadable path'
    }
    Assert-Case 'unreadable Fan path does not match the R4 basename' {
        $script:processMap = @{}
        $snap = New-Snapshot 502 'PTTI-Desktop-Fan.exe' $null ([datetime]::UtcNow.AddSeconds(-1))
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @() $true 'unreadable Fan'
    }
    Assert-Case 'exited process snapshot is discarded' {
        $script:processMap = @{ '601'=@{Status='Exited';ProcessId=601} }
        $snap = New-Snapshot 601 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddSeconds(-1))
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @() $true 'exited process'
    }
    Assert-Case 'PID reused by Fan does not reuse stale R4 path' {
        $script:processMap = @{}
        $snap = New-Snapshot 701 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddSeconds(-2)); Add-Resolved $snap $fan 'Resolved' 701 ([datetime]::UtcNow.AddSeconds(-1))
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @() $true 'PID reused'
    }
    Assert-Case 'same-path PID with inconsistent creation time is unknown' {
        $script:processMap = @{}
        $snap = New-Snapshot 801 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddMinutes(-5)); Add-Resolved $snap $r4 'Resolved' 801 ([datetime]::UtcNow.AddSeconds(-1))
        Assert-State (Invoke-State $r4 $hash $hash @($snap) $resolver) @() @(801) $false 'creation time mismatch'
    }
    Assert-Case 'target image hash drift fails closed' {
        $script:processMap = @{}
        $snap = New-Snapshot 901 'PTTI-Video-First-R4-Preview.exe' $r4 ([datetime]::UtcNow.AddSeconds(-1)); Add-Resolved $snap $r4
        $state = Invoke-State $r4 ('0' * 64) $hash @($snap) $resolver
        Assert-State $state @() @() $false 'hash drift'
        if ($state.IdentityVerified -or $state.IdentityFailure -ne 'TARGET_IMAGE_HASH_MISMATCH') { throw 'Hash mismatch did not fail closed.' }
    }
    Assert-Case 'process snapshot failure fails closed' {
        function Get-CimInstance { throw 'synthetic snapshot failure' }
        try {
            $state = Get-Goal23R4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot $null -ProcessResolver $resolver -HashProvider $script:hashProvider
            if ($state.IdentityVerified -or $state.IdentityFailure -ne 'PROCESS_SNAPSHOT_UNAVAILABLE' -or $state.CanLaunch) { throw 'Snapshot failure did not fail closed.' }
        } finally { Remove-Item Function:Get-CimInstance -ErrorAction SilentlyContinue }
    }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
