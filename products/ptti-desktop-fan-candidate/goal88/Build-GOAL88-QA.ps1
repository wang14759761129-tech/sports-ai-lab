[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$SanRoot,
    [Parameter(Mandatory=$true)][string]$SanCommit,
    [Parameter(Mandatory=$true)][string]$NodeExe,
    [Parameter(Mandatory=$true)][string]$ViteScript,
    [Parameter(Mandatory=$true)][int]$CinemaPort,
    [Parameter(Mandatory=$true)][string]$GitExe,
    [Parameter(Mandatory=$true)][string]$WebProRoot,
    [Parameter(Mandatory=$true)][string]$NativeRoot,
    [Parameter(Mandatory=$true)][string]$HostBaseCommit,
    [Parameter(Mandatory=$true)][string]$SelectorSourceCommit,
    [ValidateSet('DEV_PREVIEW','QA_DESKTOP')][string]$CinemaMode = 'DEV_PREVIEW',
    [string]$CinemaCandidateDirectory
)
$ErrorActionPreference = 'Stop'

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing." }
    if ((Get-Sha256 $Path) -ne $Expected.ToLowerInvariant()) { throw "$Label SHA-256 changed." }
}
function Invoke-Git([string]$Root, [string[]]$GitArgs) {
    $result = & $GitExe -C $Root @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Git identity check failed in $Root." }
    (($result | Out-String).Trim())
}
function Write-Utf8NoBom([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$candidateRoot = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $candidateRoot) { throw "Refusing to overwrite existing candidate: $candidateRoot" }
if ($CinemaPort -lt 1024 -or $CinemaPort -gt 65535) { throw 'Cinema port is outside the valid user-port range.' }
if ($SanCommit -notmatch '^[0-9a-f]{40}$' -or $HostBaseCommit -notmatch '^[0-9a-f]{40}$' -or $SelectorSourceCommit -notmatch '^[0-9a-f]{40}$') { throw 'A pinned Git identity is malformed.' }

$currentSanHead = Invoke-Git $SanRoot @('rev-parse','HEAD')
if ($currentSanHead -ne $SanCommit) { throw 'San HEAD changed from the requested build pin.' }
if ((Invoke-Git $repoRoot @('rev-parse','HEAD')) -ne $SelectorSourceCommit) { throw 'Host selector source commit changed from the requested pin.' }
& $GitExe -C $repoRoot cat-file -e "$HostBaseCommit^{commit}" 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Host baseline commit is not present in the local repository.' }

$webLauncher = Join-Path $WebProRoot 'Start-PTTI-Active.ps1'
$activeManifest = Join-Path $WebProRoot 'active-release.json'
$active = Get-Content -LiteralPath $activeManifest -Raw | ConvertFrom-Json
if ($active.contract -ne 'ptti.active-release/0.1' -or $active.current -ne 'web-pro-4174-accepted') { throw 'Web Pro active release identity changed.' }
$releaseManifest = Join-Path $WebProRoot ('releases\' + $active.current + '.json')
$release = Get-Content -LiteralPath $releaseManifest -Raw | ConvertFrom-Json
if ($release.status -ne 'ACCEPTED' -or $release.url -ne 'http://127.0.0.1:4174/') { throw 'Web Pro is not the expected accepted local release.' }

$cinemaTarget = $null
$targetSchema = 'ptti.goal88.targets.v1'
$targetVersion = 'goal88-qa-' + $SanCommit.Substring(0,7)
if ($CinemaMode -eq 'QA_DESKTOP') {
    if ([string]::IsNullOrWhiteSpace($CinemaCandidateDirectory)) { throw 'QA_DESKTOP requires an explicit independent Cinema candidate directory.' }
    $cinemaRoot = [IO.Path]::GetFullPath($CinemaCandidateDirectory)
    $cinemaExe = Join-Path $cinemaRoot 'host\PTTI-Desktop-Fan.exe'
    $cinemaReleasePath = Join-Path $cinemaRoot 'release.json'
    if ((Get-Item -LiteralPath $cinemaRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Cinema QA candidate root is redirected.' }
    if ((Get-Item -LiteralPath $cinemaExe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Cinema QA executable is redirected.' }
    $cinemaRelease = Get-Content -LiteralPath $cinemaReleasePath -Raw | ConvertFrom-Json
    $cinemaExeSha = Get-Sha256 $cinemaExe
    $cinemaReleaseSha = Get-Sha256 $cinemaReleasePath
    if ($cinemaRelease.schema -ne 'ptti.desktop-fan.release.v1' -or
        $cinemaRelease.version -ne '0.1.14-unified-4decbc8' -or
        $cinemaRelease.san_commit -ne $SanCommit -or
        $cinemaRelease.host_commit -ne $HostBaseCommit -or
        $cinemaRelease.native_bridge_status -ne 'DISABLED_NO_R4_BRIDGE' -or
        $cinemaRelease.profile_mode -ne 'QA_ONLY_TEMP_VERSION_PORT_SCOPED' -or
        [int]$cinemaRelease.default_port -ne $CinemaPort) { throw 'Cinema QA release identity does not match the requested selector target.' }
    if ($cinemaRelease.files.'host/PTTI-Desktop-Fan.exe' -ne $cinemaExeSha) { throw 'Cinema QA executable is not in its release file manifest.' }
    $cinemaTarget = [ordered]@{
        mode = 'QA_DESKTOP'
        exe = $cinemaExe
        exe_sha256 = $cinemaExeSha
        release_manifest = $cinemaReleasePath
        release_sha256 = $cinemaReleaseSha
        version = $cinemaRelease.version
        san_head = $cinemaRelease.san_commit
        host_commit = $cinemaRelease.host_commit
        static_artifact_sha256 = $cinemaRelease.static_artifact_sha256
        port = [int]$cinemaRelease.default_port
    }
    $targetSchema = 'ptti.goal90.targets.v1'
    $targetVersion = 'goal90-qa-' + $SanCommit.Substring(0,7)
} else {
    $cinemaTarget = [ordered]@{
        mode = 'DEV_PREVIEW'
        url = "http://127.0.0.1:$CinemaPort/"
        san_root = [IO.Path]::GetFullPath($SanRoot)
        san_head = $SanCommit
        git_exe = [IO.Path]::GetFullPath($GitExe)
        node_exe = [IO.Path]::GetFullPath($NodeExe)
        vite_script = [IO.Path]::GetFullPath($ViteScript)
        port = $CinemaPort
    }
}

$nativeLauncher = Join-Path $NativeRoot 'PTTI-Cinema\launcher.ps1'
$nativePointer = Join-Path $NativeRoot 'PTTI-Cinema\current-preview.json'
$pointer = Get-Content -LiteralPath $nativePointer -Raw | ConvertFrom-Json
if ($pointer.manifest.channel -ne 'preview') { throw 'Native R4 pointer is not a preview channel.' }
$nativeExe = Join-Path (Join-Path $NativeRoot 'PTTI-Cinema') (Join-Path $pointer.folder $pointer.manifest.exe)
$nativeQaDb = Join-Path $NativeRoot 'PTTI-Dev\VideoFirst-R4-Preview\matches.db'

$targetData = [ordered]@{
    schema = $targetSchema
    version = $targetVersion
    cinema = $cinemaTarget
    pro = [ordered]@{
        mode = 'ACCEPTED_LOCAL_RELEASE'
        root = [IO.Path]::GetFullPath($WebProRoot)
        launcher = [IO.Path]::GetFullPath($webLauncher)
        launcher_sha256 = Get-Sha256 $webLauncher
        active_manifest = [IO.Path]::GetFullPath($activeManifest)
        active_manifest_sha256 = Get-Sha256 $activeManifest
        release_id = $active.current
        release_manifest = [IO.Path]::GetFullPath($releaseManifest)
        release_sha256 = Get-Sha256 $releaseManifest
        url = $release.url
    }
    r4 = [ordered]@{
        launcher = [IO.Path]::GetFullPath($nativeLauncher)
        launcher_sha256 = Get-Sha256 $nativeLauncher
        pointer = [IO.Path]::GetFullPath($nativePointer)
        pointer_sha256 = Get-Sha256 $nativePointer
        exe = [IO.Path]::GetFullPath($nativeExe)
        exe_sha256 = Get-Sha256 $nativeExe
        qa_database = [IO.Path]::GetFullPath($nativeQaDb)
    }
}

New-Item -ItemType Directory -Path $candidateRoot | Out-Null
$sourceDir = Join-Path $candidateRoot 'source'
New-Item -ItemType Directory -Path $sourceDir | Out-Null
$programSource = Join-Path $PSScriptRoot 'Start-PTTI-Goal88-QA.cs'
$buildSource = Join-Path $PSScriptRoot 'Build-GOAL88-QA.ps1'
Copy-Item -LiteralPath $programSource -Destination (Join-Path $sourceDir 'Start-PTTI-Goal88-QA.cs')
Copy-Item -LiteralPath $buildSource -Destination (Join-Path $sourceDir 'Build-GOAL88-QA.ps1')
$targetsPath = Join-Path $candidateRoot 'targets.json'
Write-Utf8NoBom $targetsPath (($targetData | ConvertTo-Json -Depth 8) + "`n")
$targetsSha = Get-Sha256 $targetsPath

$generatedSource = Join-Path $sourceDir 'Start-PTTI-Goal88-QA.generated.cs'
$sourceText = [IO.File]::ReadAllText($programSource, [Text.Encoding]::UTF8)
if (-not $sourceText.Contains('__TARGETS_SHA256__')) { throw 'Target-manifest hash pin placeholder is missing.' }
$sourceText = $sourceText.Replace('__TARGETS_SHA256__', $targetsSha)
Write-Utf8NoBom $generatedSource $sourceText

$frameworkDir = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$csc = Join-Path $frameworkDir 'csc.exe'
if (-not (Test-Path -LiteralPath $csc -PathType Leaf)) { throw 'The supported .NET Framework C# compiler is unavailable.' }
$exePath = Join-Path $candidateRoot 'PTTI-Two-Workspaces-QA.exe'
$references = @('/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll','/reference:System.Management.dll')
& $csc /nologo /target:winexe /optimize+ "/out:$exePath" @references $generatedSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exePath -PathType Leaf)) { throw 'The native selector build failed.' }

$release = [ordered]@{
    schema = 'ptti.goal88.selector-candidate.v1'
    version = $targetVersion
    status = 'QA_ONLY'
    selector_source_commit = $SelectorSourceCommit
    selector_source_sha256 = Get-Sha256 $programSource
    host_baseline_commit = $HostBaseCommit
    san_commit = $SanCommit
    san_dev_preview_commit = if ($CinemaMode -eq 'DEV_PREVIEW') { $SanCommit } else { $null }
    cinema_mode = $CinemaMode
    cinema_port = $CinemaPort
    cinema_candidate_version = if ($CinemaMode -eq 'QA_DESKTOP') { $cinemaRelease.version } else { $null }
    cinema_exe_sha256 = if ($CinemaMode -eq 'QA_DESKTOP') { $cinemaExeSha } else { $null }
    cinema_release_sha256 = if ($CinemaMode -eq 'QA_DESKTOP') { $cinemaReleaseSha } else { $null }
    pro_mode = 'ACCEPTED_LOCAL_RELEASE'
    pro_release_id = $active.current
    pro_release_sha256 = Get-Sha256 $releaseManifest
    r4_mode = 'PRESERVED_SEPARATE_NOT_BRIDGED'
    r4_exe_sha256 = Get-Sha256 $nativeExe
    r4_qa_database_present = Test-Path -LiteralPath $nativeQaDb -PathType Leaf
    targets_manifest_sha256 = $targetsSha
    exe_sha256 = Get-Sha256 $exePath
    build_tool = 'Microsoft .NET Framework 4 C# compiler'
    published = $false
    activated = $false
}
Write-Utf8NoBom (Join-Path $candidateRoot 'release.json') (($release | ConvertTo-Json -Depth 6) + "`n")
Write-Host "Candidate created: $candidateRoot"
Write-Host "EXE SHA-256: $($release.exe_sha256)"
Write-Host "Targets SHA-256: $targetsSha"
