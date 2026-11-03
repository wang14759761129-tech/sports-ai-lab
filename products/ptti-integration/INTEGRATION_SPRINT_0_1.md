# PTTI 2.0 Integration Sprint 0.1

Status: isolated integration rehearsal; no product branches merged or cherry-picked.
Date: 2026-10-12.

## Frozen inputs and current heads

All three lines are in the same sports-ai-lab Git object database and share merge base `2c87a6433437f39bf85a9439cccf99709cce887e`. The worktrees were clean at inspection and each local HEAD matched its remote-tracking ref.

| Line | Branch | Current local and remote HEAD | Commits after base | Changed paths |
|---|---|---|---:|---:|
| Premium Design | `codex/ptti-premium-design-v1` | `51e62bf1b771e79c51726b519e6d304a50368151` | 5 | 16 |
| Web / San | `codex/ptti-web-mvp-v0-1` | `2fe0b054a0338e2a8e7e20709d9fca2edb621103` | 7 | 26 |
| Playback / 次Dex | `codex/ptti-playback-recovery-sprint-0-3` | `836d6b02084a697d92c56a6af00948601527f39e` | 5 | 20 |

These differ from the supplied Web SHA `8bae01c…`; the Web line added one documentation commit, `2fe0b05 docs(ptti-web): prepare founder pilot and preview plan`. Premium is now `51e62bf…` as supplied. Playback remains `836d6b0…` as supplied. Do not integrate using the stale Web SHA.

Pairwise changed-path overlap from the common base: Premium/Web 0, Premium/Playback 0, Web/Playback 0. This means low textual conflict risk only; it does not establish API or product-semantic compatibility.

## Integration boundary

- Desktop remains the local professional workstation for authorized files, native playback, Vision and research evidence.
- Web remains the browser-first discovery and official-source handoff experience. It must not receive local paths, private databases, research media or analysis assets.
- The products may share versioned public match/source metadata and visual guidance only after an explicit adapter and rights review. External browser playback evidence never proves desktop-native playback.

## Contract draft

The companion schema is `contracts/match-media-v0.1.schema.json`, version `ptti.match-media/0.1`.

- `Match` uses a stable `match_id`, explicit identity status, event identity, discipline, round, participants and provenance. Event-page sources remain distinct from video-page sources.
- `VideoSource` uses a stable source ID and canonical URL, publisher, publication and verification dates, resource kind, content type, match-link status, separate rights decisions, territory status and separate page/embed/external/native evidence.
- `LocalVideoAsset` is a desktop-local record bound to SHA-256 and its own timeline ID, rational time base and frame rate. Its locator is explicitly classified `LOCAL_ONLY_NEVER_EXPORT_TO_WEB`; rights for viewing, analysis, training and redistribution stay independent.
- Cross-version time conversion requires a separate human-verified `TimelineMapping`. No source may inherit another source's timestamps by matching the match ID alone.
- Null and `UNKNOWN`, `NOT_TESTED`, `BLOCKED` and `REVIEW_REQUIRED` values survive adapters. Missing evidence must never be upgraded by defaults.

Evidence fields are deliberately non-interchangeable:

- `page_access.status = OFFICIAL_PAGE_ACCESS_PASS` means only that a page opened.
- `external_video_page.status = EXTERNAL_VIDEO_PAGE_VISUAL_PASS` requires observed video imagery changing on the official page.
- `embed_playback.status = EMBED_PLAYBACK_PASS` applies only to the permitted embedded player.
- `desktop_native_playback.status = DESKTOP_NATIVE_PLAYBACK_PASS` requires a native Desktop build, source identity, build identity and recorded playback evidence.
- Vision result availability is separate from all playback states and must bind to the same source SHA and timeline ID.

Current adapters to write in a later sprint:

- Web `MatchRecord` (`products/ptti-web/src/types.ts`) records external page/video observations, territory prompts, publisher and embed permission. Its `PLAYBACK_PASS` maps only to external-page evidence when its observation data supports it; it cannot populate desktop-native or Vision evidence.
- Desktop Premium feed maps backend `videos`, `official_videos`, local asset rights and source state in `products/ptti/frontend/src/feedCatalog.ts`. Preserve its explicit thumbnail-display permission and completeness checks.
- Playback provides native Video Evidence/ScoreMoment persistence and Vision source diagnostics. Native evidence must be joined by source ID plus SHA/timeline, not title, event name or URL similarity.

## CI gate and safe work completed

The latest Playback candidate workflow is Run `38206202199` for exact head `836d6b02084a697d92c56a6af00948601527f39e`: **cancelled**. Dependency setup steps succeeded; “Full regression and isolated Windows candidate build” was cancelled, and “Upload verified candidate only” was skipped. There is no successful candidate artifact from this run. Therefore Playback runtime/API integration is held pending a completed successful Windows CI run on an exact reviewed commit.

Completed safely in this sprint:

1. Re-read the three local worktrees, branch heads, remotes, commit histories and clean/dirty states; all three are clean and match their remote heads.
2. Confirmed all five existing worktrees in the shared repository are clean. No branch, R4 activation, Launcher, user database or rollback asset was changed.
3. Created a new worktree at `C:\PTTI-Worktrees\integration-preview-sprint-0-1`, branch `codex/ptti-integration-preview-sprint-0-1`, starting exactly at the common ancestor. Existing worktrees remain untouched.
4. Added this integration record and the versioned schema draft. No runtime code from another line has been copied or merged.

## Proposed file boundaries and risks

| Stage | Candidate paths | Boundary / risk |
|---|---|---|
| Playback first | `.github/workflows/ptti-playback-candidate.yml`; `products/ptti/apps/desktop.py`; `backend/main.py`, `backend/video_evidence.py`, `backend/playback_diagnostics.py`; `frontend/src/VisionPlayer.tsx`; focused scripts/tests | Wait for CI success. Reconcile API payload, exact source SHA, timeline identity and QA origin policy before merging. Native GUI acceptance remains a separate gate. |
| Web second | `products/ptti-web/**` | Keep as a separate app. Do not import desktop player or local APIs; preserve Chinese-first behavior, official links and source evidence. Validate feedback and source checks. |
| Premium third | `products/ptti/frontend/src/VideoFeed.tsx`, `feedCatalog.ts`, feed styles/tokens and focused tests | Adapt through the agreed contract; do not copy desktop shell wholesale into Web. Maintain rights-gated thumbnails and non-verified completeness states. |

No changed file paths overlap across the lines at the inspected heads. Likely semantic integration risks are `playbackStatus` in Web being mistaken for native playback, differences between Web `MatchRecord` and desktop backend row shapes, the current desktop source/permission mapping, and local source/timeline identifiers crossing into a public response.

## Gates before a unified integration candidate

1. Freeze the exact source HEADs and confirm all worktrees are clean; use a disposable integration worktree only.
2. Playback Windows CI succeeds for the reviewed SHA. Run focused backend/API and Vision tests on the integration SHA; do not interpret CI build success as native user playback acceptance.
3. Validate schema and adapter fixtures: explicit page-access, external-video, embed, native-playback and Vision cases remain distinct; UNKNOWN/NOT_TESTED cannot become PASS.
4. Web checks: source and feedback scripts, TypeScript/build, and 1440/768/390 browser evidence.
5. Desktop checks: existing feed and ScoreMoment regressions, isolated QA DB only, no production data, native source playback and Vision QA tied to the candidate package hash.
6. Rights review: metadata listing, image display, embedding, external viewing, local analysis and training permissions remain separate. No unauthorized video or thumbnails are copied.
7. Candidate package records exact source commit and package hashes; rollback is tested. No desktop activation or public deployment in this rehearsal.

## Sprint 0.2 implementation plan

1. Wait for Playback's Windows workflow to complete successfully. If cancelled again, inspect its cancellation point and adjust workflow time/resource bounds without weakening tests or security checks.
2. In a fresh integration worktree from the agreed base, integrate the reviewed Playback commits first; validate focused API contracts and native Vision source recovery before adding other lines.
3. Add `products/ptti-web/**` as an independent app without sharing DB state. Run its source/feedback, type, build and responsive checks.
4. Add the JSON-schema-backed adapters at explicit boundaries. Map Premium feed presentation last, after status and rights fixtures pass.
5. Run combined checks on the exact integration SHA, gather browser screenshots and native Desktop evidence independently, then produce a rollback-capable candidate only if the existing resource guard permits it. Do not merge `main`, activate the Launcher or deploy publicly as part of Sprint 0.2.

Current status: **INTEGRATION_PREVIEW_PREPARED / PLAYBACK_CI_BLOCKED**. No unified candidate exists yet.
