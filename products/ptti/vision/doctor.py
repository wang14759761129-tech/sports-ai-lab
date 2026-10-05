import json
import platform
import shutil
import subprocess
from .config import VisionConfig, RV_COMMIT

def doctor(config=None):
    config = config or VisionConfig.load()
    result = dict(os=platform.platform(), desktop_python=platform.python_version(),
                  ffmpeg=shutil.which('ffmpeg'), ffprobe=shutil.which('ffprobe'),
                  worker_python=str(config.worker_python),
                  worker_exists=config.worker_python.is_file(), racketvision_commit=None,
                  BallTrack='MISSING', RacketPose='NOT_INSTALLED', TrajPred='NOT_INSTALLED',
                  dataset=(config.dataset_root / 'tabletennis/videos/match1_000.mp4').is_file())
    if (config.runtime_root / '.git').exists():
        result['racketvision_commit'] = subprocess.check_output(
            ['git', '-C', str(config.runtime_root), 'rev-parse', 'HEAD'], text=True).strip()
    if shutil.which('nvidia-smi'):
        result['nvidia'] = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                                         '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()
    if config.worker_python.is_file():
        probe = "import torch,json,platform; print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,cuda_available=torch.cuda.is_available(),gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,arch=torch.cuda.get_arch_list())))"
        try:
            process = subprocess.run([str(config.worker_python), '-c', probe], capture_output=True,
                                     text=True, timeout=60)
            result['worker'] = json.loads(process.stdout) if process.returncode == 0 else {'error': process.stderr[-2000:]}
        except Exception as exc:
            result['worker'] = {'error': str(exc)}
    result['checkpoint'] = (config.model_root / 'balltrack_best.pth').is_file()
    if result.get('worker', {}).get('torch') and result['checkpoint'] and result['racketvision_commit'] == RV_COMMIT:
        result['BallTrack'] = 'INSTALLED_NOT_VALIDATED'
    return result
