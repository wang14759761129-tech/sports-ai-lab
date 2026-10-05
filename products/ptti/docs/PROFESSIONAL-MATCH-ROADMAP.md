# Professional match intelligence roadmap

This document defines the next data and analysis steps. It does not claim that rally segmentation, whole-match analysis, or scouting is implemented.

## Step 2 — Professional Match Corpus

Keep an event/match record separate from local point-analysis matches. Import official result metadata with source URLs and retrieval dates, and let the user choose two registered athletes. Video selection must be a separate local-file action. Store the local path only after the user explicitly marks that they have analysis rights. External WTT/YouTube pages remain references and are never fetched as media. A video-ready record needs a readable supported file, rights status, and source/authorization note. The current desktop form explicitly tells the user that it copies the selected file into the local data directory; the original file is not moved or modified. The user confirms analysis rights and supplies the source/authorization note before the copy begins.

Before analysis, show the selected event, players, video filename, file metadata, rights declaration, and a reversible cancel action. The video QA step should verify decode, duration, resolution, frame rate, orientation, and audio/video stream metadata. Record an input hash and tool/model versions. Current BallTrack v1 RAW can be run on authorized local video; this step must not claim points, rallies, or tactics.

## Step 3 — Full-match structure detection

Build separate, reviewable outputs for game boundaries, point intervals, score evidence, and confidence/unknown states. Keep frame timestamps and raw detector outputs. Evaluate on whole matches with splits by match, not adjacent clips from the same match. Human correction must be possible before any per-point table is accepted. No score or rally boundary may be inferred from a video if evidence is insufficient.

## Step 4 — Tactical intelligence

Only compute tactical metrics after point segmentation and the required observations have passed quality gates. Maintain field-level provenance and uncertainty, distinguish observed labels from derived values, and report denominators. Keep unsupported tactical fields unavailable rather than filling them from outcome or player reputation.

## Step 5 — Player model and scouting

Build longitudinal player views from verified, linked match records. Track source and time for every ranking or match fact. Compare only compatible event formats, conditions, and annotated fields. Describe the covered sample and uncertainty; do not market the result as a validated scouting prediction.

## Current readiness and limits

The athlete registry, one ranking snapshot, a small sourced match catalogue, player-profile API, and Chinese directory UI are present. The user has indicated a locally held legally usable full-match video is available; it has not yet been selected, hashed, inspected, or analyzed. Professional-match creation can optionally copy an authorized MP4/MOV/MKV/AVI file into the isolated local data directory, inspect it with ffprobe, and record its hash, metadata, input-quality class, and user-supplied source/authorization note. A registered full match remains `VIDEO_READY`; the current BallTrack runner accepts only clips up to 60 seconds / 1800 frames and this registration flow does not start it. Rally segmentation and human-reviewed full-match segmentation are not implemented. Begin Step 2 by selecting the user's existing authorized local file in the desktop app and recording its specific match metadata. Do not choose or download protected broadcast media on the user's behalf.

**Manual GUI check:** `MANUAL_GUI_CHECK_REQUIRED`. Automated API tests use temporary databases and mocked video metadata; no real user video has been selected or inspected in the desktop application.
