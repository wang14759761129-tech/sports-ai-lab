# GOAL12.5 candidate handoff

Base: a3b21016b9073dc41d4992084ddb4ac6841469a0
Core: 304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe (vendored, checked before/after build).

## Confirmed defect and minimal fix
Cinema and Pro both kept active=true, so their navigation did not run the existing pause-on-hide effect. App now passes page + Insight/Review focus through the mounted workspace. A changed navigation key cancels the queue then pauses the existing controller; it does not destroy the video/session or clear notes. Existing snapshot subscription remains responsible for control state.

No new playback engine, identity promotion, source data or navigation architecture.
Existing export catch reports pro.targets.exportError and does not clear notes. New lightweight test exercises that failure branch. A successful browser download is not proven by these tests.

## Executed
- check:review-navigation PASS (actual effect body exercised with controller spy; unchanged navigation, three route transitions, export failure). Initial test extraction failed on CRLF; normalization fixed and rerun PASS.
- check:cinema-experience PASS; check:cinema-insight PASS.
- check:review-comparison PASS: real Golden point IDs, only two session-playable rows, p006 unavailable, note/facts separation and inert special text.
- check:playback-adapter PASS: 53 assertions.
- npm run build PASS: TypeScript, Vite, fixed Core pre/post checks; public0 and internal-review exclusion PASS. Existing >500 kB bundle warning remains.
- git diff --check PASS.
- check:match-library FAIL/asset BLOCKED: missing ignored .alpha-qa/match-library/internal-review.json and its associated import receipt in isolated candidate. This is an old internal-snapshot test dependency, not a production asset. No substitute data created. Internal-library full regression remains unverified; public build exclusion passed separately. Restore only an authentic audited snapshot + receipt to rerun it, never ship them in dist.

## Browser gate
Available RAM measured 1.356 GiB, below 2.5 GiB. Chrome NOT_STARTED / BLOCKED, no retry, no screenshots or actual browser download created this round. Node comparison artifact is not a browser download.

## Next single bounded acceptance
On this candidate only, with RAM margin: Cinema 1366x768 and390px, zh/en; load SIMULATED_ONLY 19-point data into Insight (no bundled video); select synthetic local video; manually confirm/save p002/p004 session boundaries while p006 stays unavailable; replay; navigate Cinema/Insight/Review and verify paused/cancelled snapshot with retained video and note; export/download actual JSON and compare identity, point IDs, simulated label and literal human note. Check invalidation on boundary revoke and media change. Session association remains LOCAL_SESSION_ONLY, never independent media verification.

Ready for conditional release-owner browser review, NOT ready for automatic activation or claims of full end-to-end PASS. Stable services, desktop launcher and installed candidates unchanged.
