param(
    [Parameter(Mandatory = $true)]
    [string]$CandidateRoot
)

$ErrorActionPreference = 'Stop'

function Stop-Safe([string]$Message) {
    throw "GEX-03B Native QA refused to start: $Message"
}

function Test-UnderRoot([string]$Path, [string]$Root) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    return $fullPath.StartsWith(($fullRoot + '\'), [StringComparison]::OrdinalIgnoreCase)
}

try {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) { Stop-Safe 'LOCALAPPDATA is unavailable.' }
    $localAppData = [IO.Path]::GetFullPath($env:LOCALAPPDATA)
    $buildsRoot = [IO.Path]::GetFullPath((Join-Path $localAppData 'PTTI-Builds'))
    $candidate = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
    if (-not (Test-UnderRoot $candidate $buildsRoot)) { Stop-Safe 'Candidate must remain under LOCALAPPDATA\PTTI-Builds.' }

    $exeName = 'PTTI-Video-First-R4-Preview.exe'
    $exe = Join-Path $candidate $exeName
    $buildInfoPath = Join-Path $candidate 'build-info.json'
    $hashPath = Join-Path $candidate ($exeName + '.sha256')
    foreach ($path in @($exe, $buildInfoPath, $hashPath)) {
        if (-not [IO.File]::Exists($path)) { Stop-Safe ('Candidate file is missing: ' + $path) }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Safe ('Candidate path is a reparse point: ' + $path) }
    }

    $info = Get-Content -LiteralPath $buildInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($info.product_name -ne 'PTTI Video First R4' -or $info.version -ne '0.6.1-R4' -or
        $info.environment -ne 'DEVELOPMENT' -or $info.source_tree_dirty -ne $false -or
        $info.official_release -ne $false -or $info.media_included -ne $false -or
        $info.commit -notmatch '^[0-9a-f]{40}$') {
        Stop-Safe 'Candidate build identity is not a clean, non-release R4 preview.'
    }
    $sidecar = (Get-Content -LiteralPath $hashPath -Raw -Encoding ASCII).Trim() -split '\s+'
    if ($sidecar.Count -ne 2 -or $sidecar[1] -ne $exeName -or
        (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sidecar[0].ToLowerInvariant()) {
        Stop-Safe 'Candidate executable SHA-256 does not match its sidecar.'
    }

    $sameName = @(Get-CimInstance -ClassName Win32_Process -Filter "Name='$exeName'" -ErrorAction Stop)
    foreach ($process in $sameName) {
        if ([string]::IsNullOrWhiteSpace($process.ExecutablePath)) { Stop-Safe 'A same-name process path is unreadable; duplicate launch refused.' }
        if ([string]::Equals([IO.Path]::GetFullPath($process.ExecutablePath), [IO.Path]::GetFullPath($exe), [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Safe ('This exact Native QA candidate is already running (PID ' + $process.ProcessId + ').')
        }
    }

    $policy = Join-Path $PSScriptRoot '..\..\scripts\resource_policy_v2.py'
    $python = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
    if (-not [IO.File]::Exists($policy) -or -not [IO.File]::Exists($python)) { Stop-Safe 'The existing Resource Policy V2 runtime is unavailable.' }
    $preflightOutput = & $python $policy --level heavy --preflight-only
    if ($LASTEXITCODE -ne 0) { Stop-Safe 'Resource Policy V2 refused the Native QA launch.' }
    try { $preflight = (($preflightOutput -join [Environment]::NewLine).Trim() | ConvertFrom-Json -ErrorAction Stop) }
    catch { Stop-Safe 'Resource Policy V2 did not return valid JSON.' }
    if ($preflight.decision.level -ne 'heavy' -or $preflight.decision.allowed -ne $true -or
        $preflight.decision.reason -ne 'HEAVY_START_BUDGET_MET') {
        Stop-Safe 'Resource Policy V2 did not confirm the existing 2.5 GiB launch gate.'
    }

    $qaRoot = [IO.Path]::GetFullPath((Join-Path $localAppData ('PTTI-Dev\NativeQA\GEX03\' + $info.commit)))
    $qaDataRoot = Join-Path $qaRoot 'qa-data'
    if (-not (Test-UnderRoot $qaDataRoot $qaRoot)) { Stop-Safe 'QA SQLite path is outside this candidate commit root.' }
    if (-not (Test-UnderRoot $qaRoot (Join-Path $localAppData 'PTTI-Dev\NativeQA\GEX03'))) { Stop-Safe 'QA SQLite root is outside LOCALAPPDATA Native QA.' }
    if ([IO.Directory]::Exists($qaDataRoot)) {
        $rootItem = Get-Item -LiteralPath $qaDataRoot -Force
        if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Stop-Safe 'QA database root is a reparse point.' }
    } elseif ([IO.File]::Exists($qaDataRoot)) {
        Stop-Safe 'QA database root path is occupied by a file.'
    }
    $qaDatabase = Join-Path $qaDataRoot 'matches.db'

    $envNames = @(
        'PTTI_NATIVE_QA', 'PTTI_NATIVE_QA_CANDIDATE_ROOT', 'PTTI_NATIVE_QA_PORT',
        'PTTI_PREVIEW_QA_DB', 'PTTI_NATIVE_QA_DATA_ROOT', 'PTTI_DB', 'PTTI_ENV', 'PTTI_PREVIEW',
        'PTTI_PREVIEW_PROFILE', 'PTTI_VIDEO_FEED_PREVIEW', 'PTTI_DESKTOP_DEPLOY_ROOT'
    )
    $oldEnvironment = @{}
    foreach ($name in $envNames) {
        $item = Get-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
        if ($null -eq $item) { $oldEnvironment[$name] = $null } else { $oldEnvironment[$name] = [string]$item.Value }
    }
    try {
        $env:PTTI_NATIVE_QA = '1'
        $env:PTTI_NATIVE_QA_CANDIDATE_ROOT = $candidate
        $env:PTTI_NATIVE_QA_PORT = '48761'
        $env:PTTI_PREVIEW_QA_DB = $qaDatabase
        $env:PTTI_DB = $qaDatabase
        $env:PTTI_ENV = 'development'
        $env:PTTI_PREVIEW = '1'
        $env:PTTI_PREVIEW_PROFILE = 'video-first-r4'
        $env:PTTI_VIDEO_FEED_PREVIEW = '1'
        Remove-Item Env:PTTI_DESKTOP_DEPLOY_ROOT -ErrorAction SilentlyContinue
        $started = Start-Process -FilePath $exe -WorkingDirectory $candidate -PassThru -ErrorAction Stop
    } finally {
        foreach ($name in $envNames) {
            if ($null -eq $oldEnvironment[$name]) { Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue }
            else { Set-Item -LiteralPath ('Env:' + $name) -Value $oldEnvironment[$name] }
        }
    }

    Write-Host 'Started the hash-verified isolated Native QA candidate; no formal R4 path or database was selected.' -ForegroundColor Green
    Write-Host ('PID: ' + $started.Id)
    Write-Host ('Commit: ' + $info.commit)
    Write-Host ('Fixed origin: http://127.0.0.1:48761')
    Write-Host ('Persistent per-commit QA SQLite: ' + $qaDatabase)
    Write-Host 'Earlier GEX-03B TEMP data is not imported, moved, deleted, or overwritten.'
    Write-Host ('Persistent WebView2 profile: ' + (Join-Path $localAppData ('PTTI-Dev\NativeQA\GEX03\' + $info.commit + '\webview2-user-data')))
    Write-Host 'Monitoring up to 15 minutes. The monitor never terminates PTTI or other processes.'
    $monitorLog = Join-Path $qaRoot 'resource-policy-v2.jsonl'
    & $python $policy --level heavy --pid $started.Id --duration-seconds 900 --interval-seconds 2 --runtime-only --log-jsonl $monitorLog
    $monitorExit = $LASTEXITCODE
    if ($monitorExit -ne 0) {
        Write-Host 'Resource monitoring stopped. Save your QA work and close only this Native QA window yourself; no process was terminated.' -ForegroundColor Yellow
        Write-Host ('Resource monitor log: ' + $monitorLog)
    } else {
        Write-Host ('Resource monitor completed. Candidate remains open only if still running; PID ' + $started.Id)
    }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
