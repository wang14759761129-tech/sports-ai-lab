"""Lightweight local diagnostic inventory. Never loads weights or dataset labels."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psutil
from fastapi import HTTPException


def guard_debug_inference(device='cuda'):
    if os.environ.get('PTTI_VISION_LAB_DEV_ONLY') != '1':
        return
    if psutil.virtual_memory().available < 3.5 * 1024**3:
        raise HTTPException(503, '受控实验暂停：至少需要 3.5 GiB 可用 RAM，运行中 2 GiB 守卫不变。')
    if device != 'cpu':
        try:
            result = subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],
                                    capture_output=True,text=True,timeout=4,
                                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            free = int(result.stdout.splitlines()[0]) if result.returncode == 0 else 0
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            free = 0
        if free < 3072:
            raise HTTPException(503, '受控 GPU 实验暂停：无法确认至少 3 GiB 空闲显存。')


def debug_allowed(mode):
    return mode in {'development', 'test'}


def inventory(config, product_root, local_root, mode, enabled=False):
    product_root, local_root = Path(product_root), Path(local_root)
    dev = local_root / 'PTTI-Dev'
    specs = [
        ('ball', 'Ball Tracking', config.worker_python, config.model_root / 'balltrack_best.pth', 'vision_worker/balltrack.py', 'BALLTRACK_V1_FROZEN_RAW'),
        ('players', 'Player Tracking / SAM2', dev / 'vision-v2-sam2/venv/Scripts/python.exe', dev / 'vision-v2-sam2/checkpoints/sam2.1_hiera_small.pt', 'vision_worker/anchor_guided_player_tracker.py', 'PARTIAL'),
        ('pose', 'Player Motion / 2D Pose', dev / 'vision-v2-rtmpose/venv/Scripts/python.exe', dev / 'vision-v2-rtmpose/models/rtmpose-m-halpe26.onnx', 'vision_worker/player_motion_rtmpose.py', 'EXPERIMENTAL'),
        ('scene', 'Scene / Grounding DINO', dev / 'vision-v2/venv/Scripts/python.exe', dev / 'vision-v2/models/grounding-dino-base/model.safetensors', 'scripts/run_scene_bootstrap.py', 'PARTIAL'),
        ('person', 'RT-DETR person candidates', dev / 'vision-v2/venv/Scripts/python.exe', dev / 'vision-v2/models/rtdetr-r18vd/model.safetensors', 'backend/person_scene.py', 'PERSON_DETECTOR_PARTIAL'),
    ]
    modules = []
    for identity, name, runtime, model, code, gate in specs:
        modules.append({'id': identity, 'name': name, 'code_exists': (product_root / code).is_file(),
                        'runtime': 'FILE_PRESENT_NOT_PROBED' if runtime.is_file() else 'MISSING',
                        'model': 'FILE_PRESENT_NOT_LOADED' if model.is_file() else 'MISSING',
                        'model_bytes': model.stat().st_size if model.is_file() else None,
                        'research_gate': gate, 'smoke_test': 'NOT_RUN_THIS_SESSION'})
    gpu = {'state': 'UNAVAILABLE', 'cuda': 'NOT_PROBED', 'devices': []}
    if shutil.which('nvidia-smi'):
        try:
            probe = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'],
                                   capture_output=True, text=True, timeout=4,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in probe.stdout.splitlines():
                name, total, free, driver = [part.strip() for part in line.split(',')]
                gpu['devices'].append({'name': name, 'total_mib': int(total), 'free_mib': int(free), 'driver': driver})
            gpu['state'] = 'AVAILABLE' if probe.returncode == 0 and gpu['devices'] else 'ERROR'
        except (OSError, ValueError, subprocess.TimeoutExpired):
            gpu['state'] = 'ERROR'
    available = psutil.virtual_memory().available
    return {'environment': mode, 'debug_available': debug_allowed(mode),
            'debug_enabled': bool(enabled and debug_allowed(mode)), 'status': 'RESEARCH_PREVIEW',
            'python': sys.version.split()[0], 'available_ram_bytes': available,
            'controlled_inference_resource_ready': available >= 3.5 * 1024**3,
            'gpu': gpu, 'modules': modules,
            'policy': {'weights_loaded': False, 'dataset_labels_read': False, 'rights_checks': 'UNCHANGED',
                       'analysis_binding': 'SOURCE_SHA_AND_TIMELINE_REQUIRED', 'remote_download': False}}
