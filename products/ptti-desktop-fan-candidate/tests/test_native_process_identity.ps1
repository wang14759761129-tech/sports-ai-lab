$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\native-bridge\Start-PTTI.candidate.ps1'
$text = Get-Content -LiteralPath $source -Raw -Encoding UTF8
$startMarker = '# BEGIN PTTI_NATIVE_R4_PROCESS_IDENTITY_V1'
$endMarker = '# END PTTI_NATIVE_R4_PROCESS_IDENTITY_V1'
if (-not $text.Contains($startMarker) -or -not $text.Contains($endMarker)) {
    throw 'Candidate selector does not expose the process identity helper under test.'
}
$start = $text.IndexOf($startMarker, [StringComparison]::Ordinal)
$end = $text.IndexOf($endMarker, $start, [StringComparison]::Ordinal)
if ($end -le $start) { throw 'Candidate process identity helper markers are malformed.' }
function Hash-File([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
Invoke-Expression $text.Substring($start, $end + $endMarker.Length - $start)

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
function New-Snapshot([int]$Id, [string]$Name, [AllowNull()][string]$Path) {
    [pscustomobject]@{ ProcessId=$Id; Name=$Name; ExecutablePath=$Path; CreationDate=[datetime]::UtcNow }
}
$root = Join-Path ([IO.Path]::GetTempPath()) ('ptti-process-id-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $r4 = Join-Path $root 'PTTI-Video-First-R4-Preview.exe'
    $fan = Join-Path $root 'PTTI-Desktop-Fan.exe'
    $impostorDir = Join-Path $root 'other'
    New-Item -ItemType Directory -Path $impostorDir | Out-Null
    $impostor = Join-Path $impostorDir 'PTTI-Video-First-R4-Preview.exe'
    [IO.File]::WriteAllText($r4, 'verified-r4-test-image')
    [IO.File]::WriteAllText($fan, 'fan-test-image')
    [IO.File]::WriteAllText($impostor, 'different-image')
    $hash = (Get-FileHash -LiteralPath $r4 -Algorithm SHA256).Hash.ToLowerInvariant()
    $map = @{}
    $resolver = { param([int]$Id) return $script:processMap[[string]$Id] }

    Assert-Case 'Fan-only is not R4' {
        $script:processMap = @{ '101'=@{Status='Resolved';ProcessId=101;Path=$fan;StartTimeUtcTicks=10} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 101 'PTTI-Desktop-Fan.exe' $fan)) -ProcessResolver $resolver
        Assert-State $state @() @() $true 'Fan-only'
    }
    Assert-Case 'exact R4 path and live PID is detected' {
        $script:processMap = @{ '201'=@{Status='Resolved';ProcessId=201;Path=$r4;StartTimeUtcTicks=20} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 201 'PTTI-Video-First-R4-Preview.exe' $r4)) -ProcessResolver $resolver
        Assert-State $state @(201) @() $false 'exact R4'
    }
    Assert-Case 'Fan and R4 together only reports R4' {
        $script:processMap = @{ '301'=@{Status='Resolved';ProcessId=301;Path=$fan;StartTimeUtcTicks=30}; '302'=@{Status='Resolved';ProcessId=302;Path=$r4;StartTimeUtcTicks=31} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 301 'PTTI-Desktop-Fan.exe' $fan),(New-Snapshot 302 'PTTI-Video-First-R4-Preview.exe' $r4)) -ProcessResolver $resolver
        Assert-State $state @(302) @() $false 'Fan plus R4'
    }
    Assert-Case 'same executable name from a different path is not R4' {
        $script:processMap = @{ '401'=@{Status='Resolved';ProcessId=401;Path=$impostor;StartTimeUtcTicks=40} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 401 'PTTI-Video-First-R4-Preview.exe' $impostor)) -ProcessResolver $resolver
        Assert-State $state @() @() $true 'same name different path'
    }
    Assert-Case 'unreadable exact-R4 path fails closed as unverified' {
        $script:processMap = @{ '501'=@{Status='Unreadable';ProcessId=501} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 501 'PTTI-Video-First-R4-Preview.exe' $null)) -ProcessResolver $resolver
        Assert-State $state @() @(501) $false 'path unreadable'
    }
    Assert-Case 'unreadable Fan path does not become an R4 match' {
        $script:processMap = @{ '502'=@{Status='Unreadable';ProcessId=502} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 502 'PTTI-Desktop-Fan.exe' $null)) -ProcessResolver $resolver
        Assert-State $state @() @() $true 'unreadable Fan path'
    }
    Assert-Case 'exited process snapshot is discarded' {
        $script:processMap = @{ '601'=@{Status='Exited';ProcessId=601} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 601 'PTTI-Video-First-R4-Preview.exe' $r4)) -ProcessResolver $resolver
        Assert-State $state @() @() $true 'process exited'
    }
    Assert-Case 'reused PID resolves current Fan path, not stale R4 snapshot' {
        $script:processMap = @{ '701'=@{Status='Resolved';ProcessId=701;Path=$fan;StartTimeUtcTicks=999} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 701 'PTTI-Video-First-R4-Preview.exe' $r4)) -ProcessResolver $resolver
        Assert-State $state @() @() $true 'PID reused by Fan'
    }
    Assert-Case 'target image hash drift fails closed' {
        $script:processMap = @{}
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 ('0' * 64) -VerifiedSha256 $hash -ProcessSnapshot @() -ProcessResolver $resolver
        Assert-State $state @() @() $false 'target hash drift'
        if ($state.IdentityVerified -or $state.IdentityFailure -ne 'TARGET_IMAGE_HASH_MISMATCH') { throw 'Target hash mismatch did not fail closed.' }
    }
    Assert-Case 'same verified image from an alternate path is still recognized as R4' {
        $alternateDir = Join-Path $root 'alternate'
        New-Item -ItemType Directory -Path $alternateDir | Out-Null
        $alternate = Join-Path $alternateDir 'PTTI-Video-First-R4-Preview.exe'
        Copy-Item -LiteralPath $r4 -Destination $alternate
        $script:processMap = @{ '801'=@{Status='Resolved';ProcessId=801;Path=$alternate;StartTimeUtcTicks=80} }
        $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessSnapshot @((New-Snapshot 801 'PTTI-Video-First-R4-Preview.exe' $alternate)) -ProcessResolver $resolver
        Assert-State $state @(801) @() $false 'same hash alternate path'
    }
    Assert-Case 'process snapshot query failure fails closed' {
        function Get-CimInstance { throw 'simulated snapshot failure' }
        try {
            $state = Get-NativeR4ProcessState -ExecutablePath $r4 -ExpectedSha256 $hash -VerifiedSha256 $hash -ProcessResolver $resolver
            if ($state.IdentityVerified -or $state.IdentityFailure -ne 'PROCESS_SNAPSHOT_UNAVAILABLE' -or $state.CanLaunch) { throw 'Snapshot failure did not fail closed.' }
        } finally { Remove-Item Function:Get-CimInstance -ErrorAction SilentlyContinue }
    }} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
