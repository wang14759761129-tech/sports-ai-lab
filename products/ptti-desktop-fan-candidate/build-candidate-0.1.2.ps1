$ErrorActionPreference = 'Stop'

$candidateSource = $PSScriptRoot
$fanRepo = 'C:\PTTI-Worktrees\web-goal14-fan-mvp'
$fanProject = Join-Path $fanRepo 'products\ptti-web'
$releaseRoot = '<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL16'
$version = '0.1.2-fan-072c57a'
$finalPackage = Join-Path $releaseRoot $version
$expectedFanCommit = '072c57a4d16c4e7fead452a22eb378f2a7a9f633'
$expectedCatalog = '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'
$expectedMediaIndex = '669895cc046e49452a82370f84726ca6ac05dce8ca474cf24feb191329844837'
$expectedMainMediaManifest = 'c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004'
$selector = '<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1'
$nativeLauncher = '<LOCAL_USER_ROOT>\PTTI\NativeRoot\PTTI-Cinema\launcher.ps1'
$r4Exe = '<LOCAL_USER_ROOT>\PTTI\NativeRoot\PTTI-Cinema\versions\5cc753886b11-b2623e68\PTTI-Video-First-R4-Preview.exe'
$python = '<LOCAL_USER_ROOT>\OneDrive\文档\ChatGPT\table tennis intelligent\.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $fanProject -PathType Container)) { throw 'Pinned Fan source project is unavailable.' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Pinned desktop build Python is unavailable.' }
if (Test-Path -LiteralPath $finalPackage) { throw 'The new version folder already exists; refusing to overwrite it.' }

$fanHead = (git -C $fanRepo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $fanHead -ne $expectedFanCommit) { throw "Fan source identity mismatch: $fanHead" }
$fanStatus = @(git -C $fanRepo status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $fanStatus.Count -gt 0) { throw 'Pinned Fan source is not a clean committed tree.' }
if ((Get-FileHash -LiteralPath (Join-Path $fanProject 'public\data\match-library-strict-public.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedCatalog) { throw 'Public catalog hash differs from the release pin.' }
if ((Get-FileHash -LiteralPath (Join-Path $fanProject 'src\approved-public-media.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedMediaIndex) { throw 'GOAL16 public media index differs from the release pin.' }
$mainMedia = Join-Path $fanProject 'scripts\fixtures\goal16-media\main-public-media-v0.2.json'
if ((Get-FileHash -LiteralPath $mainMedia -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedMainMediaManifest) { throw 'Pinned Main v0.2 media manifest differs from the release pin.' }

$expectedRuntimeFiles = @(
    @{ Path = $selector; Hash = '277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1' },
    @{ Path = $nativeLauncher; Hash = 'FA426AA15ACCA4E4308475A437D8F20A5CFCFA55B473296A6F841FF75683B969' },
    @{ Path = $r4Exe; Hash = 'FCA3BDF09A96E3D95A1F676EA63793909057C6E8A1D95D0A9274D3C3FC6738AB' }
)
foreach ($item in $expectedRuntimeFiles) {
    if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) { throw "Pinned runtime file is missing: $($item.Path)" }
    if ((Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash -ne $item.Hash) { throw "Pinned runtime file hash differs: $($item.Path)" }
}

$protectedPorts = @(4174, 4183, 4199)
$portOwnersBefore = @{}
foreach ($port in $protectedPorts) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Where-Object LocalAddress -eq '127.0.0.1')
    if ($listeners.Count -ne 1) { throw "Expected one loopback listener on protected port $port; build stopped." }
    $portOwnersBefore[$port] = $listeners[0].OwningProcess
}

Push-Location $fanProject
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "GOAL16 production build failed with exit code $LASTEXITCODE." }
    npm.cmd run check:goal15
    if ($LASTEXITCODE -ne 0) { throw "GOAL15 checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-catalog
    if ($LASTEXITCODE -ne 0) { throw "Fan catalog checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-navigation
    if ($LASTEXITCODE -ne 0) { throw "Fan navigation checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-gold
    if ($LASTEXITCODE -ne 0) { throw "Fan Gold checks failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}

Push-Location $candidateSource
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Native QA isolation checks failed; no candidate package was created.' }
} finally {
    Pop-Location
}

$pythonInfo = & $python -c "import sys, importlib.metadata as md; print(sys.version.split()[0]+'|'+md.version('pywebview')+'|'+md.version('pyinstaller'))"
if ($LASTEXITCODE -ne 0 -or $pythonInfo -ne '3.12.14|6.2.1|6.22.3') { throw "Unexpected desktop build tool versions: $pythonInfo" }

$buildRoot = Join-Path $releaseRoot ('build\' + $version)
$stageRoot = Join-Path $buildRoot 'staging'
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
$package = Join-Path $stageRoot ([guid]::NewGuid().ToString('N'))

$fanHeadAfter = (git -C $fanRepo rev-parse HEAD).Trim()
if ($fanHeadAfter -ne $expectedFanCommit) { throw 'Fan source changed during build; candidate packaging stopped.' }
New-Item -ItemType Directory -Path $package | Out-Null
Copy-Item -LiteralPath (Join-Path $candidateSource 'desktop-shell.html') -Destination (Join-Path $package 'desktop-shell.html')
$fanOutput = Join-Path $package 'fan-universe'
New-Item -ItemType Directory -Path $fanOutput | Out-Null
Get-ChildItem -LiteralPath (Join-Path $fanProject 'dist') | Copy-Item -Destination $fanOutput -Recurse
$sourceOutput = Join-Path $package 'source'
New-Item -ItemType Directory -Path $sourceOutput | Out-Null
Copy-Item -LiteralPath (Join-Path $candidateSource 'src\desktop_host.py') -Destination (Join-Path $sourceOutput 'desktop_host.py')

$tempDist = Join-Path $buildRoot 'dist'
$tempWork = Join-Path $buildRoot 'pyinstaller'
$tempSpec = Join-Path $buildRoot 'spec'
$hostSource = Join-Path $candidateSource 'src\desktop_host.py'
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name PTTI-Desktop-Fan --collect-all webview --hidden-import sqlite3 --hidden-import _sqlite3 --distpath $tempDist --workpath $tempWork --specpath $tempSpec $hostSource
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
New-Item -ItemType Directory -Path (Join-Path $package 'host') | Out-Null
Get-ChildItem -LiteralPath (Join-Path $tempDist 'PTTI-Desktop-Fan') | Copy-Item -Destination (Join-Path $package 'host') -Recurse

$files = [ordered]@{}
Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($package.Length + 1).Replace('\', '/')
    $files[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = [ordered]@{
    schema = 'ptti.desktop-fan.release.v1'
    version = $version
    fan_commit = $expectedFanCommit
    catalog_sha256 = $expectedCatalog
    fan_media_index_sha256 = $expectedMediaIndex
    main_media_manifest_sha256 = $expectedMainMediaManifest
    desktop_host_source_sha256 = $files['source/desktop_host.py']
    native_selector_sha256 = $expectedRuntimeFiles[0].Hash
    native_launcher_sha256 = $expectedRuntimeFiles[1].Hash
    r4_exe_sha256 = $expectedRuntimeFiles[2].Hash
    native_qa_database_mode = 'sqlite-read-only-backup-v1'
    web_engine = 'WebView2 via pywebview 6.2.1'
    signature_status = 'UNSIGNED_CANDIDATE'
    files = $files
}
$manifestPath = Join-Path $package 'release.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()

$hostSourceDirectory = Join-Path $candidateSource 'src'
$verifyCode = "import sys; sys.path.insert(0, r'$hostSourceDirectory'); from pathlib import Path; from desktop_host import verify_package; print(verify_package(Path(sys.argv[1]))['version'])"
$verifiedVersion = & $python -c $verifyCode $package
if ($LASTEXITCODE -ne 0 -or $verifiedVersion.Trim() -ne $version) { throw 'Staged candidate package failed its runtime manifest verification.' }
if (Test-Path -LiteralPath $finalPackage) { throw 'The final version folder appeared during the build; staged package was not activated.' }
Move-Item -LiteralPath $package -Destination $finalPackage
Set-Content -LiteralPath (Join-Path $releaseRoot ($version + '.release-json.sha256')) -Value $manifestHash -Encoding ascii
$verifiedVersion = & $python -c $verifyCode $finalPackage
if ($LASTEXITCODE -ne 0 -or $verifiedVersion.Trim() -ne $version) { throw 'Published candidate folder failed its runtime manifest verification.' }

foreach ($port in $protectedPorts) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Where-Object LocalAddress -eq '127.0.0.1')
    if ($listeners.Count -ne 1 -or $listeners[0].OwningProcess -ne $portOwnersBefore[$port]) { throw "Protected port $port changed owner during build; this script did not restart the service." }
}

[pscustomobject]@{
    Package = $finalPackage
    Version = $version
    FanCommit = $expectedFanCommit
    FanMediaIndexSHA256 = $expectedMediaIndex
    FileCount = $files.Count
    ManifestSHA256 = $manifestHash
    SignatureStatus = 'UNSIGNED_CANDIDATE'
    HostExe = Join-Path $finalPackage 'host\PTTI-Desktop-Fan.exe'
    ActiveSelectorChanged = $false
} | Format-List
