param([switch]$Install, [switch]$DownloadSample)
$ErrorActionPreference = 'Stop'
$ProductRoot = Split-Path $PSScriptRoot -Parent
$DesktopPython = Join-Path $ProductRoot '.venv\Scripts\python.exe'
$VisionPython = Join-Path $ProductRoot 'vision_worker\.venv\Scripts\python.exe'
$RuntimeRoot = Join-Path $ProductRoot 'third_party_runtime\racketvision'
$SetupLogs = Join-Path $ProductRoot 'cache\vision-setup'
New-Item -ItemType Directory -Path $SetupLogs -Force | Out-Null
Start-Transcript -Path (Join-Path $SetupLogs ('setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')) | Out-Null
try {
if($Install){
    if(!(Test-Path $RuntimeRoot)){
        git clone https://github.com/OrcustD/RacketVision.git $RuntimeRoot
        if($LASTEXITCODE -ne 0){throw 'RacketVision clone failed'}
    }
    git -C $RuntimeRoot checkout --detach c44af2a08524d3cb54d818f19686f4cdea4d2793
    if($LASTEXITCODE -ne 0){throw 'Pinned checkout failed'}
    if(!(Test-Path $VisionPython)){ & $DesktopPython -m venv (Join-Path $ProductRoot 'vision_worker\.venv') }
    Write-Host 'Installing isolated CUDA 12.8 BallTrack runtime (PyTorch download about 2.7 GiB).'
    & $DesktopPython (Join-Path $PSScriptRoot 'download_torch_wheel.py')
    if($LASTEXITCODE -ne 0){throw 'Official wheel download failed'}
    & $VisionPython -m pip install (Join-Path $ProductRoot 'downloads\torch-2.10.0+cu128-cp312-cp312-win_amd64.whl')
    if($LASTEXITCODE -ne 0){throw 'PyTorch installation failed'}
    & $VisionPython -m pip install -r (Join-Path $ProductRoot 'vision_worker\requirements.txt')
    if($LASTEXITCODE -ne 0){throw 'Worker dependencies failed'}
}
if($DownloadSample){
    Write-Host 'Explicit download: one official rally + sparse GT + BallTrack checkpoint (about 47 MiB).'
    & $DesktopPython (Join-Path $PSScriptRoot 'download_vision_sample.py')
    if($LASTEXITCODE -ne 0){throw 'Fixture download failed; partial files retained'}
}
Push-Location $ProductRoot
try { & $DesktopPython -m vision doctor } finally { Pop-Location }
} finally { Stop-Transcript | Out-Null }
