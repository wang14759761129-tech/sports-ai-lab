# PTTI current technology stack — 2026-10-07

Audited product baseline: `1052321db6887af5db4417aeaabb46124e9ad8f6`.
Evidence: actual requirements, package metadata, worker sources, saved GPU runs, frontend package.json and build scripts.
Local machine inventory: `%LOCALAPPDATA%/PTTI-Dev/technology-foundation/stack_inventory.json`.
Five existing product/vision Python environments plus four isolated research/rebuild environments were inventoried.

| Layer | Actual implementation | Status | Evidence / limitation |
|---|---|---|---|
| Video | FFmpeg/FFprobe, streaming OpenCV decode, 60-second worker chunks | USED | Full DEV 334,959 frames, 94 complete chunks; source PTS recorded |
| Ball | pinned RacketVision Official BallTrack, torch 2.10.0+cu128 | FROZEN | BALLTRACK_V1_FROZEN_RAW; `vision_worker/balltrack.py`; checkpoint SHA `00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342` |
| Scene | isolated Grounding DINO base through Transformers | EXPERIMENTAL | real table coarse boxes; not a reliable scoreboard system |
| Person | PekingU RT-DETR R18vd, Transformers/CUDA | EXPERIMENTAL | real GPU person detections; identity/role ambiguity remains |
| Masks | SAM 2.1 Hiera Small, isolated PyTorch worker | EXPERIMENTAL | anchor-guided multi-object propagation; player gate PARTIAL |
| Pose | RTMPose-m Halpe26, RTMLib 0.0.10, ONNX Runtime GPU 1.26.0 | RESEARCH_ONLY | CUDA provider verified; 84% Near / 72% Far clip coverage, checkpoint license unresolved |
| Desktop | React 19, TypeScript 5.9, Vite 7, Recharts 3, pywebview 6.2.1 | USED | declared frontend versions; native interaction still needs manual acceptance where automation cannot enumerate |
| API | FastAPI 0.142.2, Uvicorn 0.54.0, Pydantic 2.13.5 | USED | product requirements and API tests |
| Database | SQLite match stores; immutable JSON/JSONL/CSV evidence and manifests | USED | Production/Development/Test fail-closed separation; Production history remains unverified |
| Hit v0.1 | evidence-fusion local candidate baseline | LEGACY | historical preview and reports retained |
| Hit v0.2 | raw generator, temporal clustering, sequence decoder, review mode | EXPERIMENTAL | frozen draft config; full DEV measured, no full-video player evidence yet |
| Packaging | PyInstaller 6.22.3, separate Windows preview artifacts | USED | weights/data excluded; no new package needed for research foundation |
| Tests | pytest 9.1.1, httpx 0.28.1, TypeScript/Vite production build | USED | prior 360 tests; new benchmark tests added separately |
| Development | Python 3.12.14, venv/pip, per-worker requirements | USED | existing environments retained without package changes |
| New research tooling | uv 0.12.23, Ruff 0.16.10 | EXPERIMENTAL | tools-env only; no repository-wide migration/formatting |

Existing environments: `products/ptti/.venv`, `products/ptti/vision_worker/.venv`,
`PTTI-Dev/vision-v2/venv`, `PTTI-Dev/vision-v2-sam2/venv`, `PTTI-Dev/vision-v2-rtmpose/venv`.
New workers live under `PTTI-Dev/technology-foundation/`. Models are staged, not kept together in GPU memory.
No Docker command or standard Docker Desktop executable was found; WSL reports not installed.
No CVAT deployment is represented as installed or tested.

The experiment must not modify desktop requirements, validated worker environments, BallTrack/Hit configs,
main, ptti-v0.1.2, Production DB or locked calibration/holdout/TEST assets.
