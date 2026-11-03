param(
    [string]$Compare,
    [string]$OutputDirectory = (Join-Path $env:LOCALAPPDATA 'PTTI-Dev\memory-audit'),
    [ValidateRange(1, 5)][int]$PagingSamples = 3
)

$ErrorActionPreference = 'Stop'
$gib = [double](1024 * 1024 * 1024)
$now = Get-Date
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function To-GiB([double]$Bytes) { [math]::Round($Bytes / $gib, 3) }
function Safe-StartTime($Process) {
    try { $Process.StartTime.ToString('o') } catch { $null }
}

# Read worktree locations in memory only. The snapshot stores branch labels, never paths.
$worktrees = @()
try {
    $worktreeText = & git -C $repo worktree list --porcelain 2>$null
    $wtPath = $null
    $wtBranch = $null
    foreach ($line in $worktreeText) {
        if ($line -match '^worktree (.+)$') { $wtPath = $Matches[1]; continue }
        if ($line -match '^branch refs/heads/(.+)$') { $wtBranch = $Matches[1] }
        if ([string]::IsNullOrWhiteSpace($line)) {
            if ($wtPath -and $wtBranch) { $worktrees += [pscustomobject]@{ Path = $wtPath.TrimEnd('\'); Branch = $wtBranch } }
            $wtPath = $null; $wtBranch = $null
        }
    }
    if ($wtPath -and $wtBranch) { $worktrees += [pscustomobject]@{ Path = $wtPath.TrimEnd('\'); Branch = $wtBranch } }
} catch { }

$os = Get-CimInstance Win32_OperatingSystem
$installedBytes = [double](Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum
$memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$availableBytes = [double]$memory.AvailableBytes
$visibleBytes = [double]$os.TotalVisibleMemorySize * 1KB
$commitBytes = [double]$memory.CommittedBytes
$commitLimitBytes = [double]$memory.CommitLimit
$hardwareReservedBytes = [math]::Max(0, $installedBytes - $visibleBytes)

# Short on-demand counter sample distinguishes active paging from cumulative fault totals.
$paging = [ordered]@{ pagesPerSecondAverage = $null; pageReadsPerSecondAverage = $null; pageWritesPerSecondAverage = $null; samples = $PagingSamples }
try {
    $counterSets = Get-Counter -Counter '\Memory\Pages/sec','\Memory\Page Reads/sec','\Memory\Page Writes/sec' -SampleInterval 1 -MaxSamples $PagingSamples
    $values = @{}
    foreach ($sampleSet in $counterSets) {
        foreach ($sample in $sampleSet.CounterSamples) {
            $key = ($sample.Path -split '\\')[-1].ToLowerInvariant()
            if (!$values.ContainsKey($key)) { $values[$key] = @() }
            $values[$key] += [double]$sample.CookedValue
        }
    }
    $paging.pagesPerSecondAverage = if ($values['pages/sec']) { [math]::Round(($values['pages/sec'] | Measure-Object -Average).Average, 1) } else { $null }
    $paging.pageReadsPerSecondAverage = if ($values['page reads/sec']) { [math]::Round(($values['page reads/sec'] | Measure-Object -Average).Average, 1) } else { $null }
    $paging.pageWritesPerSecondAverage = if ($values['page writes/sec']) { [math]::Round(($values['page writes/sec'] | Measure-Object -Average).Average, 1) } else { $null }
} catch { $paging.error = 'Performance counters unavailable'; $paging.samples = 0 }

$pagefileSettings = @(Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ initialMiB = $_.InitialSize; maximumMiB = $_.MaximumSize }
})
$pagefileUsage = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ allocatedMiB = $_.AllocatedBaseSize; currentMiB = $_.CurrentUsage; peakMiB = $_.PeakUsage }
})

$allCim = @(Get-CimInstance Win32_Process)
$procById = @{}
foreach ($item in $allCim) { $procById[[int]$item.ProcessId] = $item }
$procRows = foreach ($item in $allCim) {
    $proc = Get-Process -Id ([int]$item.ProcessId) -ErrorAction SilentlyContinue
    if (!$proc) { continue }
    $cmd = [string]$item.CommandLine
    $owner = 'UNCLASSIFIED'
    $ancestor = $item
    for ($depth = 0; $depth -lt 10 -and $ancestor; $depth++) {
        $ancestorCommand = (([string]$ancestor.CommandLine) + ' ' + [string]$ancestor.ExecutablePath).Replace('/', '\')
        foreach ($worktree in $worktrees) {
            $worktreePath = ([string]$worktree.Path).Replace('/', '\').TrimEnd('\')
            if ($worktreePath -and $ancestorCommand.IndexOf($worktreePath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $owner = $worktree.Branch
                break
            }
        }
        if ($owner -ne 'UNCLASSIFIED') { break }
        $ancestor = $procById[[int]$ancestor.ParentProcessId]
    }
    if ($owner -eq 'UNCLASSIFIED' -and $proc.ProcessName -match '(?i)^PTTI') { $owner = 'PTTI_RUNTIME_UNVERIFIED' }
    $kind = if ($cmd -match '(?i)pytest') { 'pytest' } elseif ($cmd -match '(?i)pyinstaller') { 'packager' } elseif ($cmd -match '(?i)uvicorn|fastapi|flask') { 'python-service' } elseif ($cmd -match '(?i)vite') { 'vite' } elseif ($cmd -match '(?i)node_repl') { 'codex-node-repl' } elseif ($proc.ProcessName -match '(?i)chrome|msedge') { 'browser' } else { 'process' }
    $procById[[int]$item.ProcessId] = $item
    [pscustomobject]@{
        name = $proc.ProcessName
        image = if ($item.ExecutablePath) { [IO.Path]::GetFileName($item.ExecutablePath) } else { $null }
        pid = [int]$item.ProcessId
        parentPid = [int]$item.ParentProcessId
        parentName = if ($procById.ContainsKey([int]$item.ParentProcessId)) { $procById[[int]$item.ParentProcessId].Name } else { $null }
        started = Safe-StartTime $proc
        owner = $owner
        kind = $kind
        workingSetMiB = [math]::Round($proc.WorkingSet64 / 1MB, 1)
        privateMiB = [math]::Round($proc.PrivateMemorySize64 / 1MB, 1)
    }
}

$listeners = @()
try {
    $establishedByPid = @{}
    Get-NetTCPConnection -State Established -ErrorAction Stop | Group-Object OwningProcess | ForEach-Object { $establishedByPid[[int]$_.Name] = $_.Count }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | ForEach-Object {
        $proc = $procRows | Where-Object pid -eq ([int]$_.OwningProcess) | Select-Object -First 1
        [pscustomobject]@{ port = [int]$_.LocalPort; pid = [int]$_.OwningProcess; process = if ($proc) { $proc.name } else { 'unknown' }; owner = if ($proc) { $proc.owner } else { 'UNCLASSIFIED' }; establishedConnectionCount = if ($establishedByPid.ContainsKey([int]$_.OwningProcess)) { $establishedByPid[[int]$_.OwningProcess] } else { 0 } }
    } | Where-Object { $_.owner -ne 'UNCLASSIFIED' -or $_.process -match '^(?i:node|python|pythonw|python\d+(\.\d+)?|ptti)' })
} catch { }

$topWorkingSet = @($procRows | Sort-Object workingSetMiB -Descending | Select-Object -First 20)
$topPrivate = @($procRows | Sort-Object privateMiB -Descending | Select-Object -First 20)
$pttiProcesses = @($procRows | Where-Object { $_.owner -match 'ptti|playback|premium|web-mvp' -or $_.kind -in @('pytest','packager','python-service','vite') })
$processGroupTotals = @($procRows | Group-Object { "$($_.owner)|$($_.kind)" } | ForEach-Object {
    [pscustomobject]@{
        group = $_.Name
        processCount = $_.Count
        workingSetMiB = [math]::Round(($_.Group | Measure-Object -Property workingSetMiB -Sum).Sum, 1)
        privateMiB = [math]::Round(($_.Group | Measure-Object -Property privateMiB -Sum).Sum, 1)
    }
})
$compression = 'UNKNOWN (Get-MMAgent requires access on this device)'
try { $compression = [string](Get-MMAgent -ErrorAction Stop | Select-Object -ExpandProperty MemoryCompression) } catch { }
$pagefileOnDisk = Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue | Measure-Object -Property CurrentUsage -Sum
$disk = Get-PSDrive -Name (Split-Path -Qualifier $repo).TrimEnd(':') -ErrorAction SilentlyContinue

$snapshot = [ordered]@{
    schema = 1
    capturedAt = $now.ToUniversalTime().ToString('o')
    machineLabel = 'this Windows device'
    repository = 'sports-ai-lab/products/ptti'
    memory = [ordered]@{
        installedGiB = To-GiB $installedBytes
        visibleGiB = To-GiB $visibleBytes
        hardwareReservedGiB = To-GiB $hardwareReservedBytes
        availableGiB = To-GiB $availableBytes
        inUseGiB = To-GiB ($visibleBytes - $availableBytes)
        cacheGiB = To-GiB ([double]$memory.CacheBytes)
        standbyGiB = To-GiB ([double]($memory.StandbyCacheCoreBytes + $memory.StandbyCacheNormalPriorityBytes + $memory.StandbyCacheReserveBytes))
        modifiedGiB = To-GiB ([double]$memory.ModifiedPageListBytes)
        compressedPages = $null
        compressionSetting = $compression
        commitChargeGiB = To-GiB $commitBytes
        commitLimitGiB = To-GiB $commitLimitBytes
        commitPercent = if ($commitLimitBytes -gt 0) { [math]::Round($commitBytes / $commitLimitBytes * 100, 1) } else { $null }
        pagedPoolGiB = To-GiB ([double]$memory.PoolPagedBytes)
        nonPagedPoolGiB = To-GiB ([double]$memory.PoolNonpagedBytes)
        pagingCounters = $paging
    }
    pagefile = [ordered]@{ settings = $pagefileSettings; usage = $pagefileUsage; currentUsageTotalMiB = [double]$pagefileOnDisk.Sum }
    diskFreeGiB = if ($disk) { [math]::Round($disk.Free / $gib, 1) } else { $null }
    processCount = $procRows.Count
    topWorkingSet = $topWorkingSet
    topPrivate = $topPrivate
    processGroupTotals = $processGroupTotals
    pttiAndDevelopmentProcesses = $pttiProcesses
    listeners = $listeners
    dataCollection = 'Process command lines and paths are used in memory only for worktree classification and are not written to this snapshot.'
}

$before = $null
if ($Compare) {
    $before = Get-Content -LiteralPath $Compare -Raw | ConvertFrom-Json
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stamp = $now.ToString('yyyyMMdd-HHmmss-fff')
$jsonPath = Join-Path $OutputDirectory "memory-audit-$stamp.json"
$reportPath = Join-Path $OutputDirectory "memory-audit-$stamp.md"
$snapshot | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding utf8

$report = [System.Collections.Generic.List[string]]::new()
$report.Add('# Windows 内存审计')
$report.Add('')
$report.Add("采集时间：$($now.ToString('yyyy-MM-dd HH:mm:ss zzz'))；只读采集，无进程、服务、页面文件或系统设置变更。")
$report.Add('')
$report.Add('## 内存概况')
$report.Add('')
$report.Add("- 物理内存：$($snapshot.memory.installedGiB) GiB 安装，$($snapshot.memory.visibleGiB) GiB 可见；硬件保留约 $($snapshot.memory.hardwareReservedGiB) GiB。")
$report.Add("- 可用 $($snapshot.memory.availableGiB) GiB；在用 $($snapshot.memory.inUseGiB) GiB；缓存 $($snapshot.memory.cacheGiB) GiB，其中待机页约 $($snapshot.memory.standbyGiB) GiB，修改页约 $($snapshot.memory.modifiedGiB) GiB。")
$report.Add("- 提交量 $($snapshot.memory.commitChargeGiB)/$($snapshot.memory.commitLimitGiB) GiB（$($snapshot.memory.commitPercent)%）；页面文件当前使用合计 $($snapshot.pagefile.currentUsageTotalMiB) MiB。")
$report.Add("- 内存压缩设置：$($snapshot.memory.compressionSetting)。页面调入平均 $($paging.pageReadsPerSecondAverage) 次/秒，页面写出平均 $($paging.pageWritesPerSecondAverage) 次/秒（$($paging.samples) 秒采样）；单次采样不能证明长期分页压力。")
$report.Add('')
$report.Add('## 最大工作集进程')
$report.Add('')
$report.Add('| 进程 | PID | 父 PID | 工作集 MiB | 私有 MiB | 工作区归属 | 类型 |')
$report.Add('|---|---:|---:|---:|---:|---|---|')
foreach ($p in $topWorkingSet) { $report.Add("| $($p.name) | $($p.pid) | $($p.parentPid) | $($p.workingSetMiB) | $($p.privateMiB) | $($p.owner) | $($p.kind) |") }
$report.Add('')
$report.Add('## 最大私有内存进程')
$report.Add('')
$report.Add('| 进程 | PID | 父 PID | 私有 MiB | 工作集 MiB | 工作区归属 | 类型 |')
$report.Add('|---|---:|---:|---:|---:|---|---|')
foreach ($p in $topPrivate) { $report.Add("| $($p.name) | $($p.pid) | $($p.parentPid) | $($p.privateMiB) | $($p.workingSetMiB) | $($p.owner) | $($p.kind) |") }
$report.Add('')
$report.Add('## PTTI / 开发服务与监听端口')
$report.Add('')
if ($pttiProcesses.Count -eq 0) { $report.Add('未发现可归属到已登记 PTTI 工作区的测试服务、pytest 或打包器。') }
else { foreach ($p in $pttiProcesses) { $report.Add("- $($p.name) PID $($p.pid)，父 PID $($p.parentPid)，工作集 $($p.workingSetMiB) MiB，私有 $($p.privateMiB) MiB；归属 $($p.owner)，类型 $($p.kind)。") } }
foreach ($l in $listeners | Sort-Object port) { $report.Add("- 监听端口 $($l.port)：$($l.process) PID $($l.pid)，归属 $($l.owner)，已建立连接数 $($l.establishedConnectionCount)。") }
$report.Add('')
$report.Add('## 前后比较')
$report.Add('')
if (!$before) { $report.Add('未传入 -Compare；本次快照可作为后续基线。') }
else {
    $report.Add("前次可用 $($before.memory.availableGiB) GiB，当前 $($snapshot.memory.availableGiB) GiB，变化 $([math]::Round($snapshot.memory.availableGiB - $before.memory.availableGiB, 3)) GiB。")
    $report.Add("前次提交 $($before.memory.commitChargeGiB) GiB，当前 $($snapshot.memory.commitChargeGiB) GiB，变化 $([math]::Round($snapshot.memory.commitChargeGiB - $before.memory.commitChargeGiB, 3)) GiB。")
    if ($before.processGroupTotals) {
        $previousGroups = @{}
        foreach ($group in $before.processGroupTotals) { $previousGroups[[string]$group.group] = $group }
        $groupChanges = @($snapshot.processGroupTotals | ForEach-Object {
            $prior = $previousGroups[[string]$_.group]
            if ($prior) {
                [pscustomobject]@{
                    group = $_.group
                    processCountDelta = [int]$_.processCount - [int]$prior.processCount
                    workingSetDeltaMiB = [math]::Round([double]$_.workingSetMiB - [double]$prior.workingSetMiB, 1)
                    privateDeltaMiB = [math]::Round([double]$_.privateMiB - [double]$prior.privateMiB, 1)
                }
            }
        } | Sort-Object { [math]::Abs($_.privateDeltaMiB) } -Descending | Select-Object -First 8)
        foreach ($change in $groupChanges) { $report.Add("- $($change.group)：私有内存变化 $($change.privateDeltaMiB) MiB，工作集变化 $($change.workingSetDeltaMiB) MiB，进程数变化 $($change.processCountDelta)。") }
    } else { $report.Add('前次快照没有进程分组指标；本次已记录分组，后续比较可提供进程级变化。') }
}
$report.Add('')
$report.Add('进程工作集与私有内存按 PID 和父 PID 展示；快照不包含路径、命令行、媒体信息、凭据或事件正文。只读审计不会清空缓存、结束进程或修改任何 Windows 设置。')
$report | Set-Content -LiteralPath $reportPath -Encoding utf8

Write-Output "JSON: $jsonPath"
Write-Output "REPORT: $reportPath"
Write-Output "AVAILABLE_GIB: $($snapshot.memory.availableGiB)"
Write-Output "COMMIT: $($snapshot.memory.commitChargeGiB)/$($snapshot.memory.commitLimitGiB) GiB ($($snapshot.memory.commitPercent)%)"
Write-Output "PTTI_DEV_PROCESSES: $($pttiProcesses.Count)"
Write-Output "LISTENERS: $($listeners.Count)"
