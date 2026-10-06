# Match Structure Intelligence — Engineering Baseline

Status: `RALLY_SUGGESTION_BASELINE_READY` (engineering QA only; no annotated-match validation).

## Layer boundary

`MatchStructureEngine` consumes the unified full-match `full_match_balltrack.jsonl` output. It does not import or modify the BallTrack model and it does not change the existing manual timeline. RAW BallTrack remains the only default detector. The output is stored as a separate, versioned `match_structure_runs` record and exported as `match_structure.json` and `match_structure.html`.

Every event carries an event ID, event type, global timestamp/frame, `SUGGESTED`/human review status, a nullable confidence (this baseline does not manufacture one), evidence, and source module. Unsupported event types are declared in the capability map instead of being silently emitted. Scoreboard recognition is disabled. Point/game, replay, contact, and bounce recognition are not implemented as automatic facts.

## Rally baseline

The first implementation scans the unified timeline for sustained `visible=false` runs. A candidate boundary requires a configurable minimum gap and visible RAW observations inside context windows on both sides. A `RALLY_END_CANDIDATE` is placed at the last observed ball frame before the gap; a `RALLY_START_CANDIDATE` is placed at the first observed frame after it. A candidate rally interval is formed only between two independently supported gaps, so clip-edge intervals stay unknown. Evidence states the lost-ball duration, neighboring observation counts, frame references, and whether the gap crossed a BallTrack chunk boundary.

A lost ball is not treated as proof of a point end. The current algorithm does not use the scoreboard or infer point outcomes. It is a conservative engineering baseline, not a validated rally detector. No ground-truth precision, recall, F1, or boundary error is available.

## Review and protection

The Match Review queue lists unresolved suggestions and manual overlaps. Accept/reject/adjust/split/merge are explicit actions. Each action records actor, time, before/after boundaries, and the fact that original evidence was preserved. Accepted suggestions are confirmed in this separate structure record. They do not silently add or alter Game, Point, or Rally rows in the human timeline. Existing manual overlaps are surfaced as conflicts.

Keyboard shortcuts in the review panel: Space play/pause, A accept the first suggestion, R reject it, `[` set its start to the current playback position, and `]` set its end. Inputs keep their normal typing behavior.

## Table calibration

Manual calibration accepts four image points in order: near-left, near-right, far-right, far-left. The review UI captures a paused frame and lets the reviewer click these four corners; pixel coordinates can also be corrected directly. The homography maps these to the unit square. X runs from the near player's left to right; Y runs from the near end line to the far end line; the origin is the near-left corner. The video SHA-256 and a user-supplied camera-segment ID bind each calibration. A different video hash or segment ID returns `STALE`.

Calibration is not automatically applied to BallTrack or used for tactical conclusions. Camera cut/zoom detection is not wired to automatic invalidation; the reviewer must use a new camera-segment ID when the view changes.

## Scene and replay seams

`SceneBoundaryDetector` provides an experimental normalized histogram-distance helper and emits only `SCENE_CHANGE` suggestions. It is not yet run across complete video frames or used as an automatic rally filter. Replay recognition remains `DISABLED_EXPERIMENTAL`; scene labels stay human reviewed. `ScoreboardRecognizer` is an interface only and disabled.

## Engineering QA and limitations

Synthetic tests cover event creation, both-side windows, cross-chunk continuity, manual-timeline protection/conflicts, review audit actions, table homography and stale binding, scene-change suggestions, persistence, and report output. Synthetic fixtures do not validate algorithm accuracy. No locally available annotated legal rally dataset was identified for this work. Human correction metrics therefore remain `BASELINE NOT AVAILABLE`.

The baseline does not recognize serve start, ball contact, table bounce, net crossing, replay, point boundaries, or game boundaries. It does not infer spin, stroke, player attribution, score, or tactics. A missing-ball interval may reflect occlusion, detection failure, serve preparation, or a cut; the evidence is exposed so a human can decide.

## Gates

- Release Gate: `HISTORICAL_DB_UNVERIFIED`
- Vision Gate: `BALLTRACK_V1_FROZEN_RAW`
- Full Match Engineering Gate: `FULL_MATCH_PIPELINE_ENGINEERING_VERIFIED`
- Match Structure Gate: `RALLY_SUGGESTION_BASELINE_READY`
- Annotated real-match evaluation: `NOT AVAILABLE`
- Release/merge/tag: not authorized or performed

## RacketPose decision question

RacketPose would only be justified if review/evaluation shows that ball-only trajectory evidence cannot resolve candidate contact timing or distinguish contact from occlusion/camera motion. It could provide independent racket/player-pose evidence near already identified ball events. It should not be added solely to create a richer demo, and it cannot by itself validate rally boundaries, score, or tactics.
