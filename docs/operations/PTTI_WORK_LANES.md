# Read-only engineering inventory — 2026-10-20

Source of evidence: local file reads, `git log -1`, `git worktree list --porcelain`. Local source files may contain uncommitted edits: `git status` was blocked (`Permission denied` / work-tree errors). HEADs are observed registry/log values, not a claim of clean trees or deployed runtime. No Git settings were changed.

| Lane | Observed worktree | Observed HEAD | Findings |
|---|---|---|---|
| HOST WORK | C:\PTTI-Worktrees\ptti-goal23-desktop-builder | c7137574db8f7454a18e99d5d7151a8894cf6f78 | GOAL23 builder/config/tests exist; config pins Main and SAN; QA 4208; min RAM 2.5 GiB; bridge DISABLED_NO_R4_BRIDGE |
| MAIN DEX | C:\PTTI-Worktrees\integration-preview-sprint-0-1 | 753edfbd1b95bc85881bdc7632e6df14a09fdc24 | GOAL22 inspiration content; match-library contracts; review-target evidence fixtures |
| PLAYBACK DEX | C:\PTTI-Worktrees\playback-recovery-sprint-0-3 | b54e1546b7e6c1edc69406582ed68e90988a1910 | GOAL14 Watch Routing 0.1; pinned core 304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe |
| SAN DEX | C:\PTTI-Worktrees\web-goal14-fan-mvp | 4d24c130cbe9dbdd66390423605c29f26a7ee792 | React 19 / TS / Vite; FanCatalogPage, FanArtwork, FanSearchOverlay, fan navigation and local-data/2; own build gates |
| Existing Web tree | C:\PTTI-Worktrees\web-mvp-v0-1 | 0f544307cfe0b076ada2894674f5cbc20f52e579 (detached) | Cinema, Pro, Pulse, Stars routes in source; local review and source library components |
| Existing design | C:\PTTI-Worktrees\premium-design-v1 | 51e62bf1b771e79c51726b519e6d304a50368151 | Existing equivalent design baseline; Web integration document inspected |

Launcher: `<LOCAL_USER_ROOT>\AppData\Local\PTTI-Cinema\launcher.ps1` exists, 2791 bytes; observed file timestamp 2026-10-11 21:56:52 (host display). Read source shows hash-checked current/previous preview pointers and VerifyOnly option. No launch or validation execution was performed. Existence does NOT prove active version, correct pointers or successful GUI playback. Historical “missing” must not be repeated as current fact.

GOAL23 config version: 0.1.8-fan-4d24c13; host 0.1.8-goal23; Main/SAN above; runtime bridge disabled. Current candidate generation/build success is UNVERIFIED: configuration is not a receipt. No user DB was opened.

Dependency order: Main verified match/source metadata → Playback route eligibility / media binding → SAN page integration → Host version-pinned package / native QA. WORK supplies design tokens and flow specification to SAN; Founder accepts feel before integration. Original R4 native engine is separate from browser core.

Actual contract findings: eligibility (`ELIGIBLE`, `SCORE_ONLY`, `BLOCKED`) and playback evidence (`VERIFIED`, `NOT_TESTED`, `FAILED`) are separate. Page viewing permission does not imply embed/download/analysis rights. Existing fan-local-data/2 rejects unknown fields and allows athlete journal author SELF only. Preserve these protections.

Constraints: status/diff unavailable; active servers and desktop runtime not validated; no other conversations read; external GitHub freshness/auth not checked. Source records and local docs were sufficient for design; no claim of repository-wide exhaustive review. The selected text attachment returned no readable content from its read endpoint; the full Founder command pasted in chat is the authoritative task input.
