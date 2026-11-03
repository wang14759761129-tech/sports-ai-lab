# Playback Core source pin

The reviewed portable Core is pinned to commit `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`.
`CORE_PIN.json` binds `src/index.ts` to both its Git blob ID and SHA-256. For a
development worktree, run
`node products/ptti/playback-core/scripts/verify-core-pin.mjs --worktree <playback-git-root>`;
for an extracted fixed source, use `--source <path-to-src/index.ts>`. Before a
build, `--repo <playback-git-root>` verifies the pinned Git object. After an RC
build, add `--manifest <candidate>/manifest.json`. The checker rejects a
different requested commit, a dirty/mismatched working source, a different
snapshot hash, and a manifest that still depends on a mutable runtime source
path. It prints only relative source identity and status, not machine-specific
paths.

## San Web integration boundary

The inspected San candidate's `products/ptti-web/scripts/build-portable-rc.mjs`
defaults to the pinned commit and obtains `src/index.ts` with `git show <commit>:<path>`.
It builds from that isolated snapshot, records `playback.commit` and
`playback.source_sha256` in `manifest.json`, and sets
`runtime_source_dependency` to `false`. This already makes the portable RC
independent of later worktree edits. The builder also accepts `--core-commit`,
so call the Core pin checker before building and the Manifest check after
building; do not accept a candidate until both pass.

The regular Vite development alias can point to the adjacent mutable Playback
worktree. For an isolated preview, set `PTTI_PLAYBACK_CORE_SOURCE` to the
`src/index.ts` extracted from the SHA-pinned archive below. The `local-rc` build
mode already requires this variable and the San builder supplies its isolated
snapshot. This repository provides the lock and source artifact; San's owner
must wire the checker into any future formal builder change because this task
does not modify San files.

## Pinned source archive

The local archive contains the Core subtree from the exact pinned Git commit.
Its SHA-256 and the inner source SHA-256 are recorded alongside the archive.
Point `PTTI_PLAYBACK_CORE_SOURCE` at the extracted
`products/ptti/playback-core/src/index.ts` when a development preview must not
follow changes in the shared Playback worktree.

## Scope

This Core is the browser-local Web Pro playback module. Native R4 uses a separate
engine and is outside this source pin. A passing Core or adapter test does not
verify Native R4 behavior.
