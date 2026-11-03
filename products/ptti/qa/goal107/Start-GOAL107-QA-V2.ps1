param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'

$expectedCommit = '3efe29b564ac4ce7c55cbef4b8586d8365138724'
$expectedExeHash = 'c02f7d3d9980ebe4eabf07e0eb8393cbbbca99b607cc50a5cb82b8dc23589262'
$expectedPolicyHash = 'df9dfe246ed48640bf637ff65992acf1ca93a885becee3e0b231e2279938ec8a'
$expectedVersion = '0.6.1-R4'
$budgetMiB = 1024
$candidateRoot = '<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL107\R4-0.6.1-3efe29b\video-first-r4-3efe29b564-20261025T025207Z'
$runtimeRoot = 'C:\PTTI-Worktrees\goal99-r4-cinema-evolution\products\ptti'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$policy = Join-Path $runtimeRoot 'scripts\resource_policy_v2.py'
$exe = Join-Path $candidateRoot 'dist\PTTI-Video-First-R4-Preview\PTTI-Video-First-R4-Preview.exe'
$buildInfoPath = Join-Path $candidateRoot 'build-info.json'

function Stop-Safe([string]$Message, [int]$Code = 1) {
    Write-Host "PTTI GOAL107 QA V2: $Message" -ForegroundColor Red
    exit $Code
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}

function Test-ReparsePoint([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    return (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Test-UnderRoot([string]$Path, [string]$Root) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    return $fullPath.StartsWith(($fullRoot + '\'), [StringComparison]::OrdinalIgnoreCase)
}

try {
    if (-not [IO.File]::Exists($exe)) { Stop-Safe 'Candidate EXE is missing.' 1 }
    if (-not [IO.File]::Exists($buildInfoPath)) { Stop-Safe 'Candidate release identity is missing.' 1 }
    if (-not [IO.File]::Exists($python)) { Stop-Safe 'Pinned PTTI QA Python runtime is missing.' 1 }
    if (-not [IO.File]::Exists($policy)) { Stop-Safe 'Resource Policy V2 module is missing.' 1 }

    if ((Get-Sha256 $exe) -ne $expectedExeHash) { Stop-Safe 'Candidate EXE SHA-256 mismatch.' 4 }
    if ((Get-Sha256 $policy) -ne $expectedPolicyHash) { Stop-Safe 'Resource Policy V2 SHA-256 mismatch.' 4 }
    $release = Get-Content -LiteralPath $buildInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($release.commit -ne $expectedCommit -or $release.version -ne $expectedVersion -or $release.source_tree_dirty -ne $false) {
        Stop-Safe 'Candidate version identity mismatch.' 4
    }

    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if ([string]::IsNullOrWhiteSpace($tempBase) -or -not [IO.Directory]::Exists($tempBase)) { Stop-Safe 'Windows temp root is unavailable.' 1 }
    $qaRoot = [IO.Path]::GetFullPath((Join-Path $tempBase 'PTTI-GOAL107-QA-3efe29b564'))
    if (-not (Test-UnderRoot $qaRoot $tempBase)) { Stop-Safe 'QA root is outside Windows temp.' 3 }
    $dataRoot = Join-Path $qaRoot 'data'
    $db = [IO.Path]::GetFullPath((Join-Path $dataRoot 'matches.db'))
    $qaLocal = [IO.Path]::GetFullPath((Join-Path $qaRoot 'localappdata'))
    $webview = [IO.Path]::GetFullPath((Join-Path $qaRoot 'webview2-profile'))
    $research = [IO.Path]::GetFullPath((Join-Path $qaRoot 'research'))
    $pttiDbValue = [IO.Path]::GetFullPath($db)
    $previewQaDbValue = [IO.Path]::GetFullPath($db)
    $marker = Join-Path $qaRoot 'qa-identity.json'
    $monitorLog = Join-Path $qaRoot 'resource-policy-v2.jsonl'

    $originalLocal = [string]$env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($originalLocal)) { Stop-Safe 'Original LOCALAPPDATA is unavailable.' 3 }
    $originalLocal = [IO.Path]::GetFullPath($originalLocal)
    $liveDb = [IO.Path]::GetFullPath((Join-Path $originalLocal 'PTTI\matches.db'))
    $devDb = [IO.Path]::GetFullPath((Join-Path $originalLocal 'PTTI-Dev\matches.db'))
    if ([string]::Equals($db, $liveDb, [StringComparison]::OrdinalIgnoreCase) -or [string]::Equals($db, $devDb, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Safe 'Resolved QA database collides with a user database path.' 3
    }
    if (-not (Test-UnderRoot $qaLocal $qaRoot) -or -not (Test-UnderRoot $webview $qaRoot) -or -not (Test-UnderRoot $research $qaRoot)) {
        Stop-Safe 'An isolation directory resolves outside the QA root.' 3
    }
    if (-not [string]::Equals($pttiDbValue, $previewQaDbValue, [StringComparison]::OrdinalIgnoreCase)) { Stop-Safe 'PTTI_DB and PTTI_PREVIEW_QA_DB do not resolve to the same database.' 3 }

    foreach ($path in @($qaRoot, $dataRoot, $qaLocal, $webview, $research, $db, $marker)) {
        if (Test-ReparsePoint $path) { Stop-Safe ('A QA path is a reparse point: ' + $path) 3 }
    }
    if ([IO.Directory]::Exists($qaRoot)) {
        $existingMarker = Get-Item -LiteralPath $qaRoot -Force
        if (-not [IO.File]::Exists($marker)) { Stop-Safe 'Existing QA root has no identity marker; unknown data is preserved.' 3 }
        $oldIdentity = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($oldIdentity.commit -ne $expectedCommit -or $oldIdentity.exe_sha256 -ne $expectedExeHash -or $oldIdentity.database -ne $db) {
            Stop-Safe 'Existing QA identity differs; no QA data was reused.' 3
        }
    }

    Write-Host "Resolved QA DB: $db"
    Write-Host "PTTI_DB: $pttiDbValue"
    Write-Host "PTTI_PREVIEW_QA_DB: $previewQaDbValue"
    Write-Host "QA LOCALAPPDATA: $qaLocal"
    Write-Host "WebView2 profile: $webview"

    $preflightOutput = & $python $policy --level medium --estimate-mib $budgetMiB --preflight-only
    $preflightExit = $LASTEXITCODE
    if ($preflightExit -ne 0) { Stop-Safe ('Resource Policy V2 preflight refused launch (exit ' + $preflightExit + ').') 2 }
    $preflightText = ($preflightOutput -join [Environment]::NewLine).Trim()
    try { $preflight = $preflightText | ConvertFrom-Json -ErrorAction Stop }
    catch { Stop-Safe 'Resource Policy V2 preflight output was not valid JSON.' 2 }
    if ($preflight.decision.level -ne 'medium' -or $preflight.decision.allowed -ne $true -or $preflight.decision.reason -ne 'MEASURED_BUDGET_FITS_WITH_RESERVE') {
        Stop-Safe 'Resource Policy V2 did not confirm the measured medium-task budget.' 2
    }

    $sameName = @(Get-CimInstance -ClassName Win32_Process -Filter "Name='PTTI-Video-First-R4-Preview.exe'" -ErrorAction Stop)
    foreach ($process in $sameName) {
        if ([string]::IsNullOrWhiteSpace($process.ExecutablePath)) { Stop-Safe 'Same-name process path is unreadable; duplicate launch refused.' 5 }
        $runningPath = [IO.Path]::GetFullPath([string]$process.ExecutablePath)
        if ([string]::Equals($runningPath, [IO.Path]::GetFullPath($exe), [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Safe ('This exact QA candidate is already running (PID ' + $process.ProcessId + '). No second instance was started.') 5
        }
    }

    if ($CheckOnly) {
        Write-Host 'QA identity, SHA-256, V2 preflight, isolation paths, and duplicate check passed.' -ForegroundColor Green
        exit 0
    }

    foreach ($directory in @($qaRoot, $dataRoot, $qaLocal, $webview, $research)) {
        if (-not [IO.Directory]::Exists($directory)) { [void][IO.Directory]::CreateDirectory($directory) }
        if (Test-ReparsePoint $directory) { Stop-Safe ('QA directory became a reparse point: ' + $directory) 3 }
    }
    if ([IO.File]::Exists($db) -and (Test-ReparsePoint $db)) { Stop-Safe 'QA DB file is a reparse point.' 3 }
    if (-not [IO.File]::Exists($marker)) {
        $identity = @{ product = 'PTTI Video First R4 QA'; commit = $expectedCommit; exe_sha256 = $expectedExeHash; database = $db; policy_sha256 = $expectedPolicyHash; resource_budget_mib = $budgetMiB; created_utc = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Compress
        $stream = [IO.File]::Open($marker, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes($identity)
            $stream.Write($bytes, 0, $bytes.Length)
        } finally { $stream.Dispose() }
    }

    $envNames = @('TEMP','TMP','LOCALAPPDATA','PTTI_ENV','PTTI_DB','PTTI_PREVIEW_QA_DB','PTTI_PREVIEW_PROFILE','PTTI_PREVIEW','PTTI_RESEARCH_DATA_ROOT','WEBVIEW2_USER_DATA_FOLDER','PTTI_DESKTOP_DEPLOY_ROOT')
    $oldEnvironment = @{}
    foreach ($name in $envNames) {
        $item = Get-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
        if ($null -eq $item) { $oldEnvironment[$name] = $null } else { $oldEnvironment[$name] = [string]$item.Value }
    }
    try {
        $env:TEMP = $tempBase
        $env:TMP = $tempBase
        $env:LOCALAPPDATA = $qaLocal
        $env:PTTI_ENV = 'test'
        $env:PTTI_DB = $pttiDbValue
        $env:PTTI_PREVIEW_QA_DB = $previewQaDbValue
        $env:PTTI_PREVIEW_PROFILE = 'video-first-r4'
        $env:PTTI_PREVIEW = '1'
        $env:PTTI_RESEARCH_DATA_ROOT = $research
        $env:WEBVIEW2_USER_DATA_FOLDER = $webview
        Remove-Item Env:PTTI_DESKTOP_DEPLOY_ROOT -ErrorAction SilentlyContinue
        if (-not [string]::Equals([IO.Path]::GetFullPath($env:PTTI_DB), [IO.Path]::GetFullPath($env:PTTI_PREVIEW_QA_DB), [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Safe 'PTTI_DB and PTTI_PREVIEW_QA_DB are not the same path.' 3
        }
        $started = Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru -ErrorAction Stop
    } finally {
        foreach ($name in $envNames) {
            if ($null -eq $oldEnvironment[$name]) { Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue }
            else { Set-Item -LiteralPath ('Env:' + $name) -Value $oldEnvironment[$name] }
        }
    }

    Write-Host 'Started the hash-verified isolated QA candidate.' -ForegroundColor Green
    Write-Host ('PID: {0}' -f $started.Id)
    Write-Host "Database: $db"
    Write-Host "WebView2 profile: $webview"
    Write-Host "Resource monitor log: $monitorLog"
    Write-Host 'Monitoring up to 15 minutes. The monitor never terminates a process.'

    & $python $policy --level medium --estimate-mib $budgetMiB --pid $started.Id --duration-seconds 900 --interval-seconds 2 --runtime-only --log-jsonl $monitorLog
    $monitorExit = $LASTEXITCODE
    if ($monitorExit -eq 0) {
        $started.Refresh()
        if ($started.HasExited) {
            Write-Host ('QA candidate exited; Windows exit code: ' + $started.ExitCode + '. Monitor cleaned up normally.') -ForegroundColor Green
        } else {
            Write-Host 'Resource monitor window ended normally; the QA app is left running.' -ForegroundColor Green
        }
        exit 0
    }
    Write-Host ('Resource monitor stopped with exit code ' + $monitorExit + '. Save your QA work and close only the GOAL107 QA window yourself; no process will be terminated automatically.') -ForegroundColor Yellow
    [void](Read-Host 'After closing the QA window, press Enter to finish this launcher')
    $started.Refresh()
    if (-not $started.HasExited) { Write-Host ('The QA window remains active at PID ' + $started.Id + '; it was not terminated.') -ForegroundColor Yellow }
    else { Write-Host ('The QA process exited with Windows code ' + $started.ExitCode + '.') }
    exit 2
} catch {
    if ($null -ne $started) {
        try {
            $started.Refresh()
            if (-not $started.HasExited) { Write-Host ('QA process PID ' + $started.Id + ' remains open; this wrapper will not terminate it.') -ForegroundColor Yellow }
        } catch { }
    }
    Stop-Safe $_.Exception.Message 1
}
