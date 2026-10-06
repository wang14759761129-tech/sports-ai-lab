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
            ['git', '-C', str(config.runtime_root), 'rev-parse', 'HEAD'], text=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).strip()
    if shutil.which('nvidia-smi'):
        result['nvidia'] = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                                         '--format=csv,noheader'], capture_output=True, text=True,
                                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.strip()
    if config.worker_python.is_file():
        probe = "import torch,json,platform,importlib.util; names=['cv2','transformers','groundingdino','sam2','mmpose','mmcv','paddleocr','paddle','mmaction','cotracker']; modules={n:importlib.util.find_spec(n) is not None for n in names}; cuda=torch.cuda.is_available(); mem=torch.cuda.mem_get_info(0) if cuda else None; print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,cuda_available=cuda,gpu=torch.cuda.get_device_name(0) if cuda else None,free_vram_bytes=mem[0] if mem else None,total_vram_bytes=mem[1] if mem else None,arch=torch.cuda.get_arch_list(),modules=modules)))"
        try:
            process = subprocess.run([str(config.worker_python), '-c', probe], capture_output=True,
                                     text=True, timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result['worker'] = json.loads(process.stdout) if process.returncode == 0 else {'error': process.stderr[-2000:]}
        except Exception as exc:
            result['worker'] = {'error': str(exc)}
    result['checkpoint'] = (config.model_root / 'balltrack_best.pth').is_file()
    from .models import VisionModelManager
    result['models'] = VisionModelManager(config).status()
    if result.get('worker', {}).get('torch') and result['checkpoint'] and result['racketvision_commit'] == RV_COMMIT:
        result['BallTrack'] = 'INSTALLED_NOT_VALIDATED'
    return result
