# Playback Recovery Sprint 0.3 — partial delivery, release blocked

Date: 2026-10-12 (Asia/Shanghai). Status: **DESKTOP_UPDATE_PENDING**.
This report does not claim that the original native Vision incident is resolved.

## Isolation and source identity

- Repository: the existing `research-integration` repository; no new project.
- Own worktree: `C:\PTTI-Worktrees\playback-recovery-sprint-0-3`.
- Branch: `codex/ptti-playback-recovery-sprint-0-3`.
- Base: `2c87a6433437f39bf85a9439cccf99709cce887e`, retaining the Origin regression added after the requested `3e0281242aa6b4590d898039cf4300d794c18dd9` baseline.
- Source/test commit: `cea065a7d64fd84c0ec15011083607426b4821b3`.
- Visual worktree verified: `C:\PTTI-Worktrees\premium-design-v1`, branch `codex/ptti-premium-design-v1`, also based on `2c87a64`. Its uncommitted `design-tokens.css` change was read-only inventoried and left untouched. No source file overlap at this inspection; recheck at integration.
- QA database: a private temporary QA path, made using SQLite read-only backup of the previous Sprint 0.2 **temporary QA** database. No reimport, rights change, user DB overwrite or video addition.
- API evidence uses one in-process TestClient/backend and the same snapshot for both endpoints. Proxy tests use dynamically allocated, distinct loopback ports; no persistent service, 8765 server, Launcher or desktop activation was started.
- Existing dependency tree is referenced by an ignored `frontend/node_modules` junction. Do not run dependency mutations through it; use separate dependencies before any dependency upgrade.

## Confirmed causes, fixes, and remaining uncertainty

### Vision misleading empty state: reproduced and fixed

`VisionPlayer.tsx` initialized `videos=[]` and rendered “当前没有已登记…” solely from `!videos.length`. This was true before its GET finished and after HTTP/network/JSON failures. Its catch displayed an error separately but never distinguished unsuccessful loading from a successful empty response, and offered no recovery request. A successful API query made independently cannot prove the earlier UI fetch succeeded.

The regression executes the actual TSX component in a deterministic hook host. Before the fix it failed with `Pending request must not claim there are no registered sources`. After the fix it passes with an authorized option and the same registered media URL. It also exercises HTTP 403, network failure, wrong response shape, retry, cancellation/late response, successful empty response and the unchanged rights/Analysis View gates. This is component logic evidence, **not native rendering or media decoding evidence**.

The minimal fix adds separate loading/ready/error state, HTTP status in the source error, explicit retry, response-shape validation, no-store loading and abort/late-response protection. Only a successful empty response may display the empty-library message. No rights are widened; media endpoints, native media controls and Analysis View's disabled state are preserved.

**Original persistent native list failure: NOT_CONFIRMED.** There is no captured failing native GET/status/Origin from Sprint 0.2. Current RAM prevents relaunching a candidate to obtain it. The confirmed empty-state defect cannot by itself prove why that native request did not populate. Do not describe this sprint as completed Vision playback recovery until a new candidate provides the missing request and interaction evidence.

### API/source comparison

See `PLAYBACK_SPRINT_0_3_SOURCE_EVIDENCE.json` and rerunnable `scripts/qa_vision_source_contract.py`.

| Field | Actual isolated QA source |
| --- | --- |
| Vision GET | `/api/video-evidence/videos`, HTTP 200 in the contract probe |
| Cinema GET | `/api/video-evidence/library`; contains the same source ID |
| video_id | `35d991ea-e610-487c-985a-7d5bf949ba5f` |
| source_sha256 | `1297b3db91f2e3e160337643695dff07eabf9785ea2d88c2f7b59687ba511148` |
| rights_status | `RESEARCH_NONCOMMERCIAL` |
| hash_status / availability_status | `VERIFIED` / `AVAILABLE` |
| Existing Vision filter | Accepts this exact rights status |
| Revised component using captured API rows | Same ID appears as an option; no invented registration |

Cinema uses a catalogue envelope (`videos` plus other catalogue collections); Vision uses a direct array. Both responses conform to their consumers. No evidence supports changing the API shape or authorization filter. New native process/DB/request correspondence remains NOT_TESTED.

### QA 403: exact proxy cause and safe configuration fix

Installed Vite's string proxy shorthand expands to `changeOrigin:true`: the forwarded Host becomes the upstream backend while the original browser Origin remains on the frontend port. The backend's existing local-file guard rejects the mismatch.

`vite.config.ts` now uses an explicit object with `changeOrigin:false`. Host and Origin remain the browser's origin; neither Origin rewriting nor removal is used. `PTTI_QA_API_TARGET` supports a separate worktree backend and validates a plain loopback HTTP origin. The default target remains unchanged.

The actual Vite test reproduces legacy mismatched headers, then verifies matching forwarded headers under the repaired config, plus an unchanged foreign Origin. Real backend tests verify forwarded same-origin GET=200, foreign/local-mismatched/null Origin GET=403; recent-view POST same-origin succeeds and mismatched Origin remains 403. **No CSRF, cross-origin, file identity or analysis Gate was disabled.** This proxy fix concerns browser QA; it does not establish the root of a packaged same-origin native failure.

## Tests and resource outcome

| Check | Result / scope |
| --- | --- |
| New Vision component regression | PASS; old code red, repaired code green |
| New actual Vite proxy regression | PASS; legacy mismatch reproduced; repaired headers and foreign-origin preservation verified |
| Targeted Python tests | PASS, 15 tests in 12.90 s: new listing guard, recent views, 13 external-link tests; one existing Starlette warning |
| Existing frontend contracts | PASS: feed 31, studio 17, review 9, score 5, score observation 12 (74 total) |
| Official playback recovery tests | PASS, bridge failure/default-anchor and clipboard/manual-copy recovery logic |
| Isolated real-source API/TSX comparison | PASS; no native GUI claim |
| Broader selected Python playback suite | INTERRUPTED for RAM pressure; not a successful suite, no total PASS claim |
| Full regression / TypeScript+Vite production build | NOT_TESTED in this sprint |
| `git diff --check` | PASS |
| `dev_sync.py` after source commit | BLOCKED: `need 2.5 GiB start RAM; hard floor remains 2 GiB` |

Available RAM snapshots ranged from about 1.78 GiB at initial isolation to about 1.04 GiB under test pressure, then about 1.47 GiB after stopping the owned broader test process. Only this sprint's matching pytest launcher/child processes were stopped; no user programs were terminated. No heavy build, model inference or candidate/native startup was attempted below its guard. Dev-sync was invoked with a temporary deployment root, dedicated build root and no release acceptance, and exited at the initial resource check before creating a package or activating anything.

## Native acceptance table

Historical Cinema observations were supplied by the user for Sprint 0.2's old candidate. They do not satisfy acceptance of changed code.

| Scenario | This sprint / new candidate | Prior evidence |
| --- | --- | --- |
| Cinema game_1 play/pause/seek/fullscreen/return | NOT_TESTED | Old candidate play/pause/seek/fullscreen observed; return not transferred to new code |
| Vision lists/selects same authorized source | NOT_TESTED natively | Component/API contracts PASS; old native list incident unresolved |
| Vision real play/pause/seek | NOT_TESTED | No new native evidence |
| Vision speed selection | NOT_TESTED | No new native evidence |
| Accurate playback-rate measurement | NOT_TESTED | Selecting a rate does not measure speed |
| Vision leave/media release/re-entry/play | NOT_TESTED | No new native evidence |
| Analysis View remains disabled | NOT_TESTED natively | Component regression PASS; no gate changes |
| New package integrity/health | NOT_TESTED | New package not generated |

## Official links

- Existing canonical HTTPS YouTube/Bilibili validation and bridge/copy recovery tests pass.
- Actual Chrome launch/final navigation and real clipboard result in this sprint: **NOT_TESTED**. Prior observation of Chrome launch does not verify its final address.
- No repeated desktop attempts were made after the prior failure to reliably identify Chrome. The current Computer Use inventory contained no running PTTI candidate or Chrome window to inspect, and RAM prohibited a new candidate startup.
- Once a new candidate is safely built and native playback has been completed, the sole external-link human handoff is: click one reviewed official source, compare Chrome's final address **and video ID** with its original canonical source URL, then use “复制官方链接” and compare the pasted value in Chrome's address bar. A login/CAPTCHA/security barrier requires handoff, never bypass. Until this is observed, final destination and real clipboard acceptance stay NOT_TESTED.
- This final human handoff is **not ready yet**: candidate construction and native diagnostic evidence must first be completed by the agent when RAM allows.

## Package, rollback and release gate

- **No new candidate, build ID or new EXE SHA256 exists for this changed source.** Do not reuse the old candidate identity.
- Old candidate retained and EXE SHA256 freshly checked: `50f66a8b1919220b9458b340d05c4196653e7f8f1c11466108d8aa773e077a71`, under `C:\PTTI-Cinema-Builds\video-first-r4-3e0281242a-20261012T025834Z\dist\PTTI-Video-First-R4-Preview`.
- Active R4 remains `5cc753886b112305736fcc14ea77b37662726c9f`; manifest hashes of all **204 files** checked, zero mismatches.
- Rollback remains `f8a07e66666cf7129188ac15ee3389eaf8a782a0`; manifest hashes of all **200 files** checked, zero mismatches. This is integrity verification, not an actual rollback activation drill.
- Launcher hash before/after read-only verification: `fa426aa15acca4e4308475a437d8f20a5cfcfa55b473296a6f841ff75683b969`; no Launcher, shortcut or pointer mutation.
- Unique existing Cinema entry preserved; no desktop shortcut added. User DB and videos left in place; no production/official TEST/GAME_5 or frozen algorithm changes.
- CODE_COMMITTED: YES. TESTS_PASSED: targeted scope above. WINDOWS_BUILD_VERIFIED: NOT_TESTED for changed code. DESKTOP_UPDATED: NO. NATIVE_GUI_VERIFIED: NOT_TESTED for changed code.
- **Release Gate: NOT MET. DESKTOP_UPDATE_PENDING.** No merge to main, release publication, push or activation.

## Integration and next action

Recheck visual worktree status before cherry-picking. Keep `VisionPlayer.tsx` loading/error semantics and gates when reconciling later styling. `frontend/package.json`, `vite.config.ts` and `scripts/dev_sync.py` are shared infrastructure; merge scripts/config deliberately. No CSS, homepage, thumbnail or global visual files were changed here. Keep the new test scripts and source evidence together; the Vision regression uses the archived real QA row.

When actual RAM meets the unchanged start/floor guards, finish native request tracing against a **new isolated candidate** and the preserved source snapshot, recording GET URL/status/Origin, process/port/DB/build identity. Build from the committed current branch with its own output root; compare every packaged asset hash with its release manifest. Then complete the native table and final Chrome human handoff. Preserve DESKTOP_UPDATE_PENDING until every required check has evidence. Do not guess the native root cause or convert these NOT_TESTED rows into PASS.
