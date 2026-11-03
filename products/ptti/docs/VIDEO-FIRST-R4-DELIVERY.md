# Video First R4 — source delivery

Status: VIDEO_FIRST_R4_PARTIAL / MANUAL_GUI_CHECK_REQUIRED.

## Implemented
- Three primary routes: Video, Matches, Vision. Secondary menu retains existing tools.
- Single four-column grid, three/two/one at narrower breakpoints; compact six discipline chips and collapsed filters.
- Video-first default for preview mode; no blocking initial onboarding in that mode.
- Session-scoped category/filter and scroll restoration; no source timeline conversion.
- Vision has a separate native HTML5 source player, permitted-source selector, explicit analysis-rights single-file opener, speed and fullscreen controls. Existing analysis jobs stay in collapsed tools.
- Analysis View remains disabled. No SHA/timeline-matched result was validated this sprint.
- Separate video-first-r4 build profile and development database. Old profiles remain available.

## Verification this sprint
- Final TypeScript project check passed.
- Frontend contracts: feed 28, shell 17, review 9, score 5, observations 12: 71 passing.
- An intermediate Vite build passed before final single-file Vision opener changes. Final Vite production rebuild not run after low-RAM stop.
- Python syntax and git whitespace checks passed. No full Python rerun.
- RAM fell below 2 GiB; latest sampling was 1.14 GiB. No Windows R4 package attempted.
- Existing browser host shows older runtime flags and is not R4 QA. No R4 screenshot, source-video playback, pause/seek/rate/fullscreen or native click PASS claimed.

## Content and boundaries
Public source inventory remains 18 unique platform IDs: MS 7, WS 3, MD 4, WD 3, XD 1. No new source discovery or playback verification. No local registration performed this sprint. No confirmed completeness, identity, score or Vision gate advanced.

Frozen Hit config SHA256 remains fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3. Production DB, official TEST, GAME_5 and model inference were not used.

## Remaining acceptance
On a resource-safe isolated QA runtime, verify Cinema and Vision independently using an authorized local source. Confirm actual frames after seek, rates, fullscreen and return context. Native acceptance remains required. Build with PTTI_PREVIEW_PROFILE=video-first-r4 and a short independent PTTI_PREVIEW_BUILD_ROOT only after the existing guards pass.
