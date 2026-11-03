# SAM 2.1 player continuity experiment

Checked: 2026-10-06. This is a research-only engineering trial, not a segmentation-accuracy benchmark or released feature.

## Pinned model and runtime

- Upstream: [Meta SAM 2](https://github.com/facebookresearch/sam2), commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`; upstream code and model checkpoints are Apache-2.0.
- Model: SAM 2.1 Hiera Small; official config `sam2/configs/sam2.1/sam2.1_hiera_s.yaml`, SHA256 `592306d059a2df49898fefcb939c11abc9dfc8fd962bc77c31d132e68cb4320a`.
- Official checkpoint: `sam2.1_hiera_small.pt`, 184,416,285 bytes, SHA256 `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`.
- Worker interpreter: `%LOCALAPPDATA%\\PTTI-Dev\\vision-v2-sam2\\venv`, Python 3.12.14; PyTorch 2.10.0+cu128, torchvision 0.25.0+cu128, CUDA 12.8, NVIDIA RTX 5060 Laptop GPU (8 GB).
- The worker interpreter is separate from Desktop. Its packages reuse the already-staged `PTTI-Dev\\vision-v2` PyTorch dependency tree through an explicit package path; no RT-DETR, BallTrack, or Desktop package was changed. This is isolated at the worker/process boundary, not a fully hermetic duplicate environment.
- Native SAM 2 CUDA extension was not built (`nvcc` unavailable); inference used the upstream predictor with `apply_postprocessing=False`. The host had no WSL runtime.
- Locked tracker config SHA256: `9f2cc04ed25e935b6edb53fa296203a5091dabe9ff7ae349d77ce538dbb914bd`. It uses fixed object IDs, 120-FPS source metadata sampled at 30 FPS, no ID swaps, no automatic re-detection, and no long-occlusion reacquisition.

## Data and protocol

The source is the official **training split only** from [Extended OpenTTGames](https://github.com/moamal01/table_tennis_data), which documents Full-HD 120-FPS static side-view videos and a research dataset. Its license is CC BY-NC-SA 4.0; use is research/non-commercial only. The official [download script](https://raw.githubusercontent.com/moamal01/table_tennis_data/main/download_videos.sh) identifies the video source. No official test video was used, and no dataset video or checkpoint is committed or included in the preview build.

Five 10-second samples from five distinct training videos were screened under the same locked config. Source samples were selected before propagation; the first frame was used for seed readiness. RT-DETR candidates were inspected and Near/Far assignments were made by an experiment operator. Those assignments were not confirmed in the desktop before inference.

| Video | Start | Clip bytes | Clip SHA256 | Seed screen | SAM 2 result |
|---|---:|---:|---|---|---|
| `game_1` | 60 s | 28,176,204 | `8a47edc38efcbcc58b74abdfac538e01951aa3260727e407f9172bc54b19a904` | Two players visible; referee also present | Near 300/300; Far 159/300, 135 lost, 6 mask-area warnings |
| `game_2` | 60 s | 18,404,448 | `d181bd9f735b51f482c450242234766e3629e3cbcdc71bc79bb3befa86ffd60c` | Two players visible; referee also present | Near 300/300; Far 180/300, 118 lost, 2 mask-area warnings |
| `game_3` | 60 s | 17,002,250 | `4d1537234ec2279bc5c6e433cec43802f0f81a9883d556827087a21212748b6c` | One player was substantially cropped; no valid two-player seed | Not run; no second full-player seed |
| `game_4` | 30 s | 16,238,246 | `562caee412d402c9096410dc9b06391d80e53e5316676a3827f328709f047f48` | Two players visible; referee also present | Near 300/300; Far 300/300; no mask-area warnings |
| `game_5` | 60 s | 13,773,713 | `3082d087d73b216c07db8c6be85c1157c98f7fe3d3780387a9919ce15702eadb` | One player detected; second person was the umpire, not a player | Not run; did not seed the umpire as a player |

Each clip is 1920×1080, 10 seconds, 300 sampled frames at 30 FPS, from official 120-FPS training footage. The extracted clip SHA is recorded for every sample. Full-source SHA is recorded only for the locally held `game_4.mp4` (`ddb2bc49915a99db46702825ff322759faa9205c846a1ba902419e38c1e23b39`); the other full videos were not downloaded, so their full-source SHA is unknown. Their official source URLs and expected byte sizes are retained in the local manifest.

## Results

- Propagation ran on **3/5** clips. The two other clips remain failed initialization cases in the evaluation rather than being silently replaced.
- Across the 900 propagated frames, Near Player had 900/900 non-empty masks. Far Player had 639/900 tracked frames, 253 track-lost frames, and 8 mask-area review frames. There were no recorded ID-uncertain events. Object IDs were fixed in code, so this is not independent proof of identity continuity.
- Two propagated clips had substantial far-player losses. Visual samples show edge/camera framing and occlusion as plausible causes, but there is no frame-level identity or segmentation ground truth; the exact cause remains unverified. SAM 2 sometimes returned a mask later in the clip, but there is no RT-DETR re-detection or role reassociation workflow, so this is not counted as reliable reacquisition.
- Sampled overlays on `game_4` show broadly usable body masks with local holes around limbs/racket and fast poses. This was a visual spot check, not a labeled mask-quality score.
- The lightweight scene-cut detector found no cuts in these fixed-camera 10-second samples. Real replay, close-up, camera-switch reset, and reacquisition remain unverified.
- Propagation speed: 3.753–4.010 FPS. Model load: 0.917–1.018 s; video-state initialization: 15.257–15.790 s; propagation: 74.804–79.929 s per 10-second sample. Peak CUDA allocation/reservation: 740,103,168 / 889,192,448 bytes. Process RAM peak was not measured.
- `match10/001` and the old referee-clothing BallTrack issue were not part of this SAM 2 tracking metric; BallTrack remains frozen RAW and independent.

The machine-readable per-video results, source metadata, clip hashes, runtime, masks, sampled frames, and renders are under `%LOCALAPPDATA%\\PTTI-Dev\\vision-v2-sam2\\runs\\multi-match-final`. The report SHA256 is `288eb1e33b13f5c23e995a9f3d2f22e28a7d4ea9c47dc91c6cafe8b359bb4f57`.

## Desktop preview

The separate development preview adds **Video Analysis → 人物与球台 → 球员持续追踪**. It displays the `game_4` combined/near/far/original videos, sample frames, per-role tracked/lost counts, and five-match screening summary. A user can append a role-review record without changing RAW masks.

The essential pre-inference product loop is not finished: choosing Near/Far seeds in the desktop and launching propagation from that confirmed choice are not wired together. The existing confirmation is a post-run review record. The preview reads research outputs from local `PTTI-Dev`; it does not bundle research clips or weights. A different computer will not have these local results unless separately and lawfully staged.

## Decision

Gate: **`SAM2_PLAYER_TRACKING_PARTIAL`**. Three clips demonstrate real GPU propagation, but two could not initialize and two successful runs lost the far track for many frames. Desktop seed confirmation before inference, automatic re-detection/reassociation, long-occlusion recovery, and real scene-cut reset are incomplete or unverified. Do not start RTMPose yet.

Production database was not accessed. No main merge, tag, release, or v0.2 publication was performed.
