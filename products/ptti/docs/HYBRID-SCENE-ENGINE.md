# Hybrid Scene Engine — RTMDet Person Preflight

**2026-10-06 continuation:** the RTMDet preflight below is preserved history. Current execution pivots to Transformers-native RT-DETR R18; see [PERSON-DETECTOR-PIVOT.md](PERSON-DETECTOR-PIVOT.md). Do not continue OpenMMLab installation or treat the old intended next step as the current plan. `RTMDET_RUNTIME_BLOCKED` remains recorded.

Status: `PARTIAL`  
Frozen comparison baseline: [GROUNDING_DINO_PLAYER_BASELINE.md](GROUNDING_DINO_PLAYER_BASELINE.md)  
Current source branch: `codex/ptti-v0.2-racketvision`

## Intended detector split

- Grounding DINO remains responsible for coarse table and unusual-object bootstrap.
- Its person output is retained only as the immutable `GROUNDING_DINO_PLAYER_BASELINE` research comparison.
- RTMDet Tiny is the first fixed-class person detector candidate. No RTMDet result has yet been generated, so there is no winning detector and no product-default switch.
- `PlayerRoleResolver` produces cautious near/far/referee/other candidates from the table and person boxes. It never maps to athlete names and leaves role identity `UNKNOWN`.
- The pose adapter accepts a person box only; it does not run RTMPose or claim a pose result.
- `ScoreboardModule` is explicitly `NOT_IMPLEMENTED` and does not block the table/person gate.

## Frozen comparison inputs

Use only the same 20 extracted images from the five official Extended OpenTTGames training videos described in the frozen baseline document. Do not access the official test split. The sample is sparse research data under CC BY-NC-SA 4.0; images and videos stay outside Git and distributable packages.

The baseline manifest SHA256 is `67bc35a5a1570d4610e524141030f1c93aa5b2a8516767f12023d4eb9f75276f`. Preserve it. The baseline has 11/20 frames with opposing screen-side person candidates (55% candidate coverage), with per-match values 1/4, 2/4, 3/4, 4/4, and 1/4. These are not precision/recall because the frames do not yet have human person-box ground truth.

## RTMDet Tiny artifact provenance

- Official config: `configs/rtmdet/rtmdet_tiny_8xb32-300e_coco.py`.
- Official model-zoo checkpoint: `https://download.openmmlab.com/mmdetection/v3.0/rtmdet/rtmdet_tiny_8xb32-300e_coco/rtmdet_tiny_8xb32-300e_coco_20220902_112414-78e30dcc.pth`.
- Upstream identifies COCO as the training/evaluation dataset and publishes this configuration/checkpoint in its model zoo. The checkpoint has not been downloaded in this task; its standalone redistribution terms must be reviewed before any product bundling.
- MMDetection source is Apache-2.0. This does not automatically establish separate checkpoint or training-data rights.

## Runtime preflight and blocker

The desktop environment is Python 3.12.14 / PyTorch 2.10.0+cu128 on an NVIDIA GeForce RTX 5060 Laptop GPU. It has no MMDetection, MMCV, or MMEngine installation. The checked official OpenMMLab MMCV index for `cu128/torch2.10.0` returned 404. An official Windows wheel index for `cu121/torch2.2.0` exposes MMCV 2.2.0, while MMDetection 3.3.0's official compatibility table requires MMCV `<2.2.0`; that combination is not used. No shared environment was modified and no guessed wheel was installed.

The proposed isolated environment root is `%LOCALAPPDATA%\PTTI-Dev\vision-v2-openmmlab`. The required Python/package stack is not installed. A local Python-runtime installation action was rejected by the command execution policy, so the model and checkpoint comparison could not be run. Do not claim RTMDet coverage, runtime, VRAM, or accuracy until the isolated worker has a supported environment and the fixed 20-frame comparison has actually completed.

## TTI contracts available now

`backend/hybrid_scene.py` contains the dependency-free person-candidate schema, a COCO-class-0 prediction adapter, the conservative geometric role candidate resolver, the review-priority helper, a bbox-only future pose input contract, and the explicit unimplemented scoreboard state. These contracts are testable in the desktop environment without importing OpenMMLab.

## Decision

The player gate remains `PLAYER_DETECTION_PARTIAL`; the scene gate remains `SCENE_BOOTSTRAP_PARTIAL`. SAM2 stays locked. The next execution must first provide an isolated, version-compatible OpenMMLab worker and verified checkpoint SHA256, then run and manually review the exact 20 frozen frames against the preserved Grounding DINO outputs.
