# Main Match Library v0.1 — San local consumption

Producer read-only snapshot: `56f12f006ae61a7920b0bcd0baacf0b901e22995`.
Contract: `ptti.match-library-index/0.1`.
Actual Main handoff and full Draft 2020-12 Schema were read before implementation. An exact copy of the schema is retained in scripts/contracts/; no Main file was modified.

## Intake and identity

Run from products/ptti-web:
`python scripts/import-main-library.py C:\PTTI-Worktrees\integration-preview-sprint-0-1`

The importer uses the already installed Python jsonschema validator and format checker on both actual Main documents. It checks view identity and duplicates before writing. No dependency was installed. Import output:

- Internal: 35 video sources, 6 separately registered matches, 16 profile records. No join is established.
- Strict public: 0 video sources, 0 matches, 0 profiles.
- Internal bytes SHA-256: `770dd32962aa844c6d3cfc4580a05af9b793e522a0472d159c6d43979b849cd5`.
- Public bytes SHA-256: `63214998742b79becbee0ee14799693da2031d3ae48b909da9441e3bb379f775`.
- Schema SHA-256: `4d10c5cee7b2ac5c8bb533c71887ddf88431976ebc2d2b055b8e8b6e0ca05415`.

Hashes identify bytes only. They are not signatures or evidence of rights, media identity, factual accuracy or playback.

The internal raw snapshot and receipt live only in ignored `.alpha-qa/match-library/`. The source-only consumer does not contain fixture records. Vite does not mount or read the Main worktree at runtime.

## Delivery and isolation

Cinema retains the existing player, 19-point SIMULATED_ONLY data demonstration, original four-match review catalog and existing Insight/Review tools. The separate library is a collapsed opt-in section below the original match content. It is never used to fill existing match cards, player biographies, stats or replay bindings.

Only explicit expansion requests `/__ptti/match-library.json` with the local-review header. The endpoint requires internal-review mode, loopback peer, exact 127.0.0.1:4174 Host, same-origin Origin/Sec-Fetch-Site where supplied, and the explicit header. It verifies the snapshot bytes against the intake receipt before parsing. No CORS protection is disabled. Missing/wrong headers and cross-origin requests return 404. Raw private-file access remains denied.

The UI displays historical status as historical, source/publisher identity, territory, all six independent rights decisions and UNKNOWN match association. It renders no thumbnails or embeds. Source actions say “查看来源 / View source”. Opening a link does not establish current visual playback, completeness, permission, Desktop Native or Vision.

Public mode reads only public/data/match-library-strict-public.json. It never requests the internal endpoint. Empty is authoritative. Nonempty future public grants currently fail closed until their scoped grant evidence is explicitly supported by a reviewed consumer update.

Production allowlist now includes that empty strict-public JSON. The package check verifies public0 and checks that none of the 35 private source IDs appears in any production artifact. It contains no private snapshots or review receipt.

## Verification

- Full original Main schema validation and actual snapshot import PASS.
- Node: actual 35 unique sources, six unlinked matches, public0 and 15 rejection cases PASS. Negatives include wrong view/version, forged public content, bad URLs/IDs, duplicate sources, thumbnail URL, invented match/source joins, malformed rights and promoted session eligibility.
- TypeScript/build and strict-production privacy check PASS (7 static files). Existing >500 KiB bundle warning remains a nonblocking backlog item.
- Chrome PASS: exact 35 source IDs; lazy opt-in; search; zh/en; 1366x768 and 390px; source-only buttons; no images/media/frames; zero thumbnail/external requests and zero writes; wrong Origin/header and raw-private-path rejection; public JSON remains empty. Artifacts: `.alpha-qa/goal11-library/`.
- Desktop Known Folder still resolves to <LOCAL_USER_ROOT>\OneDrive\Desktop\PTTI Cinema.lnk. Startup CheckOnly PASS; actual Shell invocation issued the 4174 URL through the default browser handler. This is not an observed physical mouse double-click or real-user test. Original R4 backup/recovery remains in the prior GOAL11 handoff.

The existing live Playback dependency remains the sibling source worktree at `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`; this is not a portable release. No push, CI, public deployment, media download, R4 executable update or other worktree write.
