$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$fanProject = Join-Path $repo 'products\ptti-web'
$candidateSource = $PSScriptRoot
$releaseRoot = '<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL16'
$version = '0.1.1-fan-5678d96'
$package = Join-Path $releaseRoot $version
$expectedFanCommit = '5678d96eac35bdcc886faefc2ac9076b4d934b57'
$expectedCatalog = '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'
$catalogPath = Join-Path $fanProject 'public\data\match-library-strict-public.json'
$python = '<LOCAL_USER_ROOT>\OneDrive\文档\ChatGPT\table tennis intelligent\.venv\Scripts\python.exe'
$repoHead = (git -C $repo rev-parse HEAD).Trim()
git -C $repo merge-base --is-ancestor $expectedFanCommit $repoHead
if ($LASTEXITCODE -ne 0) { throw 'Expected Fan source commit is not an ancestor of candidate HEAD.' }
if ((Get-FileHash -LiteralPath $catalogPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedCatalog) { throw 'Fan public catalog hash changed; refusing to build.' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Verified local Python environment is unavailable.' }
if (Test-Path -LiteralPath $package) { throw 'Versioned candidate package already exists; refusing to overwrite it.' }

Push-Location $fanProject
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Fan production build failed with exit code $LASTEXITCODE." }
    npm.cmd run check:goal15
    if ($LASTEXITCODE -ne 0) { throw "GOAL15 checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-catalog
    if ($LASTEXITCODE -ne 0) { throw "Fan catalog checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-navigation
    if ($LASTEXITCODE -ne 0) { throw "Fan navigation checks failed with exit code $LASTEXITCODE." }
    npm.cmd run check:fan-gold
    if ($LASTEXITCODE -ne 0) { throw "Fan gold checks failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}

$pythonInfo = & $python -c "import sys, importlib.metadata as md; print(sys.version.split()[0]+'|'+md.version('pywebview')+'|'+md.version('pyinstaller'))"
if ($LASTEXITCODE -ne 0) { throw 'Python desktop build tools could not be inspected.' }
if ($pythonInfo -ne '3.12.14|6.2.1|6.22.3') { throw "Unexpected desktop build tool versions: $pythonInfo" }

New-Item -ItemType Directory -Force -Path $package | Out-Null
Copy-Item -LiteralPath (Join-Path $candidateSource 'desktop-shell.html') -Destination (Join-Path $package 'desktop-shell.html')
$fanOutput = Join-Path $package 'fan-universe'
New-Item -ItemType Directory -Force -Path $fanOutput | Out-Null
Get-ChildItem -LiteralPath (Join-Path $fanProject 'dist') | Copy-Item -Destination $fanOutput -Recurse
$tempDist = Join-Path $releaseRoot 'build\dist'
$tempWork = Join-Path $releaseRoot 'build\pyinstaller'
$hostSource = Join-Path $candidateSource 'src\desktop_host.py'
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name PTTI-Desktop-Fan --collect-all webview --distpath $tempDist --workpath $tempWork --specpath (Join-Path $releaseRoot 'build\spec') $hostSource
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
New-Item -ItemType Directory -Force -Path (Join-Path $package 'host') | Out-Null
Get-ChildItem -LiteralPath (Join-Path $tempDist 'PTTI-Desktop-Fan') | Copy-Item -Destination (Join-Path $package 'host') -Recurse

$files = [ordered]@{}
Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($package.Length + 1).Replace('\','/')
    $files[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = [ordered]@{
    schema = 'ptti.desktop-fan.release.v1'
    version = $version
    fan_commit = $expectedFanCommit
    catalog_sha256 = $expectedCatalog
    main_source_commit = 'eb0a52af32eaaf26dfd39cf1ce5f321e24a1adac'
    web_engine = 'WebView2 via pywebview 6.2.1'
    native_selector_sha256 = '277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1'
    signature_status = 'UNSIGNED_CANDIDATE'
    files = $files
}
$manifestPath = Join-Path $package 'release.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $releaseRoot ($version + '.release-json.sha256')) -Value $manifestHash -Encoding ascii
$size = (Get-ChildItem -LiteralPath $package -Recurse -File | Measure-Object -Property Length -Sum).Sum
[pscustomobject]@{Package=$package;Version=$version;FileCount=$files.Count;PackageBytes=$size;ManifestSHA256=$manifestHash;HostExe=(Join-Path $package 'host\PTTI-Desktop-Fan.exe')} | Format-List
