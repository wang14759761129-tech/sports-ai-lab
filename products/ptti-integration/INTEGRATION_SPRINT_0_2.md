# PTTI 2.0 Integration Sprint 0.2

Status: adapters and all three reviewed source snapshots merged in the isolated integration worktree; no push, CI, desktop activation, or public deployment.
Date: 2026-10-12.

## Implemented

- `adapters.py` converts the current Web `MatchRecord` fixture, Desktop official-source metadata, and Desktop-local asset metadata into `ptti.match-media/0.1`.
- Conversion is allowlist-based. Local absolute paths, database paths, and private notes are omitted. Local asset locators remain opaque and the Web projection omits local assets.
- Web playback observations are accepted only as `EXTERNAL_VIDEO_PAGE_VISUAL_PASS` when the source is a video page and evidence includes changed frames, advancing time, and a same-host final URL. This never populates embed, Desktop-native, or Vision success.
- Page-access and external-playback claims without a checked date and required URL/evidence are demoted to `REVIEW_REQUIRED`; a video-page record cannot borrow an event-article URL. Non-finite timestamps and timeline transforms are rejected.
- Permission categories are independent. Conflicting declarations fail closed; analysis-only permission does not grant listing, embedding, model-training, or redistribution.
- A thumbnail URL is included only with explicit `ALLOWED` display permission. Unknown territory stays `UNKNOWN`. Timeline conversion requires `HUMAN_VERIFIED`, a distinct source pair, valid transform values, and evidence references.
- The fixture runner is `scripts/run_fixture_integration.py`; tests are in `tests/test_adapters.py`. All fixtures are synthetic or public-source metadata already committed in the Web line; the local path strings are deliberately fake leak-detection sentinels.

## Executed fixture pipeline

Input: four current Web public-source records, two synthetic Desktop source rows (one explicitly listable/external-viewable, one rights-unknown), one synthetic analysis-licensed local asset, one unverified time mapping, and mismatched playback/Vision evidence.

Output: 4 matches, 6 video sources, 1 local asset, 1 web-safe source. Two Web fixture records carry prior recorded external-page visual pass evidence; these are conversions of existing fixture observations, not new live playback checks in this sprint. The local asset and its locator are absent from the Web projection. Native playback passes: 0. Embed passes: 0. Verified Vision results: 0. No record is inferred to be a full match.

## Latest source snapshots checked before rehearsal

| Line | Supplied SHA | Current local SHA | Remote SHA | Difference / state |
|---|---|---|---|---|
| Playback | `836d6b02084a697d92c56a6af00948601527f39e` | `737a54154182a1d1340cfe8b2fb1708e660645e9` | `836d6b02084a697d92c56a6af00948601527f39e` | One local-only commit, `fix(ptti): bound noninteractive CI health checks`; 8 paths, +526/-48. Source worktree clean. Not pushed and no new CI result was requested or recorded. |
| Web | `2fe0b054a0338e2a8e7e20709d9fca2edb621103` | `843d54928bd6820b14fae572800e2dee6e6ae634` | `843d54928bd6820b14fae572800e2dee6e6ae634` | One additional commit, `feat(ptti-web): prioritize verified official match videos`; 11 paths, +573/-125. Source worktree clean. |
| Premium | `51e62bf1b771e79c51726b519e6d304a50368151` | `51e62bf1b771e79c51726b519e6d304a50368151` | same | No change. Source worktree clean. |

All three snapshots retain merge base `2c87a6433437f39bf85a9439cccf99709cce887e`. The committed path sets are disjoint (Playback/Web/Premium: 25/31/16 paths; pairwise overlap 0). Their exact snapshots were merged in order without textual conflicts into this isolated branch:

1. Playback `737a54154182a1d1340cfe8b2fb1708e660645e9` → merge `7d5ff0f`.
2. Web `843d54928bd6820b14fae572800e2dee6e6ae634` → merge `25b6f77`.
3. Premium `51e62bf1b771e79c51726b519e6d304a50368151` → merge `b06d77c`.

Playback's latest local-only SHA is included in the rehearsal but remains unpushed and has no new CI result in this sprint. The existing Actions Attempt 2 was not queried, started, rerun, cancelled, or edited here; follow-up belongs to Playback and the user. No unified runtime candidate or desktop activation was attempted.

## Validation

- Adapter unit tests: 33 passed.
- Fixture pipeline: PASS; 4 matches, 6 sources, 1 local asset, 1 rights-eligible public source; two fixture-carryover external visual observations, zero embed/native/Vision passes.
- JSON Schema Draft 2020-12 with format checks: PASS for the emitted contract.
- Sensitive path projection checks: PASS.
- Web source/security checks: 111 checks passed; feedback-storage and watch-filter checks passed.
- Adapter `py_compile`: PASS. Existing Playback pytest suite: NOT_RUN because this host's Python has no pytest; Web/Premium TypeScript/Vite builds: NOT_RUN because the integration worktree has no installed `node_modules` and available RAM was below the build guard.
- `git diff --check`: PASS.
- Adapter suite runtime reported by unittest: 0.007 s; combined lightweight commands completed in about 1 s.
- Resource observation at test/pre-rehearsal check: 15.80 GiB physical RAM, 1.09 GiB available; no package build or GUI launch attempted.
- GitHub Actions: untouched this sprint. No workflow was started, rerun, cancelled, or edited.

## Integration boundary and remaining gates

The source snapshots are now present in the disposable integration branch; this is a code-rehearsal result only. Playback's current local-only SHA needs its owner to push/review and request any new CI. Do not make an integration candidate or activate Desktop until that CI result and the relevant API/Vision, Web, rights, and native-playback gates are resolved.
