# GOAL 12.3-G Candidate Acceptance Handoff

## Candidate identity and execution boundary

- Candidate worktree: `C:\PTTI-Worktrees\web-mvp-v0-1-goal12-1-candidate`
- Branch: `codex/ptti-goal12-1-candidate`
- Previously reported candidate SHA (not found in this object database): `f39359a169e597bad7a514adcfc0f0601bdb2fbe`
- SHA observed in this worktree before this handoff: `f39359a169e597bad7a514adcfc0f060134ed322`
- GOAL 12.3-G acceptance handoff commit: `62f048dabf4567a0f9736c7f7f663546a24b6545`
- Playback Core reference: `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`
- Worktree was clean before this handoff's edits. The only code change in this handoff is a lightweight source-contract regression in `scripts/check-cinema-experience.mjs`.
- Current available RAM at review: `1.21 GiB`; Chrome gate: `2.5 GiB`. Browser execution is **BLOCKED / NOT RUN**.
- No screenshots were generated, and no browser interaction or browser export is claimed in this handoff.

## Version identity correction (GOAL 12.3-L)

The observed baseline `f39359a169e597bad7a514adcfc0f060134ed322` is the actual GOAL 12.2 delivered commit and the direct parent of the GOAL 12.3-G handoff commit above. The previously reported value `f39359a169e597bad7a514adcfc0f0601bdb2fbe` does not resolve to a commit in this candidate repository. Available local evidence proves the parent chain but cannot determine whether the differing SHA came from transcription or another object database/worktree; cause remains `UNKNOWN`. This note preserves the original discrepancy without changing Git history.

## Release acceptance checklist

### Cinema and responsive presentation

- [ ] At `1366x768`, Cinema keeps the video as the visual priority and makes all three entries visible: local training video, `SIMULATED_ONLY` 19-point review demo, and sourced external match pages.
- [ ] At `390px`, there is no horizontal overflow; bilingual Explore cards do not cover or obstruct usable controls.
- [ ] With the 19-point demo loaded and no local video bound, Insight shows a clear no-video/no-replay empty state.
- [ ] External match sources are labelled as third-party source links. Opening a source page is not described as PTTI playback success or proof of media rights.
- [ ] Explore bilingual cards show coarse observed rally groups, sample/denominator cautions, and manual annotation guidance without converting stage groups into technical diagnosis.

### Playback, navigation, and review evidence

- [ ] p002 and p004 become replayable only after both boundaries are reconfirmed and saved in the current local video session.
- [ ] p006 remains unplayable while its boundaries are unconfirmed; the UI explains why.
- [ ] Navigation away from the player pauses playback and cancels the active queue while retaining the mounted video instance and current session. Returning to Insight shows controls/status derived from the current playback snapshot.
- [ ] Review notes remain available across navigation for the same target/session; changing the session or target follows the product's explicit note association/reset behavior.
- [ ] Exported JSON is checked against the active Review Targets identity, protocol, point IDs, current local-session replay-state snapshot, and the exact user-entered note. Export does not grant persistent replay authorization.
- [ ] Interaction evidence is retained as a redacted event log and the actual exported JSON artifact. Screenshots alone do not satisfy these checks.

## Required browser evidence files

Capture only from the isolated candidate after the RAM gate is met. Do not reuse screenshots from 4174, 4176, or 4177.

| Evidence | Required artifact | Status |
|---|---|---|
| Cinema desktop | `artifacts/goal12.3/cinema-1366x768.png` | NOT TESTED; Chrome not started |
| Cinema mobile | `artifacts/goal12.3/cinema-390.png` | NOT TESTED; Chrome not started |
| Insight no-video state | `artifacts/goal12.3/insight-simulated-no-video.png` | NOT TESTED; Chrome not started |
| Explore bilingual cards | `artifacts/goal12.3/explore-bilingual.png` | NOT TESTED; Chrome not started |
| Playback/session interactions | `artifacts/goal12.3/interaction-log.jsonl` | NOT TESTED; no browser interaction |
| Comparison export | `artifacts/goal12.3/comparison-export.json` | NOT TESTED in browser; a separate synthetic Golden logic-test artifact is not a browser download |

The interaction log should record event/result and sanitized identifiers only (for example: target ID, point ID, session changed/retained, queue stopped/rebuilt, eligible/ineligible reason). Do not include local video paths or media bytes.

## Lightweight evidence from this handoff

The source-contract check is intended to protect the requested navigation/session behavior: persistent Pro workspace mount, pause/cancel when hidden, player-controller lifetime tied to local session, playback status from the current snapshot, and export built from the matched report/target/current points/current bindings/current note/session. It does not prove runtime browser behavior.

| Check | Result |
|---|---|
| `node scripts/check-cinema-experience.mjs` | PASS: distinct entrances, `SIMULATED_ONLY` demo and no-video copy, persistent player mount, pause/cancel when hidden, current snapshot controls, same-session note behavior, export identity inputs, three bounded Explore guides, and bilingual source/sample wording. This is a source-contract test, not a browser run. |
| `node scripts/check-cinema-insight-navigation.mjs` | PASS: success/rejection/stale/error/duplicate-load navigation contract and active video-session preservation guards. This is a lightweight contract test, not a browser run. |
| `node scripts/check-review-comparison.mjs` | PASS: Golden point IDs p002/p004/p006; exactly two `LOCAL_SESSION_ONLY` rows; p006 unavailable for unconfirmed boundaries; system facts and user note separated; export grants no playback authority; malformed association rejected. |
| `git diff --check` | PASS; Git emitted only a line-ending normalization warning for the modified `.mjs` file. |
| Chrome screenshots and interactions | BLOCKED / NOT RUN: 1.21 GiB available RAM is below 2.5 GiB gate |

The comparison logic test produced `.alpha-qa/goal10-7-review-comparison-sample.json` (SHA-256 `72ded8403d58182efd8079dbbacd0280fd7d6d9b1e18f55438923b93176315d9`). It is an inspectable **synthetic Golden QA artifact** produced by the export helper, not a browser download or a real user's note. It records the Golden canonical input hash `ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5`, the three point IDs, two current-session rows, p006's `BOUNDARIES_NOT_CONFIRMED` reason, zero independently verified media, and separately labelled user-entered note text.

## Release-review readiness

**Not ready for release review.** The checklist and lightweight code guards are being prepared, but the required candidate-only screenshots, current-session playback interactions, navigation/session-retention observation, and browser-generated export comparison are missing. Revisit only when available RAM is safely above the unchanged 2.5 GiB gate; do not infer browser PASS from source checks or Golden logic tests.
