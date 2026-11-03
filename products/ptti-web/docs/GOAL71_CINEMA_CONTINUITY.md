# GOAL71-S — Cinema continuity handoff

Scope: original San Fan worktree, branch `codex/ptti-goal14-fan-experience`.
Baseline: `ab484d6cf0336372c742a6a80ebc6072d14aec4e`.
Final source/asset identity: local `.alpha-qa/goal71/BUILD_RECEIPT.json` (not a public asset).

Implemented:
- Retain the existing Cinema component after its first visit, preserving its search and featured selection while another page is open. Hidden Cinema cannot take heading focus. No additional persistent storage.
- Match-detail close clears parent identity and URL; collection-origin match URLs retain `return=corner`. Reopen the exact saved match, then return to Collector’s Lounge. Focus targets the matching card or a heading/search fallback.
- Header/mobile Watch resumes the selected source. Source changes retain the originating page but never infer a match for event-level Highlights.
- Theater mode/focus/ratio/position/panel visibility are cached only in App memory, keyed by exact source_id. A reload starts fresh layout preferences; no evidence/playback state is cached or promoted.
- Keep the three native mode buttons visible. Director’s Booth settings are in a native collapsed disclosure. Irrelevant ratio/position controls are disabled. The source-panel checkbox now hides both the source section and Intelligence panel without unmounting their children.
- Missing catalog matches have a bilingual honest state, preserving saved identity and never substituting another video.
- Responsive structure covers narrow controls, 16:10 desktop spacing, reduced motion and keyboard focus semantics. Momentum River remains restricted to existing evidence-labeled reports/demos; no public match statistics were invented.

Verification:
- `npm run check:continuous-cinema`: 35 controlled-hook/root-event/route checks with isolated synthetic storage; these are NOT browser tests.
- Existing theater layouts, Fan navigation, Watch Routing, Collector, Journal/GOAL22, GOAL28, One Game/Arena/report, media rights/isolation and Pro/Review checks passed. The GOAL45 render check includes missing-match states in both languages.
- TypeScript and complete production build passed. Combined public catalog remains 8/19/8; no GOAL55 admission.
- No new dependencies. Current production sizes are in `.alpha-qa/goal71/build.log`. Runtime performance/retained-DOM memory cost is not measured.
- GUI, 1440/16:10/390 visual layout, actual focus/keyboard, external page loading and playback: NOT_TESTED. Offline HTML is not a screenshot.

Next Host QA (independent packaging only, not automatic installation):
1. Verify receipt source commit/tree and every dist SHA-256, then consume that exact frontend.
2. In an authorized isolated profile, exercise Lobby search → detail → Theater modes/Booth → save → Collector → same detail → back.
3. Repeat in Chinese/English at 1440×900 and 390px, checking hidden content/focus, source-panel disclosure, missing data, save/remove, and reduced motion.
4. External-link opening, page loading and video start must be recorded separately. Never infer embedding or playback rights.

No service/browser was started or stopped; no desktop, Main, Playback Core, database, user media/data, remote or release pointer was modified.
