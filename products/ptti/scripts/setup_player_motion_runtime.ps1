param(
    [string]$TrackingJobId = $env:PTTI_PLAYER_MOTION_TRACKING_JOB_ID
)

$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'PTTI-Dev\vision-v2-rtmpose'
$python = Join-Path $runtimeRoot 'venv\Scripts\python.exe'
$samPython = Join-Path $env:LOCALAPPDATA 'PTTI-Dev\vision-v2-sam2\venv\Scripts\python.exe'
$cudaDlls = Join-Path $env:LOCALAPPDATA 'PTTI-Dev\vision-v2-sam2\venv\Lib\site-packages\torch\lib'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$revision = 'cc359b924ec441b3563fb71f8cd012e576b8d262'

if (-not (Test-Path -LiteralPath $python)) {
    if (-not (Test-Path -LiteralPath $samPython)) {
        throw '找不到可用的 Python 3.12 基础运行时；没有修改任何现有环境。'
    }
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    & $samPython -m venv (Join-Path $runtimeRoot 'venv')
    if ($LASTEXITCODE -ne 0) { throw '创建隔离姿态环境失败。' }
}

& $python -m pip install --prefer-binary --timeout 180 --retries 6 -r (Join-Path $root 'scripts\requirements-player-motion-runtime.txt')
if ($LASTEXITCODE -ne 0) { throw '安装锁定的姿态运行依赖失败。' }
& $python -m pip install --no-deps --force-reinstall "git+https://github.com/Tau-J/rtmlib.git@$revision"
if ($LASTEXITCODE -ne 0) { throw '安装固定 RTMLib 上游提交失败。' }

if (Test-Path -LiteralPath $cudaDlls) {
    $env:PATH = "$cudaDlls;$env:PATH"
}
$env:PTTI_PRODUCT_ROOT = $root
if (-not $TrackingJobId) {
    Write-Output '依赖已安装。设置 PTTI_PLAYER_MOTION_TRACKING_JOB_ID 后，再次运行以执行真实单帧 GPU 检查。'
    exit 0
}
& $python (Join-Path $root 'vision_worker\probe_rtmpose_single_frame.py') --tracking-job-id $TrackingJobId
if ($LASTEXITCODE -ne 0) { throw '真实单帧 RTMPose 检查失败；模块不会被标记为 CUDA 就绪。' }
