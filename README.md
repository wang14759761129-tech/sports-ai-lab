# PTTI safe source baseline

GOAL39 status: PARTIAL overall; earlier guarded Web snapshot build PASS; final expanded rerun BLOCKED by RAM guard. This is not a Desktop release, a complete backend verification or a GUI acceptance result. No remote is configured and no push is authorized.

Initial snapshot: `27e72aff9d4602459dc5461bcf46a63622b769ea`. Its original 572-file source map is retained unchanged in `provenance/files.json`. Follow-up edits and the reviewed public fixture are recorded in `provenance/goal39-changes.json` and the explicit identity manifests. Historical GOAL38 excluded/validation/blocker files describe the parent snapshot, not the current build state.

Read `docs/GOAL39-HARDENING.md` for the dependency graph, build commands, privacy boundaries, unresolved assets and rollback procedure. Use `npm test`, `npm run build:web:snapshot`, `python -B scripts/check-main-schemas.py`, and `npm run audit`. Existing original module build gates were not removed; the full legacy build still needs excluded private and media assets.

Module ownership remains SAN Web, MAIN Integration, PLAYBACK product/Core, HOST Desktop source. Original repositories, uncommitted work, old history, R4, Desktop candidates, Launcher and user data are untouched. Local machine paths and original dirty-file hashes stay only in the LOCAL_ONLY sibling directory outside this repository. Dependency binaries, generated previews and audit caches are ignored and are not upload candidates.

A future push needs separate approval for an exact new branch and commit. No original reviewed branch may be overwritten. Rollback: stop using this isolated repository and return to the original worktrees; preserve the initial and follow-up commits without resetting any original branch.
