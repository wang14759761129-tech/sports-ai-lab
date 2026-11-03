param(
    [Parameter(Mandatory = $true)]
    [string]$ExpectedExePath,
    [string]$VideoPath,
    [string]$ExpectedVideoSha256,
    [string]$CandidatePackagePath,
    [string]$ExpectedDatabasePath,
    [string]$ExpectedCommit = "491ed7ae4e74682e48a5b91d911014bb5dc8bda2"
)

$ErrorActionPreference = "Stop"
$script:checks = @()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $result = "FAIL"
    if ($Passed) {
        $result = "PASS"
    }
    $script:checks += [pscustomobject]@{
        check = $Name
        result = $result
        detail = $Detail
    }
}

$expectedExe = [System.IO.Path]::GetFullPath($ExpectedExePath)
$processRows = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -and $_.ExecutablePath -ieq $expectedExe
})

$diagnostics = $null
$diagnosticPort = $null
if ($processRows.Count -ne 1) {
    Add-Check "预览程序实例" $false "按指定 EXE 路径找到 $($processRows.Count) 个进程；必须恰好一个。"
}
if ($processRows.Count -eq 1) {
    $processRow = $processRows[0]
    $process = Get-Process -Id $processRow.ProcessId
    $responding = $process.Responding
    $windowTitle = $process.MainWindowTitle
    Add-Check "预览程序实例" ($responding -and [bool]$windowTitle) "PID=$($process.Id); Responding=$responding; 标题=$windowTitle"

    $listeners = @(Get-NetTCPConnection -OwningProcess $process.Id -State Listen -ErrorAction SilentlyContinue |
        Where-Object {
            $_.LocalAddress -eq "127.0.0.1" -or $_.LocalAddress -eq "::1" -or
            $_.LocalAddress -eq "0.0.0.0" -or $_.LocalAddress -eq "::"
        } | Select-Object -ExpandProperty LocalPort -Unique)
    foreach ($port in $listeners) {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/diagnostics/database" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($null -ne $response) {
            $diagnostics = $response
            $diagnosticPort = $port
            break
        }
    }
}

if ($null -eq $diagnostics) {
    Add-Check "本机诊断接口" $false "未能从指定程序监听端口读取 /api/diagnostics/database。"
}
if ($null -ne $diagnostics) {
    $commitMatches = $diagnostics.build.commit -eq $ExpectedCommit
    $isolatedEnvironment = $diagnostics.environment -eq "TEST"
    $productionUntouched = $diagnostics.build.production_database -eq "NOT_ACCESSED"
    Add-Check "预览版本" $commitMatches "commit=$($diagnostics.build.commit); expected=$ExpectedCommit; port=$diagnosticPort"
    Add-Check "隔离数据库环境" ($isolatedEnvironment -and $productionUntouched) "environment=$($diagnostics.environment); database=$($diagnostics.database); production=$($diagnostics.build.production_database)"
    if ($ExpectedDatabasePath) {
        $expectedDb = [System.IO.Path]::GetFullPath($ExpectedDatabasePath)
        $actualDb = [System.IO.Path]::GetFullPath($diagnostics.database)
        Add-Check "QA 数据库路径" ($actualDb -ieq $expectedDb) "actual=$actualDb; expected=$expectedDb"
    }
}

if ($VideoPath) {
    if (-not (Test-Path -LiteralPath $VideoPath -PathType Leaf)) {
        Add-Check "测试视频文件" $false "文件不存在：$VideoPath"
    }
    if (Test-Path -LiteralPath $VideoPath -PathType Leaf) {
        $video = Get-Item -LiteralPath $VideoPath
        $videoHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $VideoPath).Hash.ToLowerInvariant()
        $hashMatches = $true
        if ($ExpectedVideoSha256) {
            $hashMatches = $videoHash -eq $ExpectedVideoSha256.ToLowerInvariant()
        }
        Add-Check "测试视频 SHA256" $hashMatches "sha256=$videoHash; bytes=$($video.Length); path=$($video.FullName)"
    }
}

if ($CandidatePackagePath) {
    if (-not (Test-Path -LiteralPath $CandidatePackagePath -PathType Leaf)) {
        Add-Check "候选包文件" $false "文件不存在：$CandidatePackagePath"
    }
    if (Test-Path -LiteralPath $CandidatePackagePath -PathType Leaf) {
        $packageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $CandidatePackagePath).Hash.ToLowerInvariant()
        $firstLine = Get-Content -LiteralPath $CandidatePackagePath -TotalCount 1 -Encoding UTF8
        $header = $firstLine | ConvertFrom-Json
        $manifest = $header.manifest
        $isExpectedFormat = $header.kind -eq "manifest" -and $manifest.schema -eq "ptti-ai-evidence-package-v1"
        $sourceMatches = $false
        if ($ExpectedVideoSha256 -and $manifest.source_video_sha256) {
            $sourceMatches = $manifest.source_video_sha256.ToLowerInvariant() -eq $ExpectedVideoSha256.ToLowerInvariant()
        }
        Add-Check "候选包来源绑定" ($isExpectedFormat -and $sourceMatches) "format=$($manifest.schema); source_video_sha256=$($manifest.source_video_sha256); package_sha256=$packageHash"
    }
}

$script:checks | ConvertTo-Json -Depth 5
if (@($script:checks | Where-Object { $_.result -eq "FAIL" }).Count -gt 0) {
    exit 1
}
