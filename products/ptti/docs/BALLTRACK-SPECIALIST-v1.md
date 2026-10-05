# TTI Table-Tennis BallTrack Specialist — bounded experiment v1

Completed result: BALLTRACK_MODEL_IMPROVEMENT_FAILED. Both B and C failed known-evaluation acceptance. See [full results](BALLTRACK-SPECIALIST-v1-RESULTS.md). No final untouched test selected or run. Do not rerun the reproduction commands into this completed experiment directory: existing evidence must remain intact; any new experiment needs a separate directory and identifier.

Release Gate remains HISTORICAL_DB_UNVERIFIED. No Production DB connection, migration, main merge, tag or Release. RacketPose and TrajPred stay prohibited.

TTI_TRACKER_V1 is REJECTED / EXPERIMENTAL_FAILED_TRACKER_V1. Historical code, configs, reports, RAW outputs, images and forensic artifacts are preserved. The default product prediction pipeline remains official RacketVision RAW; specialist checkpoints are experimental and are not selected by the GUI.

## Official training audit

Pinned source: RacketVision c44af2a08524d3cb54d818f19686f4cdea4d2793. Official checkpoint SHA256: 00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342. Reviewed BallTrack README, entire config, train.py, test.py, inference.py, dataset/uball.py, model/tracknet_v3.py, loss_utils.py, BallMetrics, optional COCO metric, visualization hook and utilities. No upstream files edited.

1. **How trained:** checkpoint meta, not the current example config, records max_epochs100, saved epoch47/iter15228, batch_size20, distributed PyTorch/NCCL launcher, Adam lr.001, AMP, cosine scheduling beginning epoch20 (T_max100, eta_min_ratio.1), seed1398426208. Repo example is max_epochs2/batch2/constant scheduler, and must not be presented as checkpoint history. Original GPU count, complete training logs, initial weight history and exact dataset hashes are UNKNOWN. No optimizer state is present; fine-tuning starts a new optimizer, not an exact resume.
2. **Sports:** embedded train/val/test ConcatDataset lists badminton, tabletennis and tennis. A leftover `sport='tennis'` variable does not mean tennis-only training.
3. **Splits:** published pinned tabletennis split is625 train rallies/45matches,69 val rallies/same45matches,86 test rallies/5othermatches. Thus upstream val is not match-disjoint from train. Published badminton374/41/46 rallies, tennis350/38/43. These are current pinned-publication counts; the exact historical training snapshot is UNKNOWN.
4. **Table-tennis proportion:**625/1349 =46.33% of published TRAIN **rallies**. Actual frame/sample/batch/time proportion is UNKNOWN; differently sized rallies make clip share unsuitable as training-sample share.
5. **Input:** four RGB frames ending at annotated frame, plus concatenated RGB median:15channels at512×288; model produces4 sigmoid heatmaps but last_only=True selects final channel. Negative initial indices repeat frame0. Sparse CSV labels are the only supervised samples; no labels fabricated for unannotated frames.
6. **Target:** GT x/y scaled then integer-truncated to model grid; sigma3.5 Gaussian normalized to max1. Coordinates(0,0) yield an all-zero map. Magnitude1. No heatmap interpolation or new architecture.
7. **Visibility:** vis is returned by loader but forward loss ignores it. Zero-coordinate sentinel, not Visibility itself, yields background supervision. The new preparation step rejects invisible rows with nonzero coordinates rather than silently altering labels. BallMetrics likewise infers visibility from coordinates.
8. **Median:** loader prefers match/median.npz, else frame/rally/median.npz. RGB median resized and prepended; values divided by255. Published pinned HF tabletennis/all has csv/racket but no original frames or medians. Derived video JPEGs and GT-free100-frame rally medians are therefore a documented proxy; full official input reproduction is unavailable. A/B/C share that exact proxy.
9. **Augmentation:** model-side mixup=True, alpha.5; lambda drawn Beta(.5,.5), made >=.5; mixes frame tensors and targets with a random batch permutation. No color/brightness/geometry augmentation is implemented in the audited loader. Loss already is focal-style WBCELoss, weighting positive and negative log terms by squared response factors; adding another focal loss would not be the baseline.
10. **Best checkpoint:** embedded save_best='f1', rule greater. message_hub records best_score .9184111099765138 and best_f1_epoch_47.pth; combined-sport validation configured. This is stored metadata, not independently reproduced performance. Current repo example uses Ball/f1. Official BallMetrics uses4model-pixel localization tolerance, TP/TN/FP1(wrong visible location)/FP2(false visible)/FN. Its recall includes FP1 in denominator, unlike TTI visibility recall.

Source references: [official training source](https://github.com/OrcustD/RacketVision/tree/c44af2a08524d3cb54d818f19686f4cdea4d2793/source/BallTrack), [pinned dataset](https://huggingface.co/datasets/linfeng302/RacketVision/tree/85157ca21faa2abca96d837dd2b963738029bcc8/tabletennis), [checkpoint repository](https://huggingface.co/linfeng302/RacketVision-Models/tree/a3760773233a0988c9605259743fbdd87c59d3a3).

## Data hygiene / first ablation

This is a bounded learning experiment, not full625-clip fine-tuning:

- TRAIN: matches20–27, first two official train rallies each (16clips/400annotated samples expected).
- DEV: matches28–31, first up-to-two official val rallies (7clips/175samples expected).
- KNOWN EVALUATION: all existing Development10, Internal Holdout5 and Cross-Match10 (25clips), now exposed. No final-generalization claim.
- FINAL UNTOUCHED TEST: unselected. Only after accepted candidate freeze. All official matches have potential parent checkpoint train/val/test exposure, so a strict model-unseen final test needs independently sourced new matches and trustworthy annotations.

Match IDs are disjoint among roles, verified by CPU-only guards. GT/media have pinned provenance and hashes. Original files are never rewritten; derived JPEGs/medians live in a new ignored experiment directory. No GUI or match database is involved.

A=official parent. B=tabletennis fine-tuning with unchanged TrackNetV3, representation, core WBCELoss and threshold/bbox decoding. C=same parent,seed,LR,epochs,sample budget and uniform-replacement sampler as B, changing only TRAIN hard-negative weights from1 to3. C does not add extra training epochs on top of B. Both use Adam1e-5, batch2,3epochs, upstream mixup. Best epoch chosen only by disjoint DEV official F1. Learning rate/epochs fixed before inspecting specialist KNOWN EVALUATION.

Hard negatives are real local maxima with response>=.5 farther than4model pixels from visible GT, or on annotated negatives. Only TRAIN/DEV mining; only TRAIN manifest drives C sampling. Responses are uncalibrated sigmoid measurements. Crops, GT, candidate, match/frame and sample index retained. Category defaults UNKNOWN pending visual review; no pink/color rule exists.

GT peak rank uses ranked3×3 local maxima, radius5 spatial NMS, nearby radius4model pixels. All surviving positive-response peaks considered, not top128 truncation. Report cumulative rank<=1/4/8/16/32/64, >64 and NO_NEARBY_PEAK separately. Response values are not calibrated probabilities. Fixed match10/001 frame184 is a witness only; it is never trained on or used for model selection.

Official-style baseline uses official UniBallDataset / TrackNetV3 / BallMetrics logic with a coordinate-preservation defect repair on the bounded inputs, with a filename-only OpenCV Unicode shim. It is not an exact full-data test.py reproduction. Its coordinates/resize interpolation may differ from the legacy inference adapter. TTI metrics are reported alongside, and the historical baseline is retained unchanged.

Models are separate under models/racketvision_official and models/tti_tabletennis. Parent original models/balltrack_best.pth retained byte-identical. Provenance records parent/model/config/split SHA, train/dev matches, seed,epochs,best epoch,LR,optimizer,DEV metric,source commits,worker hash,GPU,PyTorch/CUDA and derived input manifest hash. No architecture experiment D or auxiliary verifier is planned in this first ablation.

## Reproduction

```powershell
.venv/Scripts/python.exe scripts/prepare_specialist.py
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py audit
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py prepare
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py baseline
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py train_b
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py evaluate_b
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py train_c
vision_worker/.venv/Scripts/python.exe vision_worker/specialist.py evaluate_c
```

Final Test must remain unselected if candidates fail Known Evaluation acceptance. Never lower thresholds to force a positive gate. No claims about Pilot1C/Pilot2 are changed.


Confirmed loader defect: coor is a view into data_dict and __getitem__ scales it in place. Repeated/oversampled access rescales targets again. TTI wraps each getitem with a coordinate snapshot/restore (finally), identically in A/B/C; generated target and input of the first read remain unchanged. Original source and CSV are untouched. This repair prevents corrupted training supervision and does not change the loss/architecture. CPU tests cover repeated reads and failed-read restoration.
