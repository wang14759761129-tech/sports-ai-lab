# GOAL14 Main Content Admission v0.1

## San-consumable package

Build the narrowly scoped public sample from the repository root:

```powershell
python products/ptti-integration/scripts/build_goal14_main_public_admission.py --generated-at 2026-10-18T00:00:00Z
```

Output:

`products/ptti-integration/generated/goal14-main-admission/match-library-strict-public.json`

This is the existing `ptti.match-library-index/0.1` `STRICT_PUBLIC` contract consumed by San's current `consumeFanCatalog`. It contains one reviewed Match, one official YouTube VideoSource, and two registry-backed athlete records. The existing Goal 11 strict-public output remains unchanged and empty; San must consume this package only after integrating this specific reviewed artifact, never by falling back to internal review data.

## Exact reviewed chain

- Match: `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun` (PTTI internal stable ID; no provider match-level ID was found).
- Source: `video-source:youtube:0QgbtsBWZhk` / YouTube video ID `0QgbtsBWZhk`.
- Athletes: `athlete:121558` WANG Chuqin and `athlete:135977` Felix LEBRUN.
- Match-to-video association: exact official WTT video metadata explicitly names these players, the Men's Singles Final and China Smash 2025; official WTT event result material reports the same final and 4-0 result. This is a source-metadata identity cross-check, not independent visual-content verification.

## Rights and playback scope

The only user-facing watch action is a link to the official YouTube page. YouTube Help describes copying a video link for sharing elsewhere. The package does not embed the video, display a thumbnail, copy a media frame, or grant local analysis, download, or redistribution rights. WTT's video description states ©WTT and says images require prior approval before reproduction.

The current page's live access, territory, login/paywall condition, visual playback, completeness, embedding permission, Desktop Native playback, Vision analysis, and current-session eligibility remain `NOT_TESTED` or `UNKNOWN`. A historical embed error 150 is retained as `EMBED_BLOCKED_HISTORICAL`; it is not a current playback result.

`public_listing=ALLOWED` is scoped to factual names, event/match summary and source attribution only. `external_viewing=ALLOWED` is scoped to the official platform share URL only. Neither value grants media rights. Thumbnail display is `NOT_ALLOWED` without prior approval; embedding stays `UNKNOWN`; local analysis and redistribution are `NOT_GRANTED`.

## Verification

```powershell
python -m unittest products.ptti-integration.tests.test_goal14_main_public_admission -v
```

The Main test asserts the reviewed identity edge and rejects mismatched IDs/title/round, missing link evidence, overbroad link scope, permission escalation, and false playback/territory upgrades. The generated package can additionally be passed read-only to San's `products/ptti-web/src/fan-catalog.mjs` consumer.
