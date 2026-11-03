# SCOUT-004 R2 rendered-page review (internal only)

This review ledger records only the 15 candidate labels, claimed video IDs, and grade counts visible on the supplied handoff webpage. The JSON and CSV paths shown by that page (`/workspace/ptti/scout-004-r2-candidates.json` and `.csv`) are publisher-side paths, not downloadable attachments. The page offered a PDF action, but the browser input timed out; targeted local searches did not find either machine-readable file.

`internal/review.json` is **not** the source candidate package, is not a PTTI catalog, and must not be consumed by San. It does not assign PTTI `match_id`, `source_id`, or `athlete_id` to new candidates. The rendered claims remain distinct from official match records, official video metadata, playback evidence, and rights grants.

## What the preflight establishes

- Current Main composed union: 8 unique match IDs, 19 unique video IDs, 8 athletes. This was recalculated from the SHA-pinned GOAL15/17/22/24/27 packages listed in the JSON.
- Current San worktree snapshot: clean at `b8017ac8de2a0dbac7ec274fca1f76c21f1fc7cd`; its strict public base file is still the GOAL15 5-match/15-source/8-star package. The GOAL14 public projection in that worktree contains zero events, candidates, or relationships, so the four additive GOAL17/22/24/27 packages are not physically integrated there.
- Exact ID de-duplication: C07's `cDccQqVlMnc` is already the public full-match source for `pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final`. S3's `vYsJLPTEIaI` is already in the current 9-row `official_video_sources.json` snapshot and the GOAL11 historical review roll-up of 35 unique references as `REFERENCE_ONLY`; it has no canonical match link. Do not duplicate that source or infer its match link. C07's claimed highlight `DHxcmcGrpn2` and S3's claimed highlight `9e5Eqa4Edr4` are distinct IDs but have not been verified or admitted.
- C01 is fact-checked from JTTA's official China Smash event results page. C08 is fact-checked from the Macao SAR Sports Bureau co-organizer's official press release. S1's pair and straight-games result are supported by an ITTF event report, but the M4 designation and game scores were not independently confirmed.

## Admission decision

No new match or video source was added to a strict-public package. The source report says rights are uncleared, playback is `NOT_TESTED`, and territory is `UNKNOWN`; candidate YouTube pages could not be independently fetched in this pass. Main's existing package contract requires independent source identity, explicit evidence and fail-closed rights fields. The candidate page's “READY FOR MAIN REVIEW” is not an admission.

## Resume condition

Provide the original `scout-004-r2-candidates.json` and `.csv` (or a direct, accessible download link). Then rerun full row-level identity, score, exact video-ID, type, source, and rights validation; do not use this summary ledger as an import substitute.
