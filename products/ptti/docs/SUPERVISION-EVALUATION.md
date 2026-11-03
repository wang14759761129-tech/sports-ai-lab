# Supervision trial — measured, not adopted

Pinned package 0.30.8; official source tag/commit `2c261cf98f2d412b7f87f6052b21b24019f09a96`; MIT.
Real input: Extended OpenTTGames TRAIN game_1, first two seconds, 240 source frames at 120 FPS.
Both rendering paths use the same 178 visible frozen BallTrack observations, identical coordinates and gap resets.
Comparison is current OpenCV drawing logic versus Supervision Detections + TraceAnnotator + CircleAnnotator
in one isolated runtime. It is a visualization microbenchmark, not end-to-end inference or mask tracking.

| Measurement | Existing drawing logic | Supervision |
|---|---:|---:|
| Measured adapter body nonblank LOC | 10 | 10 |
| Render time for 240 frames | 0.02498 s | 0.06158 s |
| Pixel difference before video encoding | 0 | 0 |

Saved code = 0 LOC for this operation; Supervision also needs container/setup/dependency glue.
The measured difference is tiny relative to inference/encoding, but it proves no performance benefit.
The fresh environment has ~409 MB logical installed dependencies, including shared NumPy/OpenCV/PyAV/Matplotlib/SciPy.
This is not the incremental size of adding Supervision to a worker already containing some dependencies.
Actual source generator, video sink, decoded frame count and encoded MP4 outputs worked; representative overlay visually inspected.
The first 60-second test window had no ball observations and was excluded as an uninformative visualization trial.
All reports/artifacts are retained locally rather than overwritten.

Decision: **TRIAL / B_BENCHMARK**, not ADOPT. Further value must come from reducing genuinely repetitive
multi-object/mask/zone glue, which was not demonstrated here. No product architecture was changed.

Reproducibility: new isolated `uv` project, complete lock, repeated locked sync and fresh-environment package comparison.
Use the copied `supervision-pyproject.toml` as `pyproject.toml` and `supervision-uv.lock` as `uv.lock`
in a separate research project; select the intended Python with `uv sync --python <3.12 interpreter> --locked`.
Do not run sync against any validated desktop/BallTrack/SAM2/Pose environment.

Report: `%LOCALAPPDATA%/PTTI-Dev/technology-foundation/supervision-v2-ball-visible/report.json`.
Video: same folder `supervision-overlay.mp4`. Data is CC BY-NC-SA 4.0; no product or Git redistribution.

Source: [Supervision repository](https://github.com/roboflow/supervision), [uv lock/sync](https://docs.astral.sh/uv/concepts/projects/sync/).
