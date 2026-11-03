# GOAL 07 · Web Match Center JSON handoff

## Shared input contract

Read-only verified from the MainDex integration worktree at commit `75b5dabe1969ef3981f4ee772179c509d07c5bd1`:

- Contract: `ptti.match-intelligence/0.1`
- Schema: `products/ptti-integration/contracts/match-intelligence-v0.1.schema.json`
- Consumer types: `products/ptti-integration/runtime/match-intelligence-v0.1.d.ts`
- Original demo fixture: `products/ptti-integration/fixtures/goal07-simulated-points.json`
- Web runtime copy: `products/ptti-web/public/data/pro-demo-match-intelligence.json`
- Verified byte-for-byte SHA-256: `bf610c7edb6a3f0a0f97e898bad6d32d0dfd319c5085fdb15a71dcb6a5ec8f5d`
- Protocol: Serve & Third-Ball Analytics v0.3, schema revision `1b30e8ea0f8a90a745fb6c30105599f0334fdf7c`

The runtime copy contains the complete 24-row fixture and keeps its exact bytes. It has no real match, athlete, video source, timeline, or source hash. The Web match catalog remains a separate `ptti.match-media/0.2` consumer: internal review has four records; strict public has zero. Pro never joins by title, player name, or timestamp.

The exact root keys are `contract_version`, `dataset`, and `points`. The dataset identity is `SIMULATED_ONLY:goal07-dataset-v1` / `SIMULATED_ONLY:goal07-match-001`; every point retains the original 21 Protocol v0.3 keys. Source binding stays `NOT_APPLICABLE_SIMULATED` with `source_id`, `source_sha256`, `timeline_id`, and `time_base` all null.

## Editing, provenance and storage

The editor changes existing points only. It does not add a row or modify match identity, score sequence, serving order, source protocol, or source binding. Statistics recalculate from the current point rows before save.

After a user saves or exports a changed bundle, Web uses MainDex's exact `SIMULATED_INTERACTIVE_EDIT` provenance form. Each edit names its parent `dataset_id`, canonical parent-bundle SHA-256 and point reference (`<percent-encoded match_id>/gNN/pNNN`), plus the field and before/after values. The derived dataset ID uses `SIMULATED_ONLY:edit-<24 hex>`; multiple edits chain through the immediately previous simulated bundle. It remains `SIMULATED_ONLY`, and all real source bindings remain null. The Web does not use the `HUMAN_ANNOTATION` provenance or fabricate a source hash.

Web retains the latest saved bundle locally; it does not keep every prior bundle. Export after each edit if the user needs a copy of each parent version in the chain. The parent hash identifies the stated input; it does not prove that an annotation is factually correct, and Web cannot independently re-open a prior bundle that was not retained.

The browser stores only the demo bundle under `ptti-web-match-intelligence-demo-v0.1` in localStorage. Export is a user-triggered JSON download with the exact shared root shape; there is no upload endpoint or server write. If storage is blocked, the current page remains editable and says changes will not survive closing it.

## UI and analysis boundary

- A real Fan match retains its existing source link, source rights and playback status. Its Pro pane says that the real match has no point annotations.
- A separate practice fixture is labeled `SIMULATED_ONLY · DEMO`, displays its contract and demo identity, and is never associated with real athletes or matches.
- Serve distributions count point rows; unknown, unclear and not applicable remain separate. Third-ball attack rate uses only explicit yes/no. Immediate outcome is limited to confirmed attacks and resolved outcomes; it is not point conversion.
- This is descriptive data UI, not evidence of match playback, a Vision result, or professional research validity.

## Acceptance commands

From `C:\PTTI-Worktrees\web-mvp-v0-1\products\ptti-web`:

```powershell
npm run check:pro
$env:PTTI_PLAYWRIGHT_MODULE = '<installed Playwright index.mjs absolute path>'
npm run check:pro-browser
npm run build
npm run check:preview
```

The focused checks verify the consumed JSON's exact IDs/21 fields, simulated edit lineage, local save/export and invalid input handling; browser checks exercise the real Fan-to-Pro path and 390/768/1440 widths in Chinese and English. They do not count as user research or playback verification.
