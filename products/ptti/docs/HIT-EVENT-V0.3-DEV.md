# Hit Event v0.3: event disambiguation and player evidence

## Scope and locks

Research branch: `research/hit-v03-event-disambiguation`, based on
`6b3c426b2f6852bc5c57d18bf318857053bc0200`. Only Extended OpenTTGames
TRAIN DEV game_1, game_2 and game_3 are permitted. Calibration game_4,
holdout game_5 and the official TEST split remain locked. No production
database access, desktop changes, model installation or release is required.

The existing Hit v0.2 config, reports and RAW BallTrack are immutable.
`V02_IMMUTABLE_BASELINE.json` records per-artifact hashes, source and annotation
hashes, config hash and the evaluator source hash. It is stored under
`%LOCALAPPDATA%/PTTI-Dev/evidence/hit_event_v0_3/`, alongside all research data.
The dataset remains CC BY-NC-SA 4.0, non-commercial; no media enters Git or builds.

## Verified diagnostic findings

At ±2 actual processing frames (16.667 ms for this 120 FPS baseline):

| Stage | TP | FP | FN |
|---|---:|---:|---:|
| RAW | 520 | 12741 | 192 |
| Cluster | 456 | 3800 | 256 |
| Decoder | 353 | 479 | 359 |

All FP receive signed nearest-event distances to native STROKE, BOUNCE, NET
and RALLY_ENDING. Multilabel counts are temporal associations, not verified
causal classifications. With a 100 ms diagnostic window:

| Stage | Near stroke | Near bounce | Near net | Near ending | Jump flag | Unexplained by these hints |
|---|---:|---:|---:|---:|---:|---:|
| RAW | 2380 | 4028 | 663 | 321 | 121 | 6294 |
| Cluster | 540 | 1224 | 291 | 94 | 51 | 1922 |
| Decoder | 133 | 97 | 4 | 23 | 0 | 252 |

Counts overlap and must not be summed as an exclusive confusion matrix.
UNKNOWN player proximity currently applies to every baseline FP. Serve
preparation and causal bounce/net confusion require video review; proximity
alone cannot establish either.

Of the 192 RAW FN, 94 fail the existing before/after ball-context requirement;
98 satisfy it. Inspection of those 98 reveals **97 have no visible ball center
within the matching tolerance**. The remaining event has a visible center but
violates the generator's maximum inter-observation gap. This is a distinction
between broad context availability and an eligible central observation, not
proof that all 98 are score-threshold failures. Ball observations are not filled
or invented to hide this limitation.

All 64 cluster-lost events have a matched RAW member whose cluster selected
another maximum-score member outside tolerance. Of the 103 additional decoder
losses, 40 remain review-only and 63 are auto-rejected. Reconstructed frozen
decoder traces preserve utility, predecessor and penalty explanations; reasons
can overlap (80 global-path conflicts, 51 below-floor flags, 22 ball-quality
flags, one low-sequence-utility flag).

## Feature study and limitations

±150 ms native-event windows preserve image trajectories, velocities,
acceleration/curvature proxies, model response, missingness and pre/post counts.
Speed distributions overlap substantially between stroke, bounce and net;
speed alone is not demonstrated to be a reliable event classifier.

Coarse table image coordinates show a useful DEV spatial distinction. Median
horizontal distance from coarse table center for stroke/bounce/net respectively:

| Game | Stroke | Bounce | Net |
|---|---:|---:|---:|
| game_1 | .468 | .260 | .021 |
| game_2 | .462 | .246 | .005 |
| game_3 | .491 | .278 | .005 |

These use only nearby visible observations, with different missingness between
event classes. The geometry is CAMERA_DEPENDENT, a coarse bbox projection,
not a homography, actual net detection or physical near/far truth. Existing
scene files lacked full-source hashes when created. Source linkage and
static-camera applicability must remain explicitly provisional rather than
silently treated as verified throughout a full match.

Subsequent source-link verification re-extracted the 12 unique DEV scene
keyframes from the complete local videos. All 12 JPEG SHA256 values exactly
match the original scene inputs. Source linkage is therefore verified for
these samples; whole-video coarse-geometry accuracy remains a separate limit.

## Player experiment and safety

Candidate-centric requests cover 14,579 distinct frames: 2,570 / 8,616 / 3,393
for games 1 / 2 / 3. This is not a full 334,959-frame vision rerun. RT-DETR R18
uses the previously verified checkpoint and runtime boundary without changes
to any frozen environment. New stdlib-only analysis runs in a uv-created venv.

Workers process at most 256 requested frames, decode with two FFmpeg threads,
and exit after each checkpoint. Requests and completed result hashes are
validated on resume. A worker cannot start below 3 GiB available RAM; it stops
below 1.5 GiB available RAM or above 3 GiB working set. A resource guard stopped
the initial unbounded-decoder attempt; decode threading was bounded rather
than lowering the guard. No OS crash was observed during that attempt.

RT-DETR scores are uncalibrated detector scores. The existing role resolver
supplies only role candidates. Confirmed role, athlete identity and physical
side stay UNKNOWN. Missing or ambiguous player features are neutral, not zero
distance and not an invented player.

## Preregistered small ablation

The first experiment uses the same config on all three DEV games:

- A: exact immutable Ball-only v0.2, required to reproduce TP/FP/FN.
- B: A plus a bounded coarse table-center penalty (maximum .08).
- C: A plus a bounded distance-to-player-candidate penalty (maximum .12,
  distance scale .12 image diagonals).
- D: both soft features, with the same values as B/C.

The table rule addresses spatially central non-hit candidates, supported by
the exploratory distributions above. It risks suppressing real strokes whose
projection overlaps table center. The player rule tests whether spatial
separation helps reject visual/no-contact candidates; it risks penalties when
the detector misses a real player. It is a hypothesis, not yet an accepted
product rule. No bbox or GT-near-event pattern causes hard deletion. No Pose
or new event classes are included.

Results must include all games, ±1/2/3-frame tolerances, P/R/F1, FP/min, FN/min
and review burden. Three seconds per candidate is an explicit estimate,
not measured coach time. A frozen baseline and incomplete player cache must
never be presented as completed A/B/C/D results. There is no automatic
calibration authorization even if DEV improves.

Before completion of the player experiment, the conservative research
promotion check is recorded as: at least +3 percentage points aggregate
precision, no more than 2 percentage points aggregate recall loss, and F1
improvement in at least two DEV games. These are engineering guardrails,
not a statistical significance test or product-accuracy certification.

## Tools and reproducibility

Research code lives in `research/hit-v03/`. Run `audit.py` into a new output
directory; it refuses replacement. `plan_players.py` verifies DEV source
and annotation hashes before creating observation-only requests.
`run_players.py` resumes completed per-batch caches. `evaluate.py` refuses
an incomplete player cache and asserts that A reproduces v0.2. `annotation_pack.py`
exports a small non-commercial video review package, with seven CVAT labels
and source timestamps; it does not install CVAT. Downsampled clips are previews,
not replacements for frame-accurate source annotations.

Runtime features have no file/dataset imports. GT is confined to research
diagnostics, frame selection and evaluation. Ruff applies to new code only.

Completed A/B/C/D results are recorded in `../research/hit-v03/DEV_RESULTS.md`.
D satisfies the preregistered DEV improvement guardrails: precision .4243→.4740,
recall .4958→.4986, FP 479→394, and F1 improves in all three games. Research
promotion proposal: **HIT_EVENT_V0_3_DEV_READY**. The desktop/product engine
remains unchanged at **HIT_EVENT_V0_2_PARTIAL**. Calibration, holdout and
official TEST remain locked; no automatic product acceptance is implied.
