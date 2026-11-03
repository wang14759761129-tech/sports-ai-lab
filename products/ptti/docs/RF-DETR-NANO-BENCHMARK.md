# RF-DETR Nano pretrained trial — NO_VALUE for current replacement

Package 1.11.2, source tag/commit `7433d5919d0f7e72cc6cb78663e0a731afd499e0`.
Core Nano code and published weights: Apache-2.0. No Plus/XL/2XL, training extras, fine-tuning or architecture changes.
Official checkpoint URL: `https://storage.googleapis.com/rfdetr/nano_coco/checkpoint_best_regular.pth`.
Bytes 366287238; upstream MD5 `fb6504cce7fbdc783f7a46991f07639f` verified before loading.
SHA256 `d8d6b9ee57d4d0ed2b1f305163624712a0532cb7bce0c747317984fc5457440d`.
Nano constructor/config and safe official checkpoint load succeeded. Default 384 input, FP32, threshold .30 fixed before running.

## Valid comparison

Five different RacketVision official TRAIN matches: match20/001, match21/002, match22/002, match23/002, match24/002.
All 25 native sparse GT frames per clip: 125 reviewed frames, 115 visible, 10 absent.
Manifest R1 SHA `4d28ee9e9c22dacdcf66650c4524d4fa06f49a0a62f6eda29bcc8955c0078b8f`.
Real original video frames decoded; no GT crop or oracle position is fed to either model.
RacketVision uses the existing frozen official RAW cache on exactly those source frames. Neither output uses a tracker.
All RF-DETR sports-ball candidates retained; extra/incorrectly localized targets count as FP.

| Metric | Frozen RacketVision RAW | RF-DETR Nano |
|---|---:|---:|
| Presence / visible frames | 114/115 | 12/115 |
| Localization within 20px | 114/115 (99.13%) | 9/115 (7.83%) |
| False detections under localization metric | 0 | 6 |
| Mean center error on co-visible frames | 2.279 px | 58.123 px |
| Median | 2.000 px | 3.039 px |
| P95 | 5.099 px | 284.173 px |
| >20 / >50 / >100px | 0 / 0 / 0 | 3 / 3 / 2 |

Per-clip Nano localization recall: 8/19, 1/25, 0/23, 0/24, 0/24.
Sparse annotations cannot establish full-video FP/min, FN/min, trajectory quality or downstream Raw Hit accuracy.
Those fields are explicitly NOT_EVALUABLE, not zero. No reviewed scene-stratum results are claimed.
Known TRAIN data is not untouched generalization evidence. Current-data deployment value is poor;
this does not prove that a separately trained future RF-DETR model is inherently incapable.
No fine-tuning proposal is justified by this very weak pretrained result this round.

## Runtime and corrections

Isolated Python 3.12.14; torch 2.10.0+cu128, torchvision 0.25.0+cu128.
The valid accuracy run used CPU, two CPU threads, to preserve available RAM on the current workstation.
Predict-only throughput 5.50 sampled frames/s, 181.67 ms/frame; cold imports/model load 16.40s;
decode 10.38s. Peak process working set 1.40 GiB; minimum available system RAM 2.48 GiB.
No GPU is represented as used by this corrected accuracy run.

An earlier CUDA run confirmed the model could load/run on RTX 5060 Laptop, but one attempt stopped on resource protection.
A subsequent CUDA comparison incorrectly used contiguous class-name index 32 as a sparse COCO class ID.
Its claimed zero sports-ball detections and all derived accuracy reports are INVALID and superseded, not deleted.
The corrected adapter selects official `detections.data['class_name']`; sports-ball native ID is 37.
Sparse-ID/contiguous-name mismatch now has a regression test. The rerun kept the same checkpoint, data and threshold;
it corrected an adapter bug, not a model/threshold tuning experiment.

Valid report: `%LOCALAPPDATA%/PTTI-Dev/technology-foundation/rf-detr-comparison-corrected-coco.json` and `.html`.
Original attempted results remain alongside an explicit attempt-status index. None are packaged or used to advance gates.

Decision: **NO_VALUE / HOLD / E_REJECT for pretrained Nano as a BallTrack replacement**.
Official RAW remains frozen. The common adapter/benchmark infrastructure remains useful for another justified candidate.

Sources: [official RF-DETR](https://github.com/roboflow/rf-detr),
[pinned COCO mapping](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/assets/coco_classes.py),
[pinned model weights](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/assets/model_weights.py).
