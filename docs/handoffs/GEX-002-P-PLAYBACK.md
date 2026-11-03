# GEX-002-P / PLAYBACK DEX — Private Theater adapter

Status: PROPOSED candidate instruction; requires activation by Founder. No stable merge or deployment.

## Goal and value
Let Cinema save and revisit a real media position without losing source identity, crossing rally boundaries or leaking media resources.

## Verified starting evidence
WORK observed `C:\PTTI-Worktrees\playback-recovery-sprint-0-3` HEAD `b54e1546b7e6c1edc69406582ed68e90988a1910`. Inspected GOAL14-WATCH-ROUTING-HANDOFF.md: contract ptti.watch-routing/0.1; pinned Core `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`; ELIGIBLE/SCORE_ONLY/BLOCKED separate from VERIFIED/NOT_TESTED/FAILED. Working-tree status/runtime UNVERIFIED. Recheck before implementation.

## Scope
Allowed: isolated Playback-owned adapter, contract tests and handoff. Forbidden: frozen core changes absent separate approval, SAN stable page edits, Host launcher, production DB, official stream extraction or platform access circumvention. Read local AGENTS; preserve user changes and resource guards.

## Inputs / dependencies
GEX-001 Cinema flow; Main GEX-002-M candidate identity/time contract; current RallyPlaybackBinding and duration/start/end confirmation fields. If Main contract unavailable, write clearly proposed adapter types and synthetic fixtures only; do not invent agreed protocol.

## Steps
1. Record branch/HEAD/status, inspect actual public API and source pin verification.
2. Define explicit load, ready, playing, paused, seeking, ended and error transitions exposed to SAN; source switch resets state atomically.
3. Provide read-position and seek-to-moment bindings tied to exact current video identity and valid time bounds. Reject wrong media or unknown duration/boundary where unsafe.
4. Pause on route leave; dispose owned listeners and object URLs on replacement/unmount; prevent an asynchronous prior load from replacing a newer source.
5. Keep eligible official-site fallback a user choice. Do not auto-redirect or call displayed UI a successful playback test. Keep local files on device.

## Tests / success evidence
Play/pause/seek, invalid/mismatched identity, source switch race, repeated mount/unmount, ended/error recovery and cancellation. Use owned or explicitly permitted test media. Report time progression and frame change separately from audible output. Browser acceptance and Windows native engine acceptance are independent; list unavailable environments.

## Rollback
Candidate adapter commit only; frozen core pin and stable listeners remain unchanged. Do not terminate other lanes’ sessions.

## Final receipt
PTTI WORK REPORT with full commit, actual root/status, adapter API, source pin, changed files, commands and exit codes, runtime/browser evidence, rights of test media, limitations, rollback and exact SAN handoff. Mark all not-run checks PENDING/BLOCKED.
