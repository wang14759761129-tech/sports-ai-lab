# GOAL 12.3-L / 12.4 Candidate Closeout

## Verified candidate identity

Candidate branch: `codex/ptti-goal12-1-candidate`; starting HEAD for this closeout: `62f048dabf4567a0f9736c7f7f663546a24b6545`.

| Link | Full commit SHA | Evidence |
|---|---|---|
| Previous verified candidate baseline | `e8dfedfbe7094217a3f0a9c57d3a5943847dd3bc` | GOAL12.2 handoff Base; exists in candidate object database |
| GOAL12.2 delivered commit | `f39359a169e597bad7a514adcfc0f060134ed322` | Direct child of the previous baseline; feature commit |
| GOAL12.3-G acceptance commit | `62f048dabf4567a0f9736c7f7f663546a24b6545` | Direct child of the actual GOAL12.2 commit |

The previously reported `f39359a169e597bad7a514adcfc0f0601bdb2fbe` is not present in this repository's object database. The actual commit chain is consistent. Whether the old SHA was mistyped or came from another object database remains `UNKNOWN`; the discrepancy is recorded in both GOAL12.2/12.3 handoff documents. No Git history was changed.

MainDex source worktree observed at `86e3b99aa4fe0cf474cb436738138b8cc03fbaf7`, clean. No Integration files were changed.

## Playback Core pin

The candidate vendors the verified Core source, `SOURCE_PIN.json`, and ZIP under `vendor/playback-core-304eb661/`; Vite no longer defaults to a neighboring Playback worktree. The archive is 18,661 bytes with SHA-256 `c3f6e3132ae10fed2e1c7e7cd67a9fc9bbdf518d5c3d3255925bcfee96564cfc`. The extracted `products/ptti/playback-core/src/index.ts` is 26,345 bytes, SHA-256 `a59df06b688d75885bfb8ed51364e73edbaedaaa2b3746b5f7fd1d1edf67caf2`, and Git blob SHA-1 `4ec9fd9f2c03b9cb8d7afb3ecb3679044567e0a9`. The candidate and Playback repository both resolve commit `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe` at that blob.

`src/playback-core-pin.mjs` verifies the pin JSON, whole ZIP hash/size, extracts the exact ZIP member, checks source SHA-256 and Git blob SHA-1, compares the vendored source, and rejects any `PTTI_PLAYBACK_CORE_SOURCE` override whose bytes differ. `vite.config.ts` uses this verifier and reports the pinned commit/hash in the local health response. The portable builder also consumes the pinned bytes without depending on a Playback worktree.

Build lifecycle checks run before and after `npm run build`. The post-build check writes `dist/ptti-build-manifest.json`, verifies its San/Core/source identities, confirms strict-public catalog counts remain zero, and scans the public output for internal-review data. The portable builder runs the same public-output check before generating its outer manifest. No auto-activation is performed.

## MainDex Cinema Source Review v0.1 adapter

Read-only input from MainDex commit `86e3b99aa4fe0cf474cb436738138b8cc03fbaf7`:

- Schema: `contracts/cinema-source-review-v0.1.schema.json`
- Real output: `generated/goal12-3/cinema-source-review-internal.json`
- Strict-public index: `generated/goal11-match-library/match-library-strict-public.json`

`src/cinema-source-review.mjs` is a strict, internal-only data adapter; no UI was added and the generated internal JSON was not copied into the app or its public assets. It preserves each source's event/evidence claims, exact source URL, link status, watch status, rights, thumbnail, and remaining evidence requirements. The consumer exposes only an external-source action; it has no `can_play` or playback-authorization field.

The actual sample contains 3 selected records from a snapshot of 35 distinct video sources and 6 registered match records. It reports 0 canonical video-to-match links, 0 external visual playback passes, and strict-public video source count 0. All three records keep canonical match association `UNKNOWN`/null, visual playback and territory/login checks `NOT_TESTED`, `EXTERNAL_ONLY_PERMISSION_UNVERIFIED`, completeness `UNVERIFIED`, thumbnail URL null, public/external/thumbnail/embed rights `UNKNOWN`, and local-analysis/redistribution `NOT_GRANTED`. The adapter does not promote a publisher title claim into a complete-match claim or canonical association.

## Local verification record

- `npm run check:playback-core-pin`: PASS; archive/source/Git blob identity matched; 7 altered-pin, source, archive, override, and manifest identity negative cases rejected.
- `npm run check:cinema-source-review`: PASS; consumed the real MainDex JSON and Schema version; 9 negative cases rejected; Main strict-public source count 0.
- `node scripts/check-cinema-experience.mjs`: PASS.
- `node scripts/check-cinema-insight-navigation.mjs`: PASS.
- `node scripts/check-review-comparison.mjs`: PASS.
- TypeScript check: PASS.
- `npm run build`: PASS (TypeScript + Vite, 54 modules); the existing >500 kB chunk warning remains. The pre-build Core check and post-build public artifact check both passed. The first manifest was marked `DIRTY_WORKING_TREE` because this handoff was not committed yet; rerun the post-build verifier after commit to refresh the manifest identity without rebuilding unchanged assets.
- `node scripts/check-match-library.mjs`: attempted, but could not complete because this candidate lacks the separate `.alpha-qa/match-library/internal-review.json` snapshot required by that pre-existing script. This does not affect the dedicated source-review test, which reads Main's actual report directly and separately checks its strict-public JSON.
- Chrome: NOT RUN. This closeout adds no UI; browser acceptance remains pending for the separate GOAL12.3-G screen/interaction checklist.

The MainDex dataset is read directly by the candidate-only test; it is not made available through a public UI or static bundle. The adapter alone is not an internal-review screen or public publication. Review4/public0 remains unchanged.

## Release status

Candidate remains isolated and not activated. Release review is still pending until the candidate build completes with a matching manifest and the previously requested candidate-only browser evidence is collected. No 4174, R4, desktop launcher, or 4177 files were touched.
