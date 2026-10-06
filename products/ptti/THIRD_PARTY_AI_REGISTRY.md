# Third-party AI registry

Checked 2026-10-06. Code licenses do not automatically establish checkpoint or dataset rights; verify the exact artifact before staging it. Research assets stay outside Git, desktop packages and release archives.

| Component | Code / artifact terms | Purpose | Product status | Current evidence |
| --- | --- | --- | --- | --- |
| RacketVision BallTrack | MIT code; frozen checkpoint tracked separately | Ball observations | PRODUCT, v1 frozen RAW | Existing isolated worker and checkpoint; no v1 tuning |
| OpenCV scene histogram | Apache-2.0 | Explainable shot-boundary candidates | EXPERIMENTAL | CPU-only baseline in `backend/vision_v2.py` |
| Grounding DINO | Apache-2.0 code; exact checkpoint terms/revision must be retained | Sparse table/person/referee/scoreboard bootstrap | EXPERIMENTAL, unavailable until isolated runtime and weights are staged | [Code](https://github.com/IDEA-Research/GroundingDINO); [model card](https://huggingface.co/IDEA-Research/grounding-dino-base) |
| MMDetection / RTMDet Tiny | MMDetection code Apache-2.0; official checkpoint is COCO-trained, but its standalone redistribution terms have not been verified | Fixed COCO person-class comparison against the frozen Grounding DINO candidate baseline | PRECHECK ONLY; not installed, not inferred, not a product default | [MMDetection license](https://github.com/open-mmlab/mmdetection); [RTMDet Tiny model-zoo entry](https://github.com/open-mmlab/mmdetection/blob/main/configs/rtmdet/metafile.yml) |
| RT-DETR R18 / Transformers | Model card Apache-2.0; COCO pretrained; Transformers Apache-2.0 | Sparse PERSON observations in an existing isolated worker | EXPERIMENTAL preview candidate; real CUDA inference, not role/generalization validated | [Pinned model card](https://huggingface.co/PekingU/rtdetr_r18vd/tree/ac77a11ff0170a41b771c03264987f8ce2b0d753); SHA below |
| TTI ScoreboardModule | TTI interface only | Future ROI discovery and OCR evidence boundary | NOT_IMPLEMENTED; independent of the current Scene Gate | No detector or OCR dependency staged |
| SAM 2 | Apache-2.0 code/checkpoints per upstream; exact file/revision still required | Prompted object-mask propagation | EXPERIMENTAL, not installed | [Repository](https://github.com/facebookresearch/sam2) |
| MMPose / RTMPose | Apache-2.0 code; model/checkpoint and training-data terms vary | Cropped-player pose observations | EXPERIMENTAL, not installed | [Repository](https://github.com/open-mmlab/mmpose) |
| PaddleOCR | Apache-2.0 code; model terms/revision still required | Scoreboard-ROI text candidates | EXPERIMENTAL, not installed | [Repository](https://github.com/PaddlePaddle/PaddleOCR) |
| MMAction2 | Apache-2.0 code; checkpoint terms vary | PLAY / NON-PLAY context research | RESEARCH_ONLY, not installed | [Repository](https://github.com/open-mmlab/mmaction2) |
| CoTracker | CC-BY-NC components; unsuitable for default commercial product dependency | Point-tracking experiments | RESEARCH_ONLY, disabled | [Repository and license](https://github.com/facebookresearch/co-tracker) |

Dataset boundary: Extended OpenTTGames remains CC BY-NC-SA 4.0 research/non-commercial data and must never be bundled with product distributions.

## RT-DETR R18 pinned artifact (2026-10-06)

- Model ID: `PekingU/rtdetr_r18vd`; revision `ac77a11ff0170a41b771c03264987f8ce2b0d753`.
- Official Hub blob metadata: safetensors 80,904,152 bytes; SHA256 `fe87a5a30f5daf298d10794c7682a63b6107986f97d6a770ba948d89e4340093`; verified locally before model loading.
- `config.json` SHA256 `8493be71f51a1c0a741f8f71ec151039227579379de7bcba047c0470d9320c3c`.
- `preprocessor_config.json` SHA256 `ffb4b9461a1dad746be8f0f9c8330ed7743a1ba5fba4f75c232cd281b3d4c64a`.
- Model type `rt_detr`, architecture `RTDetrForObjectDetection`, class `0: person`. Source has not been modified or fine-tuned.
- Runtime: Python 3.12.14 / PyTorch 2.10.0+cu128 / CUDA 12.8 / Transformers 4.57.6 / NVIDIA RTX 5060 Laptop GPU. Existing vision-v2 packages only; no package upgrade or OpenMMLab installation.
- Code adapter and evaluation scripts live in this repository; model files remain in explicit `PTTI-Dev/vision-v2/models/rtdetr-r18vd`, outside Git and preview packaging.
- RTMDet remains `RTMDET_RUNTIME_BLOCKED`; not deleted, not inferred. RT-DETR is not yet fully product-ready because the scene role resolver fails in crowded/front-on views. R50 not tested: the observed limitation is role association, not missing person detections.
