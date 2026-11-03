# GOAL12.7-S Insight no-video onboarding

Parent: e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3.
Development worktree: C:\PTTI-Worktrees\web-goal12-7-insight.
Branch: codex/ptti-goal12-7-insight.
Core: 304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe, unchanged source/hash.

## Actual changes
The frozen implementation already had a local-file input and a file-change early return on cancellation. These are retained. The actual dead end was that the entire annotation/Insight column required a media session. Loading the19-point demo therefore could not show the formal statistics panel.

The layout now appears when a media session OR existing point records are present. The video column alone remains session-gated. The formal statistics panel includes a bilingual SIMULATED_ONLY/no-included-video explanation, uses the existing file input, and provides a real Cinema callback. The Pro route does not duplicate the Cinema intro grid. Selecting a file does not validate correspondence with simulated points; original binding/confirmation guards stay unchanged.

Navigation still cancels before pausing. If playback or a paused playlist was active, a status message explains that playback ended while the current video is retained. Actual resumed playback clears the message; no automatic resume is added. The existing note/session lifetime is unchanged.

Buttons wrap, have minimum44px height, and become full-width below480px. No new navigation system or player.

## Executed PASS
- check-insight-media-guidance.mjs: actual React server rendering in zh/en for simulated and normal states, no video markup, select/return callback execution, actual cancelled-file handler execution with empty/null file lists. Real19-point fixture import and visibility/wiring contracts are checked. These are component/Node checks, not browser interaction.
- check-review-navigation.mjs: actual effect body cancels then pauses; active playback displays feedback and idle navigation does not; no note/session clearing; export-failure guard retained.
- check-cinema-insight-navigation.mjs: validated import path and active-session preservation contract.
- check-cinema-experience.mjs and check-review-comparison.mjs: existing contracts PASS before the final statistics visibility adjustment; relevant navigation and playback checks rerun afterward.
- check-playback-adapter.mjs:53 assertions PASS, including unconfirmed/mismatched-session ranges.
- TypeScript --noEmit PASS after final code changes.
- git diff --check PASS.
- Core source/archive pin PASS. On this new Windows checkout only, Git autocrlf changed initial working bytes. Restored the same frozen blob's exact bytes; Core has no Git content diff or version change.

## NOT_TESTED
No Chrome launched and no new build performed this round. Browser dialog cancellation, actual rendered390px geometry, live navigation snapshot/message timing, playback and downloaded JSON remain browser acceptance work. Responsive CSS and handler tests do not substitute for them. No RAM BLOCKED claim is made for this round (one early read was4.385GiB); scope focused on requested low-resource unit checks and TypeScript.

The historical check-match-library still lacks its authentic ignored audit snapshot and is not claimed PASS. Frozen candidate/QA worktree/release status, stable services4174/4176/4177, R4 and desktop launcher remain unchanged. No push/deploy/promotion.
