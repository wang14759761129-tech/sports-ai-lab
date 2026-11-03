import os
from pathlib import Path
from dataclasses import dataclass

RV_COMMIT = 'c44af2a08524d3cb54d818f19686f4cdea4d2793'
DATA_REVISION = '85157ca21faa2abca96d837dd2b963738029bcc8'
MODEL_REVISION = 'a3760773233a0988c9605259743fbdd87c59d3a3'
PIPELINE_VERSION = '0.2.0-experimental-1'

@dataclass
class VisionConfig:
    dataset_root: Path
    model_root: Path
    cache_root: Path
    output_root: Path
    runtime_root: Path
    worker_python: Path

    @classmethod
    def load(cls):
        product = Path(__file__).resolve().parents[1]
        root = Path(os.environ.get('PTTI_VISION_HOME', product))
        def location(name, default):
            return Path(os.environ.get('PTTI_VISION_' + name, root / default)).resolve()
        return cls(location('DATASET_ROOT', 'datasets/racketvision'),
                   location('MODEL_ROOT', 'models'), location('CACHE_ROOT', 'cache/vision'),
                   location('OUTPUT_ROOT', 'outputs/vision'),
                   location('RUNTIME_ROOT', 'third_party_runtime/racketvision'),
                   location('PYTHON', 'vision_worker/.venv/Scripts/python.exe'))
