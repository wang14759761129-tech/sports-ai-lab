# Player Motion v0.1

Status: experimental Windows preview; tracking and pose gates are independent.

## Runtime and provenance

- Pose path: existing anchor-guided player boxes and masks → TrackQualityGate → per-player crop → RTMPose-m SimCC Halpe26 → original-frame coordinates. No additional person detector runs in the pose worker.
- RTMLib source: `cc359b924ec441b3563fb71f8cd012e576b8d262` (`0.0.10`), Apache-2.0. A small compatibility loader imports only the RTMPose modules because the pinned package references an optional visualization package that is absent from its source distribution.
- ONNX model input: 192×256. Model archive SHA256: `55b81170e236040b59fc792ad0a8315301ac4c079a3bdb1095d838aad3088d18`. Extracted ONNX SHA256: `26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf`.
- The RTMPose checkpoint has no separately verified license in the retrieved model materials. It remains research-only, outside Git and outside the preview package. RTMLib code's license does not establish the checkpoint's license.
- Isolated runtime: Python 3.12.14, ONNX Runtime GPU 1.26.0, RTMLib 0.0.10, NumPy 2.5.3, OpenCV headless 5.0.0.93, psutil 7.2.2. CUDA libraries are loaded from the existing isolated SAM2 environment; neither environment's packages were changed.
- Hardware: NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB class. Inference sessions explicitly report `CUDAExecutionProvider` and `CPUExecutionProvider`.
- Research material: Extended OpenTTGames official training split only, CC BY-NC-SA 4.0, non-commercial. The official test split was not accessed. Videos, annotations, model files, and inference output are not included in the repository or preview package.

## Quality policy

Each player is evaluated in one-second windows. Pose runs only when tracking records are accepted, visible or partial, have a mask and sane bounding box, and have no unresolved conflict, identity uncertainty, or confirmed out-of-frame event. Windows become `POSE_READY`, `REVIEW`, or `NO_POSE`. Untrusted windows produce explicit `NO_POSE` records with no keypoint observations. They are not filled by interpolation.

The model's 26 Halpe keypoints are preserved as raw observations. Thirteen primary body joints are named for display and metrics. Coordinates are transformed from person crops to the original 1920×1080 frames. Keypoint scores are model outputs, not calibrated probabilities. Low-score joints are hidden in the overlay.

The review workbench stores visibility, identity, and track-quality annotations as append-only local JSONL under `%LOCALAPPDATA%\PTTI-Dev\vision-v2-sam2\validation-workbench`. Motion exclusions also remain local and only affect derived metrics; original pose results remain unchanged. No production database is read.

## Real training clips

All clips are 10 seconds, 1920×1080, 30 FPS, sampled from five different official training games. Coverage here is good or partial pose frames divided by all 300 frames in the clip, not a keypoint-accuracy score or visible-frame recall.

| Clip | Video SHA256 | Near pose-ready | Far pose-ready | Notes |
|---|---|---:|---:|---|
| `game_1-t60` | `8a47edc38efcbcc58b74abdfac538e01951aa3260727e407f9172bc54b19a904` | 120/300 (40%) | 180/300 (60%) | Gate suppressed multiple windows; visible skeleton on the representative midpoint was correctly absent. |
| `game_2-t60` | `d181bd9f735b51f482c450242234766e3629e3cbcdc71bc79bb3befa86ffd60c` | 300/300 (100%) | 120/300 (40%) | Near skeleton sustained; Far windows without accepted evidence were skipped. |
| `game_3-t60` | `4d1537234ec2279bc5c6e433cec43802f0f81a9883d556827087a21212748b6c` | 300/300 (100%) | 300/300 (100%) | Both skeletons visually usable at the inspected representative frame. |
| `game_4-t30` | `562caee412d402c9096410dc9b06391d80e53e5316676a3827f328709f047f48` | 300/300 (100%) | 300/300 (100%) | Both skeletons visually usable; this is the initial ten-second acceptance clip. |
| `game_5-t60` | `3082d087d73b216c07db8c6be85c1157c98f7fe3d3780387a9919ce15702eadb` | 240/300 (80%) | 180/300 (60%) | Includes a review window; only accepted windows were inferred. Not treated as a clean tracking success. |

Aggregate: Near 1,260/1,500 (84%) and Far 1,080/1,500 (72%) full-clip frame coverage. There were no `PARTIAL` or `LOW_CONFIDENCE` skeleton frames in these runs: frames that did not pass pose quality became `NO_POSE`. Across all five videos, no record outside `POSE_READY` carried model keypoints. This is an engineering sample, not a population estimate.

Representative frames from each clip were visually inspected. The three stable clips (`game_3`, `game_4`, and accepted windows in `game_5`) showed both colored skeletons generally aligned with the players. `game_1` and `game_2` illustrate correct suppression when the track gate cannot support both players. The tracker remains `PLAYER_TRACKING_V1_PARTIAL`; pose success does not promote that gate.

## Performance and interpretation

The five final clip runs captured process RAM and GPU device memory. Peak worker working set was 1.36 GB. Peak NVIDIA device memory used was 3.17–3.40 GB; this is whole-device usage, not memory attributable solely to the pose process (Windows WDDM did not expose a process-level figure). Across clips, effective processing was about 26.6–37.3 source frames/s with mean pose inference around 6.4–8.5 ms per person. The `game_4-t30` preview-validation run processed 600 person frames at 7.391 ms/person and 26.588 frames/s, with 1.344 GB process RAM and 3.399 GB total device memory. A cold first single-frame startup took about 38 seconds; repeated warm inference on the same crop measured about 5–10 ms.

The product displays body-center, stance-width, knee-angle, lateral-motion, and wrist-path values as 2D `proxy` / `estimate` only. No force, power, load, muscle, technical-quality, stroke, contact, serve, spin, or tactical conclusion is made. Motion metrics require continuous identity evidence and do not bridge a skipped interval.

## UI and validation evidence

The video analysis page's **人物与球台** tab now contains **人体动作 · 2D 观察**. It provides Near/Far skeleton toggles, person-box and mask video layers, joint-score display, a one-second wrist trail, quality-window filtering, window seeking, 2D proxy metrics, local motion exclusion, and a separate tracking review form. The preview build is named `PTTI-Vision-v2-Player-Motion-Preview`; it reads results from local development storage and uses a development-only database. When the original source codec is not browser-compatible, the worker creates an H.264 preview copy after checking the registered source hash; it does not modify the registered video. The updated package was launched and the hosted desktop page was used to play the `game_4-t30` clip with both skeleton layers. The native pywebview window could not be enumerated by the available desktop automation bridge, so direct native-window interaction remains unverified.

The five overlay MP4s and result JSON are local under `%LOCALAPPDATA%\PTTI-Dev\vision-v2-rtmpose\runs\jobs\<tracking-job-id>`. The model and research video are not copied into the build. Full native Windows interaction still requires a manual check if the desktop automation bridge cannot expose the pywebview window.
