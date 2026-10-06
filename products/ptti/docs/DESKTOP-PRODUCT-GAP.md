# Professional Desktop Preview gap audit

Backend capabilities not adequately surfaced before this preview:

- Athlete registry/rankings existed, but detail-page video/analysis counts were fixed empty text.
- Sourced professional matches existed, but no focused match-detail/result workspace.
- Local authorized video import existed inside secondary forms; no primary inspect → match → permission → analysis journey, and generic uploads were capped at 2 GiB.
- Persistent full-match jobs existed, but no refreshed cross-match job queue.
- BallTrack CSV/JSONL, reports and bounded overlays existed, but overlays and a complete output center were inaccessible from the main product flow.
- Manual Game/Point/Rally editing existed, but was buried behind experimental pages.
- Research diagnostics existed, but shared the normal-user workflow and raw engineering details.
- Synthetic demo remained a home action; onboarding led users toward CSV/demo instead of professional matches.

Reuse the current registry, full-match service, protected database resolution, timeline editor and research APIs. Keep research media outside all builds. Preview has its own executable name and DEVELOPMENT database guard; stable PTTI.exe is unchanged.
