# GOAL17.1 Main-to-San handoff

This is an additive package. It does not replace the GOAL15 strict-public library or GOAL16 public-media manifest.

## Public files

- `public/athlete-photo-additions.json` — `ptti.goal17.1-athlete-media/0.1`; three scoped, attributed athlete-profile images.
- `public/assets/` — six metadata-stripped responsive WebP derivatives described by the manifest.
- `public/official-match-video-additions.json` — `ptti.goal17.1-match-video-additions/0.1`; two official WTT YouTube external links.
- Schemas: `products/ptti-integration/contracts/goal17-1-athlete-media-v0.1.schema.json` and `goal17-1-match-video-additions-v0.1.schema.json`.

## Review files and source originals

- `internal/goal17-1-photo-rights-review.json` contains the scoped use decision and visual/rights rationale for the three new images, rechecks all nine GOAL16 candidates, and records the unresolved focus-player gaps, the rejected 2026 venue-image candidate and WTT-video limitations.
- `internal/goal16-nine-photo-recheck.json` records the nine prior decisions. Four already-cleared original files were locally rehashed; five non-cleared originals were not staged and remain `NOT_MEASURED_ORIGINAL_NOT_STAGED`.
- `reviewed-originals/` holds only the three newly reviewed Commons source images used to create the derivatives. The originals are not part of the public directory.

## Consumption rules

For the three images, render only in factual profile/editorial context with the manifest attribution, source and license links visible. The image identity is not evidence for a specific match. Homepage promotion, advertising, endorsement, match-photo, video-thumbnail, AI-training and other uses remain not cleared by this package. Keep the full four-player context for Félix Lebrun; do not crop it as an individual portrait. Do not enlarge the 498×648 Sun Yingsha interview still beyond its stated quality limit.

For WTT videos, use only the provided official YouTube `watch_url` as an external-platform route. `playback_status` is `NOT_TESTED`; embed, thumbnail, download, local analysis and redistribution permissions are not granted; territory and login status remain `UNKNOWN`. “FULL MATCH” is the official title claim, not an independent completeness verification.

No record in this delta modifies the base package. The JSON carries the exact GOAL15 and GOAL16 baseline hashes; refuse application if those baselines change until the delta is regenerated and reviewed.

## Rebuild and validate

From repository root, set `PTTI_FFMPEG_PATH` and `PTTI_FFPROBE_PATH` if those programs are not on `PATH`, then run:

```powershell
node products/ptti-integration/scripts/build_goal17_1_real_content.mjs --build
node --test products/ptti-integration/tests/goal17_1_media.test.mjs
node products/ptti-integration/scripts/build_goal17_1_real_content.mjs --validate
```

The generator stops if the locked GOAL15/GOAL16 baselines, source originals, or source dimensions do not match. Public and internal outputs are written to separate directories.
