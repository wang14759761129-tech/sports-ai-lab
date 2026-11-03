# GOAL12.6-S browser evidence harness

Status: PREPARED / browser NOT_TESTED. This is QA tooling, not a new product release.
Frozen application: e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3.
Playback Core: 304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe.
Independent worktree: C:\PTTI-Worktrees\web-goal12-6-qa.
Only qa/goal12-6 is changed; application source remains identical to the frozen commit.

## Low-memory preparation checks

From this QA worktree, run:

```powershell
node --check qa/goal12-6/prepare.mjs
node --check qa/goal12-6/acceptance.mjs
node --check qa/goal12-6/create-test-media.mjs
node qa/goal12-6/acceptance.mjs
node qa/goal12-6/check-preparation.mjs
```

Default acceptance invocation never starts a service/browser. check-preparation validates actual Golden canonical identity through the existing Main-compatible consumer, the 19-point count and producer IDs p002/p004/p006. These are Node results, not browser acceptance.

Windows autocrlf was observed to change vendored Core bytes in the new checkout. prepare restores ONLY this QA worktree's Core file from the exact frozen Git blob after verifying SOURCE_PIN SHA, then reruns the existing verifier. It does not normalize arbitrary source, change the frozen candidate, or weaken the byte check. To repair only this checkout before lightweight checks:

```powershell
node --input-type=module -e "import {restoreQaCoreBytes} from './qa/goal12-6/prepare.mjs'; await restoreQaCoreBytes()"
```

## Explicit future execution, once resources permit

Prerequisites: Windows, existing Chrome, Node, local ffmpeg with libx264, and Playwright module below. Do not install global browsers/frameworks. If local QA node_modules is missing, run the existing lockfile install in products/ptti-web only (`npm ci --ignore-scripts --no-audit --no-fund`); this does not authorize a public deployment. Preparation build requires 3 GiB available. Runtime requires three launch samples spaced10 seconds apart, each >=3 GiB (2.5 hard gate +0.5 margin), then a one-second RAM monitor and checkpoints maintain >=2.5 GiB. Maximum execution time is 180 seconds, one browser/context/page. No retries or user-process cleanup.

```powershell
node qa/goal12-6/prepare.mjs .alpha-qa/goal12-6-build
node qa/goal12-6/create-test-media.mjs
$env:PTTI_PLAYWRIGHT_MODULE='<LOCAL_USER_ROOT>\AppData\Roaming\npm\node_modules\cognee-openclaw-skills\node_modules\openclaw\node_modules\playwright-core\index.mjs'
$env:PTTI_QA_SYNTHETIC_MP4='C:\PTTI-Worktrees\web-goal12-6-qa\.alpha-qa\goal12-6-media\SYNTHETIC-TEST-PATTERN-60s.mp4'
$env:PTTI_QA_MEDIA_RECEIPT='C:\PTTI-Worktrees\web-goal12-6-qa\.alpha-qa\goal12-6-media\media-receipt.json'
node qa/goal12-6/acceptance.mjs --run
```

Environment changes affect only this shell; do not persist them globally. Existing media file will not be overwritten. The generator creates a 60-second original test pattern, no real players/audio, with local SHA receipt; only files below20MiB with matching synthetic receipt are accepted. Receipt is an input-integrity record, not an independent authenticity or rights certificate.

The build uses existing local-rc mode and pinned Core, in QA-only output. It is not the frozen public dist: it has the same verified application source with the existing local-demo flag enabled. qa-build.json records the distinction, source commit, Core SHA, output hashes and fixture byte hashes. No release registration or activation occurs. Serving uses an OS-assigned loopback port and an exact file allowlist, not4174/4176/4177 or any running service. Only actual synthetic Golden fixtures are exposed in the demo endpoint; no internal library or private reports. The QA HTTP server does not claim deployed HTTPS response-header acceptance.

## Ten checks in one flow

1. Cinema's local-video / simulated-review / third-party-source entrances.
2. Actual 19-point Main Golden load, automatic Insight route and canonical identity, no video initially.
3. Original synthetic local video, fresh blob session, explicit separate p002/p004 boundaries saved.
4. Real advancing playback and completion of p002/p004/p002; Seek observed.
5. p006 stays disabled and not session-playable.
6. Start continuous playback before each Cinema/Insight/Review transition; verify paused/cancelled controls, same video element/blob URL and two eligible rows.
7. Literal human note retained across all three routes.
8. Actual Playwright download event, save/read JSON; check canonical identity, SIMULATED_ONLY, count3, all IDs, two LOCAL_SESSION_ONLY rows, p006 NOT_PLAYABLE, no persistent playback authorization, independent verification0 and exact human text.
9. Chinese/English x1366x768/390px screenshots for Cinema/Insight/Review/Explore; selected-language state and horizontal overflow assertions.
10. Controlled URL.createObjectURL exception only during export; check actual application error and unchanged note, restore API afterward. This tests the application's catch path, not every OS download failure mode.

The 19-point data is synthetic analysis, not an included match recording. Main point_ids confer no media rights. Manually confirming boundaries associates synthetic test-pattern time only within the current browser session. It never proves true match alignment, real-player performance, independent media identity or copyright authorization.

## Evidence and failure diagnosis

Each explicit run creates .alpha-qa/goal12-6-runs/<UTC timestamp>/:
- report.json: source/Core identity, QA HEAD, runtime environment, ten independent statuses, RAM samples/minimum, errors, attempted blocked requests, download hashes and elapsed time.
- interaction.jsonl: immediately appended step/request/clip/navigation events; sequence survives a later failure.
- cinema/insight/review/explore zh/en1366/390 PNG files only after real screenshots succeed.
- actual-browser-review.json only after a real browser download; never synthesized by Node to substitute for it.

Use failure.step and interaction timestamps to reproduce only the failed action. Failed step=FAIL; untouched later steps=NOT_TESTED. RAM/preflight guard=BLOCKED; completed steps retain PASS. A runtime guard closes only the browser launched by this harness, then its own ephemeral server. page_errors and blocked external/upload attempts prevent overall PASS. Download parsing/field mismatch fails step8 and leaves the downloaded file for inspection. Missing Playwright, ffmpeg, build receipt or wrong source identity is recorded as setup failure; fix the stated prerequisite before one later run. No automatic retries.

## Current acceptance boundary

GOAL12.5-B remains BLOCKED: recorded available RAM2.018/2.012GiB; zero Chrome instances, screenshots and downloads. This preparation round does not change those results. check-match-library still lacks its authentic ignored historical internal snapshot/receipt, so it is NOT_PASS. The new harness does not fabricate or restore internal data.

Release status remains frozen/pending browser acceptance. Real-video accuracy, real users, sound, device compatibility, installed4177 behavior and public release are NOT_TESTED by this harness. No launcher, stable product, other worktree, deployment or CI action is part of these commands.

## GOAL12.7-Q update

The shared runner now uses resource-guard.mjs (including launch-time monitoring and tested abort/evidence handling). The old no-config target remains e788e2f. For candidate825805 and its separate source/build/evidence paths, use ../goal12-7/README.md and insight.config.json. Simulated guards do not prove real Chrome acceptance.
