# GOAL12.7-Q: Insight candidate QA integration

QA tooling only. Application candidate82580591ada031a5943b65756811ab2e2a1633d8 is not promoted. The old e788e2f4c4ac0d6677155a2d3a43d0d22491f2a3 configuration remains the no-config default. Core is304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe for both.

## Actual execution chain
`qa/goal12-6/acceptance.mjs --run --config qa/goal12-7/insight.config.json`
→ `candidate.mjs`: selects source/config, verifies Git-source snapshot and build receipt.
→ `resource-guard.mjs`: readWindowsMemory uses asynchronous PowerShell CIM query (3s timeout), no outer monitor required.
→ guard.preflight: exactly three passing samples >=3GiB, separated by10s waits.
→ guard.launch: another >=3GiB check immediately before launch, then starts the1s runtime monitor BEFORE chromium.launch.
→ runtime checks maintain2.5GiB plus180s bound; measurement failure is BLOCKED.
→ guard.perform races browser steps against the abort promise. On observed failure, it rejects the step and closes only the browser object returned by its own launch callback. A browser whose launch resolves after the block is also closed. No process-name lookup, process-tree kill, attach/connect to user browser, or service takeover.
→ evidence.mjs writes partial-report.json on block, retaining completed statuses/download references; interaction.jsonl is appended immediately. Finally writes report.json and closes the guard-owned browser and ephemeral QA server.

The polling cadence is1s; query timeout is3s. Detection/cancellation is initiated when a bad sample or timeout is observed, not a promise of millisecond-level termination. Browser shutdown is best effort with a3s bound. A machine/Node process crash or failed disk cannot guarantee a final report; immediately appended logs may survive.

The server binds127.0.0.1 with port0 (OS-selected unused port), uses exact build-file allowlisting and hash verification, and serves only actual synthetic fixtures. No4174/4176/4177 service is contacted. Build output is QA local-rc mode, not a public package.

## Independent candidate materialization / build
The config references an exact commit, never an assumed running worktree HEAD. candidate.mjs materializes only regular tracked application files from that Git commit into `.alpha-qa/sources/<full SHA>/products/ptti-web`, preserving original bytes. Existing different bytes are refused. Neither candidate worktree is written. Every source file is checked against its Git blob; extra files outside node_modules are refused.

Prepared source snapshot:
C:\PTTI-Worktrees\web-goal12-6-qa\.alpha-qa\sources\82580591ada031a5943b65756811ab2e2a1633d8\products\ptti-web

When a later runtime run is authorized and RAM is sufficient:

```powershell
# cwd: C:\PTTI-Worktrees\web-goal12-6-qa
node qa/goal12-6/candidate.mjs --materialize --config qa/goal12-7/insight.config.json
# If this QA-owned source snapshot has no dependencies, install its existing lockfile locally.
npm ci --ignore-scripts --no-audit --no-fund --prefix .alpha-qa/sources/82580591ada031a5943b65756811ab2e2a1633d8/products/ptti-web
node qa/goal12-6/prepare.mjs .alpha-qa/goal12-7-insight-build --config qa/goal12-7/insight.config.json
node qa/goal12-6/create-test-media.mjs
$env:PTTI_PLAYWRIGHT_MODULE='<LOCAL_USER_ROOT>\AppData\Roaming\npm\node_modules\cognee-openclaw-skills\node_modules\openclaw\node_modules\playwright-core\index.mjs'
$env:PTTI_QA_SYNTHETIC_MP4='C:\PTTI-Worktrees\web-goal12-6-qa\.alpha-qa\goal12-6-media\SYNTHETIC-TEST-PATTERN-60s.mp4'
$env:PTTI_QA_MEDIA_RECEIPT='C:\PTTI-Worktrees\web-goal12-6-qa\.alpha-qa\goal12-6-media\media-receipt.json'
node qa/goal12-6/acceptance.mjs --run --config qa/goal12-7/insight.config.json
```

No build or actual Chrome run was performed during this handoff. New output defaults differ from old output. Receipt checks require exact source commit, config name, Core commit/source hash, complete build file hashes and actual Golden fixture byte hashes. Canonical input identity remains the Main-compatible normalized hash, separate from file-byte SHA. Tampering with input fixtures or mismatching old/new receipt is rejected.

## Added browser assertions (NOT_TESTED)
Step2 now requires actual formal statistics without a video,19 points and MATCHED canonical identity; the new simulated/no-match-video guidance; zero playable rows and disabled p002/p004/p006. Uses the actual local-video button to invoke Playwright's filechooser. Empty selection must preserve data/note; return-to-Cinema must update navigation; return-to-Insight must retain the note. Checks both languages and1366/390 layouts before loading video, including action button bounds/heights.

Step3 invokes the same button and selects the original synthetic file. Session binding is still LOCAL_SESSION_ONLY and not independent media identity/rights. Step6 requires the new Chinese navigation-pause message after active replay transitions. Step7 also checks empty selection with an already bound video preserves the video DOM node/blob/session eligibility and note. Step9 requires Chinese/English pause messages and retains existing viewport assertions and screenshots.

Playwright FileChooser.setFiles([]) exercises the browser empty-selection handler. It does NOT prove physical OS dialog Escape/cancel behavior; that remains NOT_TESTED. No video/statistics are generated or relabelled by the config. Real-video/real-user acceptance remains outside this run.

## Executed results
- `node qa/goal12-6/check-resource-guard.mjs`:12/12 simulated tests PASS; zero real browsers. Report `.alpha-qa/goal12-7-guard-tests/report.json`.
- `node qa/goal12-7/check-config.mjs`: PASS; old/new isolation, exact Git snapshot/Core, actual Golden canonical identity and7 receipt rejection cases. `.alpha-qa/goal12-7-config-tests/report.json`. Synthetic unit receipts are explicitly not real builds.
- Node syntax checks and safe default: PASS.
- Existing Insight component rendering/callback/cancelled-handler and TypeScript results belong to candidate825805; browser remains NOT_TESTED.
- Current source snapshot and application worktrees are not modified by the runner. QA-only harness changes are committed locally.

New-run evidence: `.alpha-qa/goal12-7-insight-runs/<UTC timestamp>/report.json`, `partial-report.json` if blocked, `interaction.jsonl`, real PNGs and `actual-browser-review.json` only when actually produced. No screenshots/downloads are fabricated by unit tests. Failed/blocked step is named; untouched later steps remain NOT_TESTED or BLOCKED; no silent fallback.

GOAL12.5-B stays BLOCKED. No release/launcher/installed service changes, no push/CI/deploy.

## GOAL12.7-Q2 interval correction

Audit found preflight originally waited1s between samples. It now waits10s between each of the three >=3GiB samples. Tests advance an injected clock and assert sample times0/10000/20000ms. Runtime polling remains1s with a3s reader timeout and2.5GiB hard threshold. Since a guard discrepancy was found in phase1, no Chrome is started in this correction round. Any host preflight-only record is not browser evidence, build verification, or permission to reuse old RAM readings for a future run.

## GOAL12.7-Q3 build sealing

`node qa/goal12-7/build-candidate.mjs` installs the existing lockfile only within the QA-owned exact source snapshot if needed, runs TypeScript noEmit, invokes the existing local-RC build, checks public0 and the fixed Core, and writes a manifest with the verified PRODUCT Git SHA. It does not take the source SHA from the surrounding QA HEAD. BUILD_RECEIPT.json contains the separate QA commit, actual artifact path, all SHA256 values, checks, command outcomes and explicit success/failure. A partial/failing build remains FAIL. The existing seven identity/file rejection cases are retained; an explicit failed-build receipt is also rejected.

The first actual attempt compiled successfully but failed the previous QA scanner: it treated a `PRIVATE_REVIEW_ONLY` validation comparison inside the existing report importer as private report content. Its FAIL receipt is preserved. The corrected scanner still rejects serialized private visibility fields, actual internal-review markers and filenames. The fix changes QA only. After low-resource tests, an explicitly recorded retry can use `--retry-after-qa-fix`; it refuses replacing a successful receipt and archives the original failed receipt before starting.

`node qa/goal12-7/verify-build.mjs` reads the real BUILD_RECEIPT.json using the SAME shared verifyBuildReceipt function, then checks its actual artifact manifest and files. It writes QA_RECEIPT_VERIFICATION.json. Read `.alpha-qa/goal12-7-insight-build/BUILD_RECEIPT.json` for the actual latest result; these instructions are not a PASS claim.

Because a QA isolation-check fix was required this round, Chrome remains NOT_TESTED and admission BLOCKED for this round under GOAL12.7-Q3 instructions. A later run must independently pass the real10-second-spaced RAM preflight again. No historical RAM sample is reused.
