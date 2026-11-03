param([int]$Port = 4176, [switch]$NoBrowser, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$logFile = Join-Path $logs 'launcher.log'
$mutex = $null
$owned = $false
function Log([string]$Text) { Add-Content -LiteralPath $logFile -Encoding UTF8 -Value ((Get-Date -Format o) + ' ' + $Text) }
function Hash-File([string]$File) {
    $stream = [IO.File]::OpenRead($File)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Invalid local port.' }
    $manifestFile = Join-Path $root 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
    if ($manifest.contract_version -ne 'ptti.web-rc-manifest/0.1') { throw 'Unsupported candidate manifest.' }
    foreach ($entry in $manifest.files.PSObject.Properties) {
        $file = [IO.Path]::GetFullPath((Join-Path $root $entry.Name))
        if (-not $file.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $file -PathType Leaf)) { throw ('Candidate resource is missing or unsafe: ' + $entry.Name) }
        if ((Hash-File $file) -ne $entry.Value) { throw ('Candidate resource hash mismatch: ' + $entry.Name) }
    }
    $manifestSha = Hash-File $manifestFile
    $url = 'http://127.0.0.1:' + $Port + '/'
    function Health {
        try { $h = Invoke-RestMethod -Uri ($url + '__ptti/health.json') -UseBasicParsing -TimeoutSec 2 } catch { return $null }
        if ($h.app -eq 'ptti-portable-web-rc' -and $h.artifact_id -eq $manifest.artifact_id -and $h.manifest_sha256 -eq $manifestSha) { return $h }; return $null
    }
    $mutex = New-Object Threading.Mutex($false, ('Local\PTTI-Portable-RC-' + $Port))
    try { $owned = $mutex.WaitOne(40000) } catch [Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) { throw 'Another candidate launch is still running.' }
    $health = Health
    if (-not $health) {
        $tcp = New-Object Net.Sockets.TcpClient
        try { $busy = $tcp.ConnectAsync('127.0.0.1', $Port).Wait(600) -and $tcp.Connected } catch { $busy = $false } finally { $tcp.Dispose() }
        if ($busy) { throw ('Port ' + $Port + ' is occupied by another service. Nothing was stopped.') }
        if ($CheckOnly) { throw 'The candidate service is not running. CheckOnly does not start it.' }
        $arguments = '"' + (Join-Path $root 'app\server.mjs') + '" --port ' + $Port
        $p = Start-Process -FilePath (Join-Path $root 'runtime\node.exe') -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'stdout.log') -RedirectStandardError (Join-Path $logs 'stderr.log') -PassThru
        Log ('SERVICE_START pid=' + $p.Id + ' port=' + $Port)
        $deadline = (Get-Date).AddSeconds(25)
        do { Start-Sleep -Milliseconds 300; $health = Health } while (-not $health -and (Get-Date) -lt $deadline)
        if (-not $health) { throw 'The candidate did not become ready within 25 seconds. Check logs/server.log and logs/stderr.log.' }
    }
    Log ('READY artifact=' + $health.artifact_id + ' san=' + $health.san_head + ' core=' + $health.playback_head)
    if ($NoBrowser -or $CheckOnly) { $health | ConvertTo-Json -Compress; exit 0 }
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    if ($ram -lt 2.5) { throw ('Browser launch is BLOCKED by the 2.5 GiB memory guard. Available: ' + [math]::Round($ram,2) + ' GiB. The candidate service is ready.') }
    Start-Process $url
    Log ('BROWSER_OPEN ' + $url)
} catch {
    Log ('ERROR ' + $_.Exception.Message)
    if ($NoBrowser -or $CheckOnly) { Write-Error $_; exit 1 }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(('PTTI 候选版未能打开。' + [Environment]::NewLine + $_.Exception.Message + [Environment]::NewLine + '日志：' + $logFile), 'PTTI Cinema RC') | Out-Null
    exit 1
} finally { if ($owned) { $mutex.ReleaseMutex() }; if ($mutex) { $mutex.Dispose() } }
