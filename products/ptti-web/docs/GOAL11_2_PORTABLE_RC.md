# GOAL11.2 — isolated portable release candidate

## Build and runtime separation

The existing Windows desktop link and stable 4174 Web Pro installation are not replaced. The candidate lives under `<LOCAL_USER_ROOT>\PTTI\Release-Candidates\` and uses loopback port 4176. Its real relative-path entry is `Start-PTTI-RC.cmd`; PowerShell starts an independent hidden bundled Node process and returns. No terminal needs to remain open. A local convenience .lnk is inside the candidate directory only; after moving the directory use the .cmd entry because .lnk arguments are location-specific.

The RC build refuses a dirty San source tree and refuses to overwrite an existing candidate. It extracts Playback Core directly from the specified Git commit into a private build snapshot and compiles that snapshot with Vite. At runtime there is no Vite, npm, node_modules, Codex cache or development-worktree source access. Build tools are needed only to reproduce the artifact.

Node is still the runtime, explicitly bundled as runtime/node.exe with its exact version/SHA and matching official Node LICENSE. Windows PowerShell 5.1 and Windows/browser compatibility are system requirements; this is not a native EXE or a tested installer. React/ReactDOM/Scheduler licenses are also included.

From a clean committed products/ptti-web directory:

```powershell
node scripts/build-portable-rc.mjs --node-license .alpha-qa/rc-runtime/NODE-LICENSE.txt --core-commit 304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe
node scripts/check-portable-rc.mjs <candidate-directory>
$env:PTTI_PLAYWRIGHT_MODULE = '<existing playwright-core index.mjs>'
node scripts/check-portable-rc-browser.mjs <candidate-directory>
```

The license input for this machine was obtained from the official nodejs/node repository at v24.15.0/LICENSE. Build invocation variables are explicit and recorded, not global runtime requirements. The generated manifest pins San commit, clean state, package-lock SHA, Core commit/source SHA, actual build-tool and compiled dependency versions, bundled Node version/hash, data scope and every immutable resource hash. Generated convenience links and logs are not immutable resources. The PowerShell launcher streams file hashes before running the bundled executable; hashes are byte-integrity checks, not signatures or media/rights evidence.

## Content and security

Default RC catalogs are strict-public0 for matches, sources and profiles. The four internal bridge matches, 35 review sources and six local review-derived player cards are not distributed. The original 19-point Main Golden is original SIMULATED_ONLY data with no MP4 or source identity. It does not grant replay eligibility; selecting a lawful local file and confirming/saving both point boundaries is still required. The separate original 24-point analysis lab remains labelled separately.

The server only serves manifest-allowlisted built files, the original synthetic demo and identity health. Runtime executables, manifest, scripts, source files and private/index endpoints are not web-accessible. Only GET/HEAD are accepted; other methods and foreign origins are rejected. It binds only 127.0.0.1. No upload, telemetry or remote assets are added. The RC's HTTP CSP allows local blob video and denies remote media/frames; it narrowly permits inline style attributes used by the existing React UI. Public deployment _headers are unchanged. RC HTTP headers, not the static _headers text, govern the local candidate.

## Verification records

Actual generated evidence is in `.alpha-qa/goal11-2-rc/runtime-report.json` and `browser-report.json`, with exported Quick draft/notes and screenshots beside them. These files only exist after real execution; missing or BLOCKED reports are not PASS. The runtime test starts the candidate on an initially unused port, checks reuse/PID stability, safe occupied-port refusal against an owned fixture, hash mismatch refusal, strict-public0 and denied private/dev routes, and confirms that the stable desktop shortcut and 4174 identity are unchanged. It closes only its own fixture; the usable candidate service remains running.

The Chrome test keeps the existing 2.5 GiB guard and uses an existing clearly labelled synthetic test-pattern MP4. It checks compiled offline-runtime rendering, Main canonical identity, p002/p004 confirmed clips, p006 refusal, local notes and actual JSON downloads, refresh/import without restored video identity, bilingual/mobile layout and no network writes or private browser storage.

## Gates and backlog

This RC does not claim current-region official-video playback, public metadata permission, sound, real athletes, real recordings, Windows Native/Vision, reboot persistence, cross-machine/ARM compatibility, code signing or installer acceptance. Real content rights and real-user/video/device tests remain release gates. The compiled chunk-size warning, richer editorial content and nonblocking layout work remain backlog items. Next installer work can consume the manifest-based package after its actual local RC checks pass. No public release, push, CI or R4/desktop replacement is authorized here.
