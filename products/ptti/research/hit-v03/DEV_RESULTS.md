# Hit v0.3 full DEV results

Scope: Extended OpenTTGames TRAIN DEV game_1-3; 712 stroke GT, 2791.325 seconds.
License: CC BY-NC-SA 4.0, non-commercial evaluation only.

All main values use +/-2 actual processing frames = 16.667 ms.

| Game | Mode | P | R | F1 | FP/min | FN/min | Review/min |
|---|---|---:|---:|---:|---:|---:|---:|
| game_1 | A | 0.6429 | 0.6149 | 0.6286 | 4.47 | 5.04 | 18.12 |
| game_1 | B | 0.6447 | 0.6087 | 0.6262 | 4.39 | 5.12 | 17.55 |
| game_1 | C | 0.6443 | 0.5963 | 0.6194 | 4.31 | 5.28 | 17.88 |
| game_1 | D | 0.6667 | 0.5963 | 0.6295 | 3.90 | 5.28 | 17.07 |
| game_2 | A | 0.3832 | 0.4687 | 0.4216 | 12.59 | 8.86 | 35.25 |
| game_2 | B | 0.4034 | 0.4712 | 0.4347 | 11.62 | 8.82 | 32.86 |
| game_2 | C | 0.4090 | 0.4787 | 0.4411 | 11.54 | 8.70 | 32.95 |
| game_2 | D | 0.4450 | 0.4862 | 0.4647 | 10.12 | 8.57 | 29.94 |
| game_3 | A | 0.3526 | 0.4408 | 0.3918 | 11.94 | 8.25 | 30.00 |
| game_3 | B | 0.3626 | 0.4342 | 0.3952 | 11.26 | 8.35 | 27.86 |
| game_3 | C | 0.3568 | 0.4342 | 0.3917 | 11.55 | 8.35 | 27.48 |
| game_3 | D | 0.3846 | 0.4276 | 0.4050 | 10.10 | 8.45 | 25.92 |

| Aggregate | TP | FP | FN | P | R | F1 | Review/min |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 353 | 479 | 359 | 0.4243 | 0.4958 | 0.4573 | 29.56 |
| B | 352 | 448 | 360 | 0.4400 | 0.4944 | 0.4656 | 27.71 |
| C | 353 | 448 | 359 | 0.4407 | 0.4958 | 0.4666 | 27.75 |
| D | 355 | 394 | 357 | 0.4740 | 0.4986 | 0.4860 | 25.64 |

A = unchanged v0.2; B = Ball+Table; C = Ball+Player; D = Ball+Table+Player.

Experiment config SHA256: `9703ec102f0bf11ff545ee2772ebea16fd708d7e8a52d6693fafe1ceb22ba530`.

D reduces decoder FP by 85 (17.75%), increases TP by 2, raises precision by 4.97 percentage points and recall by 0.28 percentage points. All three games improve precision and F1, although game_1 loses 3 TP and game_3 loses 2 TP.

Player evidence alone (C) reduces FP by 31 with aggregate TP unchanged; this is a modest contribution, not a dramatic gain.

Review D: TP392 / FP801 / FN320, P0.3286 / R0.5506 / F1=0.4115.
At 3 seconds per candidate, a 45-minute match implies about 1154 candidate clicks and 57.7 review minutes, versus 1330 clicks / 66.5 minutes for A. This is an assumption, excludes playback/correction/creation time, and is not measured human efficiency. Review mode is not yet practically validated.

Research promotion proposal: HIT_EVENT_V0_3_DEV_READY, based on the preregistered DEV-only guardrails. This is not PRODUCT_READY or AUTO_READY. Desktop remains unchanged.
Calibration is a worthwhile next research check, but game_4/game_5/official TEST were not run and still require a later explicit scope change.

Ball kinematic event types still overlap. Camera-dependent spatial priors improve the tradeoff but do not establish reliable automatic bounce/net recognition. Player roles and striking-side mapping remain unconfirmed; no side-accuracy improvement is claimed.

Original v0.2 artifacts remain intact. Large data and output media remain outside Git under PTTI-Dev.
