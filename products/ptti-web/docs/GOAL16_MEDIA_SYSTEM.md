# GOAL16 San media system

## Current upstream review package

The reviewed Main input is commit `0d30c3fdbd4b4ba3e36d0dfabf421eae7bc636ff`.

- Manifest: `ptti.public-media-manifest/0.1`, SHA-256 `e533ceeae42138a1bcf45099f0ea53180a29a7f21366e5f59d6ce8bebd837a49`.
- Schema: `products/ptti-integration/contracts/public-media-manifest-v0.1.schema.json`, SHA-256 `4eb14ddc583bf1f5bd15db298d6ca93d07a59e0d70f212788a713d51aabb8a6a`.
- The Main manifest is `INTERNAL_MEDIA_RIGHTS_REVIEW`, contains 9 candidate records, and its schema fixes `display_permission` to `NOT_CLEARED`. Its strict-public eligible list is empty. All nine records have no linked Goal15 match and no computed local media SHA-256.
- The byte-identical review manifest and schema are retained only in `scripts/fixtures/goal16-media/` for tests. They are not imported by application code and must never be copied to `public/` or the build output.

## Rendering boundary

`src/approved-public-media.json` is the only media index consumed by the Fan artwork layer. It is a San-side, allowlisted rendering projection (`ptti.web-public-media-index/0.1`), not a rewrite of the Main review schema. It currently contains zero assets, so all existing PTTI original poster art remains visible.

`AthletePortrait` resolves only by exact `athlete_id`; `MatchPoster` resolves only by exact `match_id`. Images must be same-origin files under `/media/goal16/`; external image URLs are rejected. Each rendition needs an exact local SHA-256, dimensions and MIME type. Public assets also require photographer, attribution, source-page URL, license and license URL. Derivative creation has its own explicit permission, notice and license fields; a CC BY-SA derivative must retain the same license and license URL in this release gate. Match photography requires an exact match ID, event identity and evidence source listed on that match in the strict-public catalog. The build verifies each file's actual bytes against the recorded SHA and MIME type.

## Future approved delivery

Do not copy a Main internal review record into the web index. When Main issues a separately reviewed delivery that actually marks media display as allowed, the image must be visually inspected, identity and crop reviewed, match-specific linkage supported by direct evidence where relevant, and permitted local renditions produced. Add only those exact local bytes and the allowlisted metadata to `approved-public-media.json`, then run `npm run check:goal16-media` and `npm run build`. The gate checks the strict-public athlete/match identities, required attribution/license fields, exact association, all rendition hashes, and scans `dist` for internal review details. A failure blocks the build.

The current GOAL16 Main package does not satisfy those delivery conditions. No real athlete photograph or match photograph is enabled by this change.
