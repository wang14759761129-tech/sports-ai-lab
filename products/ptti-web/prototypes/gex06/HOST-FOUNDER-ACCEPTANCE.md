# GEX06R Restore + Event Arena — manual acceptance

Owner: new isolated `C:/PTTI-Worktrees/gex06r-moment-restore`, branch `codex/ptti-gex06r-moment-restore`. Start with `node products/ptti-web/prototypes/gex06/serve.mjs` or the same command plus a previously used free port. Strict loopback only; never kill a listener. The printed URL/runtime.local.json identify this candidate, not old 51886.

## Existing browser manual route
No need to release RAM or launch another automated browser. Founder can manually open the candidate URL in their already-open browser. Automated testing still requires all RAM/idle/control guards.

1. Cinema → Use PTTI original test video (or a private video you have rights to). Observe moving frames, pause and drag. Confirm time changes visibly; a poster alone is not PASS.
2. Moments → save two different timestamps with notes. Export JSON; verify a real downloaded file exists.
3. Clear this video's Moments with the explicit confirmation. Verify only Moments disappear.
4. Import that downloaded JSON. Preview should show two additions. Cancel first and check no change. Repeat, confirm and check both records appear. Repeat import and check zero additions/two duplicates.
5. Click restored Moment: real video jumps to the matching frame/time. Refresh, reselect identical bytes, verify records remain. A renamed identical file should match; a different file must not.
6. Arena starts 9:9. Choose A, lock, then Reveal. The video should actually play to the mock timestamp before score changes. Double clicking must score only once.
7. Advance through all four events. Expected scores: 10:9,10:10,11:10,12:10. Compare history: four unique IDs, each prediction and result. These are MOCK events, not observed points.
8. Continue watching → return Arena: round remains. Replay current revealed event: score unchanged. Full reset: 9:9, zero predictions/history. Check the unrevealed retry unlocks a choice without scoring.

## Minimal evidence (do not expose private frames)
Use the bundled synthetic asset for screenshots: Cinema, restored Moments, import preview, final Arena event history. Record candidate commit/URL, pass/fail per step and browser-reported playback failure if any. For private video use text-only sanitized observation; do not capture private notes, file paths or frames.

Current agent status: 31 offline test groups; GUI, browser seek, import file picker, real download, refresh restore and reveal animation NOT_TESTED. One preflight below 3GiB stopped automation; no bypass/retry. Manual Founder testing is permitted, not declared impossible.

## Preserved
Original San worktree and both existing services remain untouched. d94bccc2 remains in Git. No R4/Main/Launcher/production DB changes, no push/merge/deploy. Stop only the new prototype process to roll back. Do not use this request to start a Desktop build or change a release pointer.
