# Measured PTTI bottlenecks — October 2026

Source: three complete Extended OpenTTGames TRAIN DEV videos; 46.522 minutes, 712 stroke events.
No Hit configuration changes or new training in this audit. ±2 processing frames = ±16.667 ms at 120 FPS.

## Priority 1: missing ball-position truth

12,741 unmatched Raw Hit candidates are event-level FP, NOT 12,741 proven wrong ball detections.
Stroke labels measure contact timing. They do not label the ball on every frame, every distractor or every gap.
The count of genuinely missing ball observations vs incorrect ball points is UNKNOWN for these complete videos.
Create reviewed ball points/absent frames and negative context windows before deciding which detector to replace.

## Priority 2: raw generator selectivity and unsupported side assignment

Raw: 13,261 candidates for 712 GT strokes; TP 520, FP 12,741, FN 192, recall .7303.
All candidate generation uses ball kinematics; full-video player evidence is absent and roles are UNKNOWN.
The ball-player proximity field is zero and the alternation constraint cannot validate real identities.
Every kinematic extremum is not a racket contact. Product inference does not receive bounce/net GT.
4,028 unmatched raw candidates fall within 100 ms of annotated BOUNCE, and 663 within 100 ms of NET.
These are non-exclusive temporal overlaps, not manually proven BOUNCE/NET error categories.
Nearby genuine strokes or annotation timing ambiguity can overlap those windows.

## Priority 3: raw misses and stage attrition

Of the 192 Raw FN, 94 have insufficient pre/post ball context and 98 have pre/post context available.
This is measured input-availability stratification, not causal proof: available coordinates may still be wrong.
Clustering loses another 64 GT matches. Decoder drops 63 more outside review and keeps 40 in review only.
Auto-selected matched GT = 353. Review mode recovers 393/712 but needs 29.55 candidates/minute.
Decoder P/R/F1 .4243/.4958/.4573; Review .2858/.5520/.3766. Neither is review-ready.

## Priority 4: missing full-video player evidence

Player evidence availability near GT = 0/712. Side accuracy is NOT_EVALUABLE.
Effect on Hit precision/recall is NOT_MEASURED: there is no same-video Ball-only vs Ball+Player ablation.
Do not claim that missing player evidence explains a particular percentage of errors.
The existing RT-DETR/SAM2 path can later supply sparse side/location evidence without expensive full-mask production.

## Priority 5: annotation and benchmark scope

Existing RacketVision native ball labels allow a sparse known-TRAIN detector comparison.
They cannot establish full-video FP/min or true trajectory continuity. Existing OpenTTGames TRAIN event labels
can evaluate downstream Hit timing after aligned ball/player evidence exists; they are not detector annotations.
PTTI Benchmark v0 must preserve these scopes, source/license hashes and unknown scene strata.
Human-reviewed annotation production is the next prerequisite; no new large model is justified by aggregate Hit FP alone.

RAM safety remains a practical constraint: previous full DEV worker peak ~1.34 GiB, lowest system available RAM ~1.31 GiB.
Use one model worker at a time and streamed outputs. Current system has a 16 GiB RAM / 8 GiB GPU class budget.
Saved reports are research-only and do not upgrade product gates.
