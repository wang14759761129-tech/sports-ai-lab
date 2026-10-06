# Third-party AI registry

Checked 2026-10-06. Code licenses do not automatically establish checkpoint or dataset rights; verify the exact artifact before staging it. Research assets stay outside Git, desktop packages and release archives.

| Component | Code / artifact terms | Purpose | Product status | Current evidence |
| --- | --- | --- | --- | --- |
| RacketVision BallTrack | MIT code; frozen checkpoint tracked separately | Ball observations | PRODUCT, v1 frozen RAW | Existing isolated worker and checkpoint; no v1 tuning |
| OpenCV scene histogram | Apache-2.0 | Explainable shot-boundary candidates | EXPERIMENTAL | CPU-only baseline in `backend/vision_v2.py` |
| Grounding DINO | Apache-2.0 code; exact checkpoint terms/revision must be retained | Sparse table/person/referee/scoreboard bootstrap | EXPERIMENTAL, unavailable until isolated runtime and weights are staged | [Code](https://github.com/IDEA-Research/GroundingDINO); [model card](https://huggingface.co/IDEA-Research/grounding-dino-base) |
| MMDetection / RTMDet Tiny | MMDetection code Apache-2.0; official checkpoint is COCO-trained, but its standalone redistribution terms have not been verified | Fixed COCO person-class comparison against the frozen Grounding DINO candidate baseline | PRECHECK ONLY; not installed, not inferred, not a product default | [MMDetection license](https://github.com/open-mmlab/mmdetection); [RTMDet Tiny model-zoo entry](https://github.com/open-mmlab/mmdetection/blob/main/configs/rtmdet/metafile.yml) |
| TTI ScoreboardModule | TTI interface only | Future ROI discovery and OCR evidence boundary | NOT_IMPLEMENTED; independent of the current Scene Gate | No detector or OCR dependency staged |
| SAM 2 | Apache-2.0 code/checkpoints per upstream; exact file/revision still required | Prompted object-mask propagation | EXPERIMENTAL, not installed | [Repository](https://github.com/facebookresearch/sam2) |
| MMPose / RTMPose | Apache-2.0 code; model/checkpoint and training-data terms vary | Cropped-player pose observations | EXPERIMENTAL, not installed | [Repository](https://github.com/open-mmlab/mmpose) |
| PaddleOCR | Apache-2.0 code; model terms/revision still required | Scoreboard-ROI text candidates | EXPERIMENTAL, not installed | [Repository](https://github.com/PaddlePaddle/PaddleOCR) |
| MMAction2 | Apache-2.0 code; checkpoint terms vary | PLAY / NON-PLAY context research | RESEARCH_ONLY, not installed | [Repository](https://github.com/open-mmlab/mmaction2) |
| CoTracker | CC-BY-NC components; unsuitable for default commercial product dependency | Point-tracking experiments | RESEARCH_ONLY, disabled | [Repository and license](https://github.com/facebookresearch/co-tracker) |

Dataset boundary: Extended OpenTTGames remains CC BY-NC-SA 4.0 research/non-commercial data and must never be bundled with product distributions.
