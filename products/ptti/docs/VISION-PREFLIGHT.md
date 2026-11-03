# v0.2 preflight — 2026-10-05

- Starting clean branch main, commit `2e709019911384b103124dc938beee72aa1deef5`; stable annotated release `ptti-v0.1.2` preserved.
- Python 3.12/FastAPI/SQLite backend, React 19/TypeScript/Vite frontend, pywebview/PyInstaller desktop, pytest; existing CSV → evidence-aware analytics → JSON/HTML works. There was no active video pipeline or CLI.
- Original 50 product tests remain in `tests/`; pytest now explicitly excludes optional upstream runtime tests (otherwise upstream RacketPose test scripts require torch in the desktop environment).
- NVIDIA RTX 5060 Laptop GPU, driver 616.64, 8151 MiB VRAM; FFmpeg/ffprobe available.
- Integration risk: legacy upstream PyTorch 2.1/CUDA 12.1 predates this GPU. Use an isolated PyTorch 2.10/CUDA 12.8 worker, no MMCV until BallTrack validation is complete.
- Official API: `BallInferencer(cfg_path, ckpt_path, device, thre, batchsize)` takes extracted JPG paths and median.npz. Original inference CLI accepts a split, not an arbitrary single video.
- Verified source discrepancy: `_preprocess_batch` uses `range(i-seq_len,i)` yet outputs `Frame=i`; training dataset history ends at `fid`. TTI's external subclass includes the labelled current frame. Upstream checkout is unchanged.
- The actual GT CSV is sparse, not one label per video frame. Unannotated frames must never be counted as false detections / negatives. First benchmark reports annotated-frame visibility and co-visible localization errors, not official F1 or PASS.
- Scope: observation first, no tactical inference. Existing Protocol v0.3 / Pilot 1C / Pilot 2 conclusions remain unchanged.
