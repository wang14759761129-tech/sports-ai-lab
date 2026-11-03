# GOAL11 — Cinema-first local Web product

This increment follows GOAL11_DESKTOP_HANDOFF.md. R4 and all existing desktop backups are retained.

## Product

- Cinema opens the existing local-video workbench directly. Before media selection its 16:9 empty stage explicitly says there is no match footage. Wide layout uses approximately 66/34 stage/companion columns, stacked below 900px.
- The companion panel reads the actual Main 19-point Quick/Review Targets Golden through a loopback-only internal-review endpoint. It independently checks canonical identity with the production consumer. Source files remain under scripts/fixtures, not public/ or dist/.
- Default data is read-only. Explicitly loading it uses the same validated Quick importer as local file import, without video identity or confirmed boundaries. It is refused if work already exists. No user work is silently overwritten.
- The exact A / 3–4 contact loss target contains p002/p004/p006, N=3. Default replay count is zero. The demo does not install an MP4 or assert a full match recording exists. All two-clip test playback required selecting the existing SYNTHETIC TEST PATTERN file and manually confirming/saving p002/p004. p006 remained unconfirmed and disabled.
- Cinema, Insight and Review use one persistently mounted workbench. Switching those navigation items retains the current legal local media session. Moving to Stars/Explore/Feedback cancels playback and pauses the hidden player but keeps its session in memory. Media replacement, refresh, imported-input changes and revoked-boundary invalidation retain their existing rules.
- Report import, GOAL09 quality review and the separate original 24-point analysis lab remain inside a labelled expandable section. Neither dataset is attached to real catalog matches.
- Stars derives six player-name cards from the four actual reviewed records, listing associated events and original source links. Names are catalog labels, not fabricated verified identity IDs or biographies. No playing style, equipment or social profile is invented.
- Explore lists existing event sources and owned guidance explaining the exact coarse observation categories and UNKNOWN. Equipment recommendations remain absent because no verified material is available.

## Desktop

Known Folder Desktop: `<LOCAL_USER_ROOT>\OneDrive\Desktop\PTTI Cinema.lnk`.
The shortcut invokes Windows PowerShell and the independent launcher:
`<LOCAL_USER_ROOT>\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\PTTI-Web-Pro\Start-PTTI-Web-Pro.ps1`.
The original `PTTI-Cinema\launcher.ps1` still resolves the R4 package and is not overwritten or used by the Web shortcut. Backups and Restore-PTTI-Cinema.ps1 remain as described in the prior handoff.

Shell invocation, actual browser process URL and rendered Chrome acceptance are distinct from an observed human mouse double-click. No physical double-click or real-user acceptance is claimed.

## Evidence

- Main contract `ptti.review-targets/0.1`, Quick `ptti.quick-annotation/0.2`.
- Main canonical input SHA: `ac38316ea8dd90fb82ecf9fce565e2fe9ec2e3166e90250ae535e138ca7bdad5`.
- Playback source during tests: external worktree commit `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`. This remains a machine-local source dependency, not a portable package.
- New Chrome flow PASS: 5 groups / 8905 ms, 1366x768 and 390px, six sourced player cards, canonical demo load, exact target IDs, two individually confirmed clips, p006 refusal, stable media across Cinema/Insight/Review, paused/cancelled task on Stars, English navigation, no page errors or network writes.
- Existing formal Review Targets Chrome flow PASS: 63 actions; p002/p004 session clips, p006 disabled, split manual-note export, revoked boundaries, source replacement, changed input, refresh/import without restored media identity. Synthetic file only; zero independent-media verification and zero real users.
- TypeScript/build, strict public preview audit, 36 target cases, Comparison export, 22 playback adapter assertions and Quick v0.1/v0.2 input checks PASS.
- After the successful 5-group browser run, a small explicit browse-library callback was added so a selected match deep link can return to search (instead of linking to an absent search element). Final TypeScript/build and package privacy checks pass. The newly extended browser script's sixth group did NOT execute: RAM was 2.46 GiB, below the unchanged 2.5 GiB guard. No retry or new Chrome was started. Earlier screenshots and 63-action results remain evidence of the earlier tested code; they do not prove this last callback's browser behavior.
- Actual screenshots and JSON action log: `.alpha-qa/goal11-cinema/`. Prior full-flow evidence remains in `.alpha-qa/goal10-6-review-targets-browser.json` and `.alpha-qa/goal10-7-review-comparison-browser.json`.

## Remaining gates and backlog

Review4/public0 stays unchanged. Internal Golden endpoint is not available in public mode; dist does not contain this Golden input, real review data or any media. Official embedding, regions, audio and real athlete/video acceptance are not promoted. A >500 KiB bundle warning remains nonblocking. Cross-computer dependency packaging, visual polish and equipment/social research are future work. No push, CI, public deployment, Windows Native launch or R4 executable update.

## Playback 304eb661 error-copy follow-up

Persistence follow-up: GOAL11_1_PERSISTENT_DESKTOP.md supersedes the original cache launcher location. Its later 6-group Chrome run also passes the previously blocked browse-library callback check; the earlier BLOCKED entry above remains the historical result of that earlier run.

The live 4174 transformed LocalVideoReview module resolves `@ptti/playback-core` to the actual sibling worktree index.ts; health reports `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`. Vite explicitly reads PTTI_PLAYBACK_CORE_SOURCE and applies it as the alias and minimal fs.allow directory. The detached launcher worker sets that variable from its explicit installation configuration. This is actual served-module evidence, not an environment-variable-only upgrade claim.

The existing adapter now distinguishes play-rejected, seek-failed and seek-timeout with Chinese/English copy. Existing unsupported format, read failure/interruption, not-ready and decode mappings remain. Cancelled and playlist-replaced produce an empty warning key; cancelled task outcomes do not enter the failed-task path. Official RESTRICTED remains in the independent catalog/source display; opening an external page does not promote playback evidence.

Lightweight verification: 53 adapter assertions including real bilingual dictionary evaluation PASS; TypeScript PASS; existing watch-filter/source-status checks PASS; diff check PASS. RAM was 2.37 GiB at initial preflight, below 2.5 GiB; no new Chrome or native launch was performed. The current desktop shortcut was inspected, service identity was verified, and a browser-free launcher CheckOnly probe was used. Physical desktop double-click and fresh browser acceptance of these copy changes remain NOT_TESTED. Prior actual shortcut Shell launches and rendered UI evidence are retained with their original versions.
