# PTTI Three-Line Integration Pre-Review

Date: 2026-10-12
Scope: read-only comparison of Premium Design, Web MVP, and Playback branches. No merge or cherry-pick was performed.

## Repository and branch state

All three worktrees share merge base `2c87a6433437f39bf85a9439cccf99709cce887e`.

| Line | Worktree | Branch | Current local / remote HEAD | State at review |
|---|---|---|---|---|
| Premium Design | `C:\PTTI-Worktrees\premium-design-v1` | `codex/ptti-premium-design-v1` | `ae9b84e8da5e9ebd91fceabc2eaa17c67e070ba9` | Clean before this closeout; final V1.1 review changes are now local to this worktree |
| Web MVP | `C:\PTTI-Worktrees\web-mvp-v0-1` | `codex/ptti-web-mvp-v0-1` | `8bae01c672dc77efb2a8ca80621d80638542bcc3` | Clean; local equals remote |
| Playback | `C:\PTTI-Worktrees\playback-recovery-sprint-0-3` | `codex/ptti-playback-recovery-sprint-0-3` | `836d6b02084a697d92c56a6af00948601527f39e` | Clean; local equals remote |

The Web branch has advanced beyond the previously supplied `481eb362…` to `8bae01c…`; later commits add verified direct-match routes, Sprint 0.3 checks and Sprint 0.4 browser observations for two official WTT video pages. Its latest commit updates the Web-owned match data, playback evidence fields, QA and rights notes. Playback has advanced beyond the previously supplied `d12d1a9…` to `836d6b0…`, which adds a Windows candidate CI workflow and its plan. The review used the current local and remote refs; neither branch was reset or modified.

## Histories and changed paths

Premium Design has three commits after the common base: `7145147 Polish premium Cinema visual system`, `b51dc01 Clarify official video watch states`, and `ae9b84e Gate Cinema covers on explicit display permission`. Its committed scope is the desktop feed catalog, feed card/shell styling, feed tests, and screenshots/docs. This closeout adds only the final fallback-cover refinement, its tests, report and screenshots.

Web MVP has six commits after the base: `8bd0412 feat(ptti-web): migrate isolated browser MVP`, `d3d1c50 docs(ptti-web): preserve source QA and migration provenance`, `481eb36 feat(ptti-web): add Chinese-first bilingual UX`, `84ed200 feat(ptti-web): add verified direct match routes`, `9197066 docs(ptti-web): record sprint 0.3 checks`, and `8bae01c feat(ptti-web): verify official video playback`. Changes are contained in the new `products/ptti-web/**` application, including its own React/Vite package, static `public/data/cinema.json`, types, UI, source/security/QA documentation and checks. The latest Web record shape adds explicit playback evidence (final URL, publisher, timestamps, visible frame changes and prompts); this is useful input for the shared contract but remains distinct from desktop-native playback verification.

Playback has five commits after the base: `cea065a fix(ptti): recover Vision source loading and preserve QA origins`, `c5fb8c0 docs(ptti): record privacy-safe Sprint 0.3 evidence`, `388754d feat(ptti): add opt-in native Vision playback diagnostics`, `d12d1a9 Add on-demand Windows memory audit`, and `836d6b0 Prepare isolated Windows playback candidate workflow`. Changes include `apps/desktop.py`, backend library/source and health code, `backend/playback_diagnostics.py`, `frontend/src/VisionPlayer.tsx`, Vite/package scripts, focused tests and reports, memory audit tooling, and `.github/workflows/ptti-playback-candidate.yml`.

**Path-conflict result:** there are no overlapping changed paths between any pair of branches from the common base. This is a low textual-conflict risk, not proof of compatible runtime behavior.

## What can integrate and what needs adaptation

- The Web app can be added as its own `products/ptti-web/**` application. It is intentionally independent of the desktop backend and does not import the desktop player, Vision, launcher, or UI components. Keep that boundary unless a later product decision establishes shared runtime services.
- The Premium feed work can integrate into the desktop UI as a focused presentation change. Its `feedCatalog.ts` consumes `/api/video-evidence/library`; its new fallback is self-authored SVG/CSS and hides remote thumbnails until explicit display permission is present. The same visual rules can guide Web styles, but desktop React components should not be imported into the separate Web app.
- Playback is the runtime/API line. Its Vision and backend changes should be integrated against the desktop library contract, then checked against the feed's source-state mapping. `VisionPlayer.tsx` is separate from Premium's `VideoFeed.tsx`; the styles and route shell still need a product-level compatibility check.
- The Web app's `MatchRecord` is its own model (`id`, event/category/year, discipline, round, participants/result, platform and URL, route type, playback/source states, restriction, embed permission and evidence). Desktop feed rows instead map backend `videos`, `official_videos`, `video_source` and local-asset fields. A small explicit adapter is needed if these views ever share data; direct JSON reuse would blur distinct semantics.

## Data contract to agree before cross-surface reuse

Define a versioned `Match` with stable identity, and separate `VideoSource` and `LocalVideoAsset` records. Each source should carry its own provider/source ID, canonical URL, publisher, title, event/date, discipline, round, participants, content type, rights and region restrictions, thumbnail display permission, external-view route, embed permission, actual playback test state/time/evidence, and completeness evidence. Local assets additionally need file identity (SHA-256), access/analysis rights, availability, and a source-specific timeline ID/time base.

Keep `PAGE_ACCESSIBLE`, `EXTERNAL_PLAYBACK_OBSERVED`, `EMBED_ALLOWED`, `PTTI_EMBED_PLAYBACK_VERIFIED`, and `NOT_TESTED` distinct. Keep `FULL_MATCH` as content type separate from human-verified completeness. Do not share timestamps between source versions without a verified mapping; bind ScoreMoment and analysis results to the exact asset/source and hash. `UNKNOWN` and `REVIEW_REQUIRED` must survive adapters unchanged.

## Recommended integration sequence

1. Freeze and record the current three HEADs. Create a dedicated integration worktree from the agreed shared base; do not use `main` as a shortcut.
2. Integrate Playback runtime/API changes first. Run its source recovery, diagnostics, proxy and backend tests. Treat the candidate CI workflow as build/test automation only; it does not satisfy native GUI acceptance.
3. Add `products/ptti-web/**` as a separate application and run its own dependency, source-contract, route and build checks. Avoid sharing a database implicitly.
4. Integrate Premium feed presentation after the source contract is settled. Adapt the UI at the boundary; preserve the explicit thumbnail, embed, restriction and completeness gates.
5. Run combined Python/frontend/TypeScript/Vite checks, browser screenshots at 390/768/1440, source/rights regressions and isolated-DB restart checks. Then perform the native Windows playback checklist on the exact candidate hash. Keep stable activation separate until those gates pass.

## Required gates

- Automated checks on the exact integration SHA, including API contract and source-version/timeline binding.
- Rights and provenance checks: no unauthorized thumbnails, media downloads, invented completeness, or playback-status upgrades.
- Isolated QA data only; no Production DB or restricted TEST data.
- Responsive browser evidence, keyboard focus, reduced-motion and readable state labels.
- Native Windows QA for source playback, external handoff, seek/state behavior and Cinema/Vision switching. Browser screenshots do not substitute for this.
- Candidate package identity and hash verification; no desktop activation or release until the native and rollback gates pass.

## Current limitations

This is a source/history pre-review only. No branch has been integrated, no shared data contract has been implemented, and no Windows-native release gate was run here. Current product playback and release Gates remain unchanged.
