# GOAL 12.2 Candidate Handoff

## Scope

- Worktree: `C:\PTTI-Worktrees\web-mvp-v0-1-goal12-1-candidate`
- Branch: `codex/ptti-goal12-1-candidate`
- Base: `e8dfedfbe7094217a3f0a9c57d3a5943847dd3bc`
- Playback Core: `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`
- This candidate is local-only and must not be activated before release review.

## Delivered

- Cinema's first screen presents three separate choices: a local training video, the 19-point `SIMULATED_ONLY` review-data demo, and sourced match pages opened externally.
- The simulated demo continues to say that it has no bound match footage and currently offers zero replayable clips until a user selects a local video and confirms boundaries.
- The external-source entry leads to the existing match catalog. It does not imply embedded playback, media permission, or regional availability.
- Explore contains exactly three review guides: coarse observed contact groups, report-provided denominators and sample cautions, and the manual record-then-review workflow.
- `ProWorkbench` remains mounted under the hidden persistent workspace while navigation changes. When inactive, the existing player pauses and the current playlist is cancelled; playback code was not replaced.
- The previously delivered success-only demo-load navigation to Insight is unchanged.

## Verification

- `npm run check:cinema-experience`: PASS.
- `npm run check:cinema-insight`: PASS; verified load success navigates, rejected/stale/error cases remain on Cinema, duplicate loads are disabled, and the video session cannot be replaced by demo import.
- `npm run build` (includes `tsc -b`): PASS with the existing Vite chunk-size warning.
- `git diff --check`: PASS.
- Playback Core source HEAD checked at `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`.
- Accepted 4174 release manifest: 60/60 file hashes match; its worktree remains at `0f544307cfe0b076ada2894674f5cbc20f52e579`, clean, and its health endpoint still reports that same San HEAD and Playback Core.
- Chrome: NOT RUN. Available memory was 0.96 GiB, below the unchanged 2.5 GiB browser gate.

## Next Candidate Acceptance Checklist

1. With available memory safely above 2.5 GiB, open only the isolated candidate in Chrome; do not use 4174 screenshots as candidate evidence.
2. Confirm the three Cinema choices are distinct in Chinese and English; the local-video choice opens the existing browser-local player.
3. Load the 19-point demo and verify that the validated success route opens Insight while the simulated label and no-bound-video notice remain visible.
4. Navigate Cinema → Insight/Review → Explore and confirm the local video player remains mounted; when hidden it pauses and cancels any active playlist, then returns without losing the selected local session.
5. Confirm source links lead to their recorded HTTPS source pages and that source-page opening is not labelled as playback success.
6. Check 1366×768 and 390px layouts, keyboard focus, and all three Explore guides.
7. Recheck candidate hashes and `review4/public0` separation before any release registration.

## Version identity correction (GOAL 12.3-L)

- The base recorded above, `e8dfedfbe7094217a3f0a9c57d3a5943847dd3bc`, exists and is the parent of the actual GOAL 12.2 feature commit.
- Actual GOAL 12.2 delivered commit: `f39359a169e597bad7a514adcfc0f060134ed322`.
- Earlier reported full SHA: `f39359a169e597bad7a514adcfc0f0601bdb2fbe`; this object is absent from the candidate repository's object database.
- The actual commit is present on the candidate branch and descends directly from the recorded base. The available evidence cannot distinguish a transcription error from a SHA originating in another object database/worktree; cause remains `UNKNOWN`.
- No history was rewritten. The incorrect reported value is retained here as an investigation record, not as the GOAL 12.2 commit identity.
