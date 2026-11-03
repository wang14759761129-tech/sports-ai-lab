# GOAL107 — original R4 official viewing integration

Baseline: 5653cd4c156150b5fe85879aff126e10c9896af7. Original product:
5cc753886b112305736fcc14ea77b37662726c9f. Main isolated worktree only.

## Actual product changes

- Existing VideoFeed card chooses its existing EMBED route for one exact reviewed
  source. A bounded catalog review binds 0QgbtsBWZhk, registered match ID, official
  watch URL, channel and GOAL106 evidence. Conflicts fail closed. No global embed
  switch; old Native failure remains unchanged. Permission is for an intact
  official-player attempt only, with no new media or analysis rights.
- Reuse OfficialVideoPlayer, not another player. The iframe uses autoplay=0,
  controls=1, enablejsapi=1 and the actual window.location.origin. Normal browser
  referrer policy is strict-origin-when-cross-origin; no forged Referer. Non-HTTP
  contexts are refused. Browser DOM measured 960×540, CSS minimum 480×270, with
  horizontal overflow on narrow viewports instead of shrinking below minimum.
- Live ready/playing/paused/error/timeout text is separate from historical
  playback_limitation. Official link uses the existing desktop bridge adapter and
  the existing copy recovery. Error 101/150/153 remains a failure, not a bypass.
- On exit or source change the official player is destroyed and its captured
  container emptied. A pending API promise checks the live flag and cannot
  resurrect a removed player. React owns the container, not the API-owned iframe.
- Return clears both official and Story state, restores the wall scroll and
  preserves existing component search/filter state. Story passes the canonical
  matched FeedVideo source, preserving exact identity and the same viewing gate.

## Actual browser scope

Real production React components VideoFeed, StudioShell, OfficialVideoPlayer and
LegacyMatchStory were loaded by the existing Vite tool. A temporary test harness
provided the existing catalog/registry shape and memory-only favorites; all other
backend fetches were rejected. No backend module, database, or user favorites were
read/written. This is a component integration browser test, not a full backend or
installed-Windows test. Temporary harness files/server were removed/stopped.

| Check | Actual result |
|---|---|
| Original wall | PASS: 9 cards; 4 columns measured 330.667px each at 1440px; feed.png |
| Exact 0Q card → internal theater | PASS |
| Preview, WTT channel/YouTube controls | PASS; no autoplay before user play |
| Real match playback | PASS: moving match image; first run 0:01→0:08→0:11, final player code 0:08→0:12; playback.png |
| Pause | PASS; final status explicitly changed to 官方播放器已暂停 |
| Official full screen / exit | PASS via official controls; not Native full screen acceptance |
| Back to feed | PASS; search 王楚钦 and 男单 retained; separate nonzero scroll test 180→theater 0→wall 180 |
| Unmount | PASS: zero remaining iframes on return; not a heap/GPU memory measurement |
| Story → theater → wall | PASS after final return-state change |
| Story save → Favorites navigation | PASS using memory-only favorite endpoint; existing storage schema unchanged |
| Product official link | PASS: exact watch URL opened, matching title and verified World Table Tennis publisher shown |
| Offline failure | PASS: tab-scoped network-offline test produced 未连接到互联网 and 12-second fallback notice; offline.png |
| Disabled embed 101/150 / identity 153 | Error paths implemented, actual provider rejection NOT_TESTED this run |
| Clipboard end-to-end | NOT_TESTED; existing copy/bridge unit regressions PASS |
| Windows Native/WebView2 | NOT_TESTED; actual origin/Referer delivery and provider acceptance must be verified there |
| Full video, Vision, analysis | NOT_TESTED / not granted |

Temporary viewport and offline settings were restored. No hidden iframe remains.

## Tests and remaining bounds

Commands from products/ptti/frontend:

```powershell
npm run test:official-theater
npm run test:feed
npm run test:goal99-story
npm run test:youtube-thumbnail
npm run test:match-photo
npm run test:media-distribution
npm run build
```

Scoped identity negatives, unmodified input/historical evidence, lifecycle source
contracts, Feed/Story/favorites, thumbnail and distribution gates PASS. Browser
tests above supply the separate runtime evidence. Full TypeScript and Vite build
PASS; no dependency installation. Available RAM before the build/browser phase
was 3.67 GiB, above the unchanged guard.

Seven other YouTube sources remain external-link routes with current in-product
embed/playback NOT_TESTED; they were not granted permission by copying the 0Q
review. Bilibili remains separate and unchanged. Future source admission must
bind its exact identity and separate observed evidence; do not infer it from this
one success. This is remaining P1 work, not eight-source acceptance.

Standalone real homepage covers restored: **0**. Player preview is neither a
downloaded image nor a homepage thumbnail permission. Existing photograph and
thumbnail gates, original four-column CSS, stable EXE, desktop entry, Launcher,
user databases/Journal/media and other worktrees are untouched. No Host build,
push, deployment or formal activation performed.
