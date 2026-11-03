# Video Evidence review and long-video resource hardening

## Current user workflow

Open **视频复盘**, choose a locally authorized recording, then select or import its
matching frozen candidate package. The candidate queue supports review-state and
attention filters, previous/next navigation, a saved local review cursor, and the
J/K/A/R keyboard shortcuts. Selecting a candidate seeks the source video; the
existing player offers a short context replay, slow playback, and approximate
frame stepping. A/F are not used as evidence labels: the user can preserve
`UNKNOWN` or explicitly correct the side in the review panel.

The queue links to JSON, CSV, and Chinese HTML exports. Exports preserve raw AI
time, reviewed time, status, evidence source, review history, and filtered rows;
filtered means algorithm-suppressed, never human-confirmed. Rule evidence scores
are not calibrated probabilities. Imported video remains a local reference and
is not copied into the Preview or exported with the report.

## Evidence boundary

The existing evidence library keeps the original AI candidate and adds every
human decision to append-only review/audit history. A user edit does not modify
research ground truth. Candidate timestamps are labelled according to the
imported package's declared mapping; an absent mapping remains `UNKNOWN`.
Near/Far is not inferred from `UNKNOWN`. Pose is a 2D estimate and is not a
stroke or tactical conclusion.

## Long-video resource controls

The existing pipeline already splits the video into independently checkpointed
chunks. BallTrack decodes frames sequentially with a bounded inference batch and
bounded temporal history. The full-match background image uses at most 100
deterministically sampled frames resized to model dimensions; it does not load
the entire source video into a frame array. The median implementation and sample
selection remain unchanged.

The service now derives its startup RAM budget from physical RAM (at least 3 GiB
or 25% of physical RAM), pauses below a separate low-memory floor or on a steep
short-window decline, and samples the owned worker process tree during ffmpeg,
background generation, and BallTrack execution. Resource samples are appended
to per-run JSONL logs. On a guard stop the owned child process tree is terminated,
the chunk is checkpointed as `INTERRUPTED`, and the run can resume without
counting that chunk as complete. Chunk video, background, worker JSON, merged
timeline, and report writes use temporary files followed by replacement.

The guard is intentionally conservative. It does not expand the Windows page
file, stop unrelated processes, or change model weights, frame sequence,
resolution, timestamp mapping, thresholds, or frozen Hit Event configuration.

## Validation boundary

Automated tests exercise the resource trend guard, fail-closed pause, interrupted
chunk checkpoint, resume behavior, evidence review audit, filters, and exports.
This is not proof of a full multi-chunk GPU run. A real DEV inference must only
start when the machine-relative budget allows it; if not, the run remains paused
and the resource gate remains incomplete. The GAME_5 internal holdout, its
annotations, the official TEST split, and the Production database are outside
this engineering task.

Native Windows window interaction remains a separate manual QA gate when the
available computer-use runtime cannot control native desktop windows.
