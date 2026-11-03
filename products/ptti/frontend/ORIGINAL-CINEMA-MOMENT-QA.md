# Original Cinema + Moment: isolated MAIN candidate

## Identity and scope

- Original visual/source reference: `5cc753886b112305736fcc14ea77b37662726c9f`.
- Candidate starts from MAIN `54d75007eb7dc63e33dd8ac419afc20cf7e2615c`, which contains both GEX-03D `c6b0a94...` and GEX-03E monitor fix `4915980...`.
- The separate official metadata PoC `f895441...` remains intact and is not merged into this candidate.
- Selective integration uses the already prepared `ffc86c7...` bridge. Its two untouched GEX-06R evidence/event dependencies match `71ff6af...`; Moment import is adapted with a stale-storage check. No GEX-06R homepage, HTML or CSS is copied.
- `VideoFeed.tsx` remains the R4 wall. `video-feed.css`, catalog/media permission, Story, official watch routing, favorites and original Fan Arena engine are unchanged from MAIN `54d7500`.

## What is integrated

The existing compact `快捷入口` exposes Moment Cards, Pro Lab and Arena. When the Cinema catalog is loaded, the extra four-space navigation row is hidden so that the wall begins closer to the founder's 5cc reference; it remains visible in the other spaces and when the catalog is unavailable. Founder visual review is available from the same compact menu in internal QA. Search, selection and scroll state use existing state logic.

Only in `INTERNAL_FOUNDER_QA`, Pro Lab can select a local video, compute its content identity after an explicit click, preview a compatible GEX-06R Moment JSON, confirm an additive restore, and seek the same local HTML5 video. A mismatched video, unsupported envelope, invalid timestamps, oversized JSON, storage error, stale preview, or an intervening storage change prevents the write. The pre-write comparison detects already-completed changes; localStorage provides no atomic cross-tab compare-and-swap guarantee. Use an isolated QA browser profile/origin for the test. This bridge does not seek an official YouTube iframe and does not bind private video to a professional match.

Existing Moment Cards already provide official-link time markers and JSON export. Existing Pro Lab notes already support local capture/seek. Existing Arena remains a single-game `SIMULATED_ONLY` prediction experience. GEX-06R event-to-video, Rally playback, PoseEvidence UI, Vision changes and complete GEX-06S integration are not included in this first-stage bridge. The exact GEX-06S source/commit was not identified during this audit.

## Actual evidence

- PASS: in-memory Moment identity/preview/restore, wrong-video/time/JSON, quota, stale-preview and already-changed-storage guards.
- PASS: the existing synthetic `rally.mp4` and `roundtrip-example.json` produce the same content identity and two restorable Moments in a Node logic check. No GUI playback or seek is inferred.
- PASS: Pro Lab React SSR and existing-note safety, Feed/Story, compact-navigation SSR, thumbnail runtime and media distribution gate, original Fan Arena engine, and TypeScript project check.
- The preserved historical GEX-03E `thumbnail-results.json` records 8/8 YouTube images decoded at 1440 px, with the Bilibili card falling back. This is historical internal QA evidence, not a new-candidate test or distribution grant.
- BLOCKED / NOT_TESTED: candidate screenshot, same-size 5cc comparison, candidate 8/8 image decode, local file selection, actual video playback/seek, browser navigation and Windows Native. Memory later recovered above 2.5 GiB on 2026-10-28, but the single isolated QA API/Vite startup command was rejected before execution by the automatic execution policy (`blocked by policy`). No QA service, browser or Native instance was started; no alternate route was attempted.

The founder's supplied 5cc screenshot shows no additional four-space row. The historical GEX-03E screenshot does show that row, a Founder QA notice, `contain` image fit and additional card actions. Hiding the row is a code change addressing one observed density difference; the candidate has not been visually proven identical to the founder's screenshot.

## HOST visual QA handoff

Only after the established resource guard permits a browser session, prepare a unique loopback QA API and isolated browser profile with explicitly verified temporary `PTTI_DB` and isolated `LOCALAPPDATA`. Confirm both the resolved database path and API identity before starting the frontend; do not reuse a production API/DB or the already running user's profile. Founder QA Vite requires an explicit `PTTI_FOUNDER_QA_API=http://127.0.0.1:<isolated-port>`, and the normal distributable mode must retain its media gate.

1. Compare founder's original 5cc image and the actual new candidate at the same desktop viewport and scroll position: 4 columns, 16:9 cards, navigation, filters, stars, title hierarchy and density. Record the 8/8 individual QA image statuses and fallback separately.
2. Open the existing compact menu → Pro Lab. Select the synthetic local video from `C:/PTTI-Worktrees/gex06r-moment-restore/products/ptti-web/prototypes/gex06/media/rally.mp4` and wait for metadata. Click `启用 Moment 恢复`, import the corresponding `qa/roundtrip-example.json`, preview, confirm, and click a restored time. Observe actual playback/seek; then return to the wall and check search/filter/scroll.
3. Verify Story/favorites and Arena entry in the isolated QA environment. The Arena's simulated points must not be presented as real video events. Do not bypass YouTube embed restrictions.
4. Capture candidate screenshots and report each browser/Native/playback outcome separately. The existing GEX-03E screenshot is a reference only; it cannot serve as candidate evidence.

This is a source candidate, not a release. No EXE, launcher, production database, personal media, public assets or deployment was modified. `scripts/dev_sync.py` was not run because it would create/activate desktop output outside the founder's authorization.
