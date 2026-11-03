# GOAL20.3 Private Alpha release gate

Status: **BLOCKED for public-network deployment** until the owner authorizes a specific Cloudflare account, invited email list, feedback return channel and no-purchase/free-tier budget. No account was accessed. No product was uploaded.

## Local identity and content gate

Run from `products/ptti-web` after committing a clean worktree:

```powershell
node scripts/check-private-alpha-routes.mjs
node scripts/check-runtime-health.mjs
node scripts/package-controlled-alpha.mjs
```

The packager runs TypeScript, Vite and public isolation checks, then copies only reviewed `dist/` files plus `release-identity.json` into `.alpha-qa/goal20-2/<artifact-sha>/site/`. `BUILD_RECEIPT.json` remains outside the served root. Its SHA list must exactly match the site/ files and the ZIP before any upload. Rebuild and repack after every source change; do not relabel an earlier ZIP with a newer commit.

`release-identity.json` names the clean source commit, Main catalog SHA, official match delta SHA, fixed Core and routing source hashes, and SHA of the built file list. It carries no private path or user data. The 4183 candidate health endpoint is `/__ptti/goal14/candidate-identity.json` on loopback. It reports the service configuration commit, current Git HEAD, clean/dirty state, and actual public catalog bytes separately. As a mutable Vite development server, it explicitly reports `exact_served_bundle_verified=false`. Compare its content hashes with the immutable package receipt; a healthy dev server alone cannot certify a release bundle.

The targeted real-browser runner is `qa/goal20-3/private-alpha-browser.mjs`. It requires `PTTI_PRIVATE_ALPHA_RECEIPT`, `PTTI_PLAYWRIGHT_MODULE` and `PTTI_QA_RESOURCE_GUARD_MODULE` pointing to the existing QA guard. Its own preview uses loopback port 4184 and only stops that process plus its own browser. It checks natural idle before the existing three RAM samples and immediately before launch. The guard samples every second while running and stops at 2.5 GiB. Evidence is saved under `.alpha-qa/goal20-3/<run>/`. An invalid first-run idle command failed before Chrome; after correction, one new attempt was BLOCKED at 12.969 seconds idle, also before Chrome. No current visual PASS is claimed.

The Fan URL map supports `/`, `/matches/<match_id>`, `/stars`, `/stars/<athlete_id>`, `/watch/<source_id>`, `/clips`, `/highlights`, and the existing secondary Fan sections. Watch URL query fields preserve the originating match/star context. Legacy `/?match=...` still works. Cloudflare Pages' default SPA fallback requires that no root `404.html` be uploaded. Check direct GET and refresh for Cinema, Stars, real athlete detail and Watch, including a nested route's JS/CSS/JSON requests. A returned index.html alone is insufficient: confirm the correct record renders.

## Safe hosting order

1. With explicit owner approval, create a **new** Cloudflare Pages Direct Upload project using a harmless test page. Do not connect the source repository or upload the Fan package yet. The test page itself may briefly be publicly reachable; it contains no PTTI product or private information.
2. Configure Cloudflare Access default deny and an explicit email allowlist for the production `<project>.pages.dev` hostname. Configure a separate Access application/policy for wildcard preview hostnames `*.<project>.pages.dev`; add a distinct policy for any custom domain. Verify each hostname, including old immutable preview aliases. Cloudflare's Pages preview toggle by itself covers only previews.
3. Test unauthenticated GET for the test page and direct static test asset on every hostname. Reject the release if any returns product bytes. Verify one invited login and one denied identity. Keep session duration short and public bypass rules absent.
4. Upload **only** the reviewed `site/` directory to a protected preview branch. Keep production on the harmless page. Repeat unauthenticated probes against HTML routes, JS, JSON, WebP and `release-identity.json`; then inspect the actual authenticated UI, mobile layout, links, export and error view. Confirm the browser's release identity and the receipt agree.
5. Share only the protected preview URL with invited testers. Keep feedback local until they explicitly export and send JSON through the approved channel. No automatic telemetry or uploads are in the Fan build.

Cloudflare currently documents preview URLs as public by default and says preview Access does not protect production or custom domains automatically. Its known-issues guide requires separate protection for those hostnames. Pages serves root HTML for SPA paths when there is no root `404.html`. Cloudflare Access evaluates every protected request, including assets. Source docs:

- https://developers.cloudflare.com/pages/configuration/preview-deployments/
- https://developers.cloudflare.com/pages/platform/known-issues/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/
- https://developers.cloudflare.com/pages/get-started/direct-upload/

## Acceptance and rollback

Before sharing, record anonymous and invited results for `/`, each deep link, the built JS, public JSON, a scoped WebP, and release identity. A 200 response to an anonymous request for any product byte is a release blocker. Login page redirects must target the configured Access domain; blindly following redirects hides failure. Test bilingual 390px and 1366px views, official link in a user-opened tab, back context, local save/follow/note/JSON after refresh, and an intentionally broken URL or failed image. Confirm the six approved portraits appear only on the corresponding athlete detail pages.

To withdraw: first remove allow rules and revoke Access application sessions on **all** hostnames; then disable/delete the preview deployment. Verify anonymous requests remain denied after revocation. Production rollback can select an earlier hashed production deployment if one exists; Pages preview deployments are not production rollback targets. Previously downloaded browser copies cannot be recalled. Reference: https://developers.cloudflare.com/pages/configuration/rollbacks/ and https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/session-management/ .

Estimated service cost: Cloudflare Pages/Access free tiers may cover a small invited cohort, subject to the owner's account and current quotas. No paid plan, domain or actual bill was verified; budget authorization must be explicit. Primary risks are unprotected alternate hostnames, stale preview aliases, browser-local data tied to its origin, platform logs/auth metadata, third-party YouTube availability, and six portraits' restricted editorial context.
