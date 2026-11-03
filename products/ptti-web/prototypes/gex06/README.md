# PTTI GEX06R — local video → Moment → human review

This evolves the existing isolated GEX06 branch. It does not update Native R4, the San production UI, Launcher, Main or any user database. Only the accessible GEX06 three-scene source was found; the separate six-page MUSE delivery was not available here. No claim is made that its original scoring implementation was edited.

## Run / open
From `C:/PTTI-Worktrees/gex06r-moment-restore`:

`node products/ptti-web/prototypes/gex06/serve.mjs`

Open the printed `http://127.0.0.1:<free-port>/` in your existing Windows browser. Free loopback port, no port takeover. Keep this process running. Ctrl+C stops only this prototype. Old servers use immutable in-memory snapshots and are not silently updated. `runtime.local.json` identifies the newest process and exact served hashes.

## One actual intended path (GUI acceptance pending)
1. **Cinema** → choose a video you have rights to, or click the PTTI-owned synthetic test asset. Hashing processes every byte in 1 MiB chunks. No filename-based identity; no upload. Wait for metadata readiness.
2. Play/pause with native HTML5 controls or the app button. Drag the real video scrubber, select 0.5× / 0.25×, request native fullscreen. Browser codec/autoplay/fullscreen policy may prevent an operation; no iframe is modified.
3. **Moments** → pause at a time → type a note → save → jump/replay/edit/delete. Notes carry that content ID and actual video time. Select another file: its notes cannot leak into this video. Reselect identical bytes under a different filename to restore saved records. Refresh clears the media File object; reselect it to restore records. Unconfirmed form edits are not saved.
4. **Pro Lab** → mark start/end from the current player, add manual text, save three real spans. Invalid/zero/reversed/out-of-range bounds are rejected. This is the prototype's segment workspace, not the production professional engine.
5. **Rally Coach** → select a saved span → replay. The same video element seeks to start and pauses near the end via timeupdate; this is not frame-accurate playback acceptance. It displays the saved human text. Optional speech is **text-to-speech only** and selects only browser voices with `localService=true`; no confirmed local voice means no speech. No microphone request or speech recognition. Save a correction/training note explicitly; it is genuinely written to the independent store or a storage error is reported.
6. Export the current evidence JSON. Check actual download. The bundle contains VideoAsset, TimelineEvent, Moment, Rally, Annotation, ReviewNote, simulated Predictions, a complete Vision checklist when saved, and an empty PoseEvidence list. No video bytes, automatic filesystem path, filename, public match or official source binding.

## Moment restore (this revision)
Select the exact same video content first. Moments → Import JSON → inspect counts → confirm merge or cancel. Schema, content identity, duration, complete envelope and all moment timestamps are checked before any write. Same ID with different contents is a conflict and is skipped, not overwritten. Same time/text/video under different IDs is also deduplicated. Stale previews, malformed/oversize JSON and storage errors do not change existing data. Only Moments restore; the preview explicitly excludes other record types. The old d94bccc export is supported only for the exact original synthetic asset via its known whole-file SHA ↔ chunk-content-ID bridge, never by filename.

Export → explicitly clear current-video Moments → import → confirm → replay a restored moment → refresh/reselect identical video → verify retained records. The clear button does not clear rallies, notes, formal Journal or other videos.

## Arena correctness (this revision)
Starts at the explicit MOCK 9:9 scenario. Four unique events A/B/A/A derive 10:9 → 10:10 → 11:10 → 12:10. The final score is never inserted as a terminal string. Every event has eventId, pointIndex, scoreBefore, winner, scoreAfter, timestamp, revealState, prediction and predictionResult. Source is MOCK; timestamps are deliberately placed at 20/40/60/80% of the selected video's duration and **do not claim a real point occurred there**. The interface for measured timelines is NOT enabled.

Choose → lock → Reveal plays from just before the event timestamp. Only the actual video timeupdate reaching that position applies the score and history. A rejected play or navigation/pause cancels the pending reveal without scoring. Revealed events cannot score twice. Retry unlocks only an unrevealed prediction; replaying an already revealed event does not score. Full reset returns to the explicit starting 9:9 and empties predictions/history. Returning to Moments and back retains the current round; choosing another video deliberately starts a new mock round.

## Vision and Motion Twin
Vision exports video ID, camera, fps and UNKNOWN/ESTIMATED/CONFIRMED_BY_USER status, light, occlusion, action type, start/end, all five continuous phase bounds, all five checkbox booleans, manual note, review timestamp, human source, unverified-fact status and not-frame-verified boundary status. Phase gaps/overlaps, invalid times and inconsistent fps status are rejected. Unknown fps remains null, not inferred from the filename.

Motion Twin remains inactive. `poseEvidence()` specifies exactly 33 finite landmarks per time-ordered frame and explicit source/video identity. A structurally valid payload is not proof of measurement; provider provenance still needs independent review. No sine skeleton, similarity score or professional diagnosis is rendered. Voice, pose and vision are not claimed as AI capabilities.

## Data and rights
Only `ptti.gex06r.local-evidence/1` is read/written. Original GEX06 records and all formal Journal/favorite/follow keys remain untouched. Corrupt storage is not overwritten; write/quota failure retains the current session and asks for export. Explicit save is required. Browser storage is local to this port/origin; use the same running URL to recover it. Restarting the server on a new port has a different localStorage origin. To retain the same origin, restart with `node products/ptti-web/prototypes/gex06/serve.mjs <previous-port>`. This is strict: an occupied port fails, without killing a process or switching ports. Export before stopping as a backup. Cross-origin Moments restoration is now supported via explicit JSON import after selecting matching video bytes; other evidence types are not imported.

The four-column 5cc visual DNA, native-video approach and exact eight San match facts are retained, without copying R4 runtime. The catalog remains distinct from private video. Approved third-party distributable covers remain zero; every bundled visual is original and marked as not that match's footage. GEX03E historical GUI evidence and GEX05 mock/API foundation are not new GUI acceptance.

## Validation
- `node products/ptti-web/prototypes/gex06/test.mjs`: full-content identity (including changed middle chunk and renamed file), media SHA, moments/rallies, persistence JSON roundtrip, wrong-video rejection, bad times, complete Vision export, duplicate-score/late-prediction/reset, all four 9:9 events, PoseEvidence negatives and no production storage/upload patterns.
- `node products/ptti-web/prototypes/gex06/build.mjs`: isolated minified browser bundle in ignored `qa/build`; no new dependency.
- `node products/ptti-web/prototypes/gex06/verify-service.mjs`: current running server HTTP, range 206/416, no source/QA exposure and no upload endpoint. HTTP is not GUI playback.
- Original test video remains H.264, 960×540, 24fps, 12 seconds, no audio; original full decode passed. No private media used in tests.

This revision preflight on 2026-10-27: **1.128 GiB / idle63.235s**. Below 3GiB, so GUI/BROWSER_PLAYBACK/FULLSCREEN/TTS/RESPONSIVE_VISUAL/DOWNLOAD remain NOT_TESTED/BLOCKED. No browser was launched and no retry/bypass was made. Browser API support is not observed success. Screenshots are unavailable, not simulated.

## Boundaries / rollback / handoff
All changes are under `products/ptti-web/prototypes/gex06`. Parent `d94bccc2dd6658ef1c3a4fec64efdd18389c8462` is the original prototype checkpoint. Stop the new standalone process to roll back; old services/candidates are preserved. No deployment, push, database or Launcher change.

PLAYBACK handoff: adapt content ID + confirmed duration + `{video_id,start,end}` into its owned session interface, and validate native seek/end tolerance, codec failure and fullscreen before production integration. The full-content chunk-hash ID is versioned and is **not** claimed to equal a normal whole-file SHA256. MAIN handoff: only approved source-bound cover records; no private media identity is promoted to a public match. Vision handoff: measured 33-point provider provenance and timestamp alignment; absent now.

## HOST / Founder handoff
Read `HOST-FOUNDER-ACCEPTANCE.md`. Low RAM blocks agent automation, not Founder's manual use of an already-open browser. No agent screenshot or browser PASS is claimed. The previous d94bccc snapshot and its old service are not replaced.

New checks: `node products/ptti-web/prototypes/gex06/test-restore-events.mjs` writes synthetic roundtrip and exact four-event JSON into ignored `qa/`. These are model/storage tests, NOT actual browser download/upload/seek evidence.

## Independent worktree build tools
No dependencies are needed to run the server or tests. For the optional browser bundle in this dependency-free worktree, set PowerShell `$env:PTTI_ESBUILD_MODULE='C:/PTTI-Worktrees/web-goal14-fan-mvp/products/ptti-web/node_modules/esbuild/lib/main.js'` then run `node products/ptti-web/prototypes/gex06/build.mjs`. This uses the already-installed San build tool read-only; it does not install packages, copy dependencies, or change the original worktree. With normal project dependencies installed, omit the environment variable.
