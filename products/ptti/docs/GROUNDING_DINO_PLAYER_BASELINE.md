# Grounding DINO Person Baseline

Status: `GROUNDING_DINO_PLAYER_BASELINE`  
Baseline code commit: `239aea44bd6be3baba248d3a738f8b6123fd13e2`  
Evaluation manifest SHA256: `67bc35a5a1570d4610e524141030f1c93aa5b2a8516767f12023d4eb9f75276f`

This is the frozen person-candidate baseline for the Hybrid Scene Engine comparison. Do not replace these observations with later detector results.

## Fixed sample

- Dataset: Extended OpenTTGames, official training split only, revision `36471a76b969a0340df59258a813bf8214e68e7c`.
- License: CC BY-NC-SA 4.0; research and non-commercial evaluation only.
- Five match files, four deterministic sampled frames per match (20 frames total), each 1920×1080.
- Prompt profile: `official_bootstrap_a` (`table tennis table. person. referee. scoreboard.`).
- Model: `IDEA-Research/grounding-dino-base`, revision `a062f8edaf7f3aa52714a8f80cb8db7de1e5e170`, checkpoint SHA256 `5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21`.
- Full video hashes are available only for game_4; extracted frame hashes identify all sampled images. The source media and derived imagery remain outside Git and product packages.

## Frozen observations

| Match | Sampled frames | Table candidate | Both screen-side person candidates | Extra person candidates |
| --- | ---: | ---: | ---: | ---: |
| game_1 | 4 | 4/4 | 1/4 (25%) | 6 |
| game_2 | 4 | 4/4 | 2/4 (50%) | 7 |
| game_3 | 4 | 4/4 | 3/4 (75%) | 5 |
| game_4 | 4 | 4/4 | 4/4 (100%) | 4 |
| game_5 | 4 | 4/4 | 1/4 (25%) | 3 |
| **Total** | **20** | **20/20** | **11/20 (55%)** | **25** |

The 55% value is **candidate coverage**, not recall or person-detection accuracy: no human person-box ground truth was annotated for this sample. “Both” means a candidate on each side of the table under the existing spatial heuristic; it does not establish player identity or distinguish a referee with certainty. Scoreboard candidates were 0/20.

The five-match coarse table-box audit reported exploratory mean IoU ≈0.933. Its manually approximated extents include the physical table supports and are not a formal mask/box benchmark.

## Use in comparisons

Reuse the exact 20 frame files and timestamps listed in the external manifest. Compare detector candidates on these same frames. Keep `GROUNDING_DINO_PLAYER_BASELINE` immutable; create a separate result artifact for RTMDet. Aggregate and per-match candidate coverage alone do not establish true precision/recall until a human-reviewed reference set is available.
