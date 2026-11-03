param([string]$ConfigPath = (Join-Path $PSScriptRoot 'web-pro.json'), [switch]$CheckOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$mutex = $null
$owned = $false
$logPath = Join-Path $PSScriptRoot 'launcher.log'
function Write-LaunchLog([string]$Text) { Add-Content -LiteralPath $logPath -Value ((Get-Date -Format o) + ' ' + $Text) -Encoding UTF8 }
try {
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    $project = [IO.Path]::GetFullPath($config.project)
    $core = [IO.Path]::GetFullPath($config.playback_core_source)
    if (-not (Test-Path -LiteralPath $core -PathType Leaf)) { throw 'Playback Core source is unavailable. This Alpha requires its reviewed local worktree.' }
    $package = Get-Content -LiteralPath (Join-Path $project 'package.json') -Raw | ConvertFrom-Json
    if ($package.name -ne 'ptti-web-mvp' -or $package.scripts.'dev:review' -ne 'vite --mode internal-review --host 127.0.0.1 --port 4174 --strictPort') { throw 'Unexpected Web package or review startup command.' }
    if (-not (Test-Path -LiteralPath (Join-Path $project 'node_modules\vite\bin\vite.js'))) { throw 'Local Web dependencies are missing.' }
    if (-not (Test-Path -LiteralPath $config.node)) { throw 'Node runtime is unavailable.' }
    function Get-PTTIHealth {
        try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:4174/__ptti/health.json' -TimeoutSec 2 -UseBasicParsing } catch { return $null }
        if ($h.app -eq 'ptti-web-review-alpha' -and $h.mode -eq 'internal-review' -and $h.workspace -ieq $project -and $h.playback_core_source -ieq $core) { return $h }
        return $null
    }
    $mutex = New-Object Threading.Mutex($false, 'Local\PTTI-Web-Pro-4174-Launcher')
    try { $owned = $mutex.WaitOne(45000) } catch [Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) { throw 'Another PTTI launch is still in progress. Try again shortly.' }
    $health = Get-PTTIHealth
    if (-not $health) {
        $listener = [Net.Sockets.TcpClient]::new()
        try { $connected = $listener.ConnectAsync('127.0.0.1', 4174).Wait(700) -and $listener.Connected } catch { $connected = $false } finally { $listener.Dispose() }
        if ($connected) { throw 'Port 4174 is occupied by an unverified service. It was not stopped or replaced.' }
        if ($CheckOnly) { throw 'PTTI service is not running. CheckOnly does not start it.' }
        $worker = Join-Path $PSScriptRoot 'Start-PTTI-Web-Service.ps1'
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $worker + '" -ConfigPath "' + $ConfigPath + '"'
        $process = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList $arguments -WindowStyle Hidden -PassThru
        Write-LaunchLog ('service-start-request pid=' + $process.Id)
        $deadline = (Get-Date).AddSeconds(35)
        do { Start-Sleep -Milliseconds 400; $health = Get-PTTIHealth } while (-not $health -and (Get-Date) -lt $deadline)
        if (-not $health) { throw 'PTTI did not become ready within 35 seconds. See service.log and launcher.log.' }
    }
    Write-LaunchLog ('ready san=' + $health.san_head + ' playback=' + $health.playback_head)
    if ($CheckOnly -or $NoBrowser) { $health | ConvertTo-Json -Compress; exit 0 }
    $ram = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    if ($ram -lt 2.5) { throw ('Web service is ready, but browser launch is blocked by the 2.5 GiB RAM guard. Available: ' + [math]::Round($ram,2) + ' GiB.') }
    Start-Process 'http://127.0.0.1:4174/'
    Write-LaunchLog 'default-browser-open-request http://127.0.0.1:4174/'
} catch {
    Write-LaunchLog ('ERROR ' + $_.Exception.Message)
    if ($CheckOnly -or $NoBrowser) { Write-Error $_; exit 1 }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(('PTTI Web Pro could not open.' + [Environment]::NewLine + $_.Exception.Message + [Environment]::NewLine + 'Log: ' + $logPath), 'PTTI Cinema') | Out-Null
    exit 1
} finally { if ($owned) { $mutex.ReleaseMutex() }; if ($mutex) { $mutex.Dispose() } }
