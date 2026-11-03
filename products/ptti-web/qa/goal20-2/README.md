# GOAL20.2 Solo Alpha — local delivery

No deployment, account purchase, DNS change, tunnel, desktop update or release promotion is authorized or performed.

## Reproduce

From products/ptti-web:

```powershell
npm run build
node scripts/package-controlled-alpha.mjs --self-test
node scripts/check-goal20-observation.mjs
node scripts/package-controlled-alpha.mjs
```

The package is `.alpha-qa/goal20-2/<artifact SHA>/site/`. Only this `site/` directory is a possible future upload; BUILD_RECEIPT.json remains outside it. The receipt lists every file, size, SHA256 and source commit. The artifact ID is SHA256 of the sorted JSON file manifest. No Node runtime, localhost service, desktop executable or external worktree is required to serve these static files. A static HTTP host is required; opening index.html as file:// is not supported.

## Evidence and limitations

`prior-browser-observation.json` preserves the prior conversation's actual in-app-browser observation. It is not a new Chrome run, OS-browser verification or complete-viewing claim. Exact wall-clock observation time and saved screenshot files are unavailable. Main evidence and the three USER_REPORTED records are unchanged.

This run: TypeScript/build, seven-match Watch routing, navigation/return context, local saves/follows/four note kinds/import/export, media SHA/scope negatives, public isolation, Pro, 36 Review Target cases and Comparison passed. Static route and state tests are not GUI acceptance.

Fresh browser admission stopped at first sample on 2026-10-19T22:56:46.8939007+08:00: RAM 3.454 GiB, input idle 0.5 seconds. No new browser launched; no retry. All new 390/768/1366 visual, clipboard, image-error and external-playback checks remain NOT_TESTED. A separate final port check confirmed 4183 on 127.0.0.1, PID 28932, homepage HTTP200; the developer health endpoint returned404, so runtime commit identity is not established by that endpoint. Initial mixed-table output was inconclusive, not proof of no listener. No process was stopped or replaced. Prior observation: one source started playback; zero complete views; zero external participants.

## Controlled sharing proposal (not deployed)

Use Cloudflare Pages static hosting with Cloudflare Access email allowlist. Current published plans include a free tier and Access for up to 50 users; target incremental hosting cost $0 within that tier, no custom domain purchase. Reconfirm account eligibility/quotas before approval; no paid resource is provisioned.

Crucial: Pages preview URLs are PUBLIC by default. Its preview Access toggle does not protect the production pages.dev hostname or custom domains. Before uploading any product files, configure protection for every intended hostname and preview alias. Use default deny plus explicitly invited email identities. Verify unauthenticated requests to HTML, JS, JSON and WebP are blocked, and invited users work. No client-side password, hidden URL or noindex header is access control. If all paths cannot be protected before upload, do not deploy.

References checked for this task:
- https://developers.cloudflare.com/pages/configuration/preview-deployments/
- https://www.cloudflare.com/plans/
- https://blog.cloudflare.com/rollbacks-and-api-access-for-pages/

Feedback: existing Watch feedback form saves USER_REPORTED facts locally and exports JSON. Tester explicitly sends that file through a user-approved channel; no automatic upload. Favorites/notes remain per browser and origin: a new host will not automatically contain localhost data. Use explicit JSON backup/import if desired. Hosting provider sees normal request/authentication metadata; YouTube remains subject to its own login, region and availability conditions.

Rollback/revocation: first revoke Access allowlist/session access across all aliases; roll back to a previously hashed approved artifact if one exists. Otherwise disable/remove the candidate deployment. Old immutable preview aliases must remain protected/revoked too. This has NOT been tested against a live hosting account.

Minimum user decisions before any public-network action: authorize a named hosting account, invited email list, permitted feedback return channel and a $0/no-purchase budget. Public deployment remains BLOCKED pending approval and real access-control tests. Local package readiness does not mean online readiness.

## Short solo test

1. Cinema → search 王楚钦 → match → Watch. Confirm exact official URL before click; distinguish new tab, page load, playback start and complete view.
2. Return to PTTI; confirm match context. Save → My Corner → unsave. Follow → My Corner → unfollow.
3. Create a test note, refresh, edit, export JSON, import with explicit confirmation. Do not overwrite existing personal data.
4. Repeat Chinese/English at 390, 768 and 1366; visit all six photo profiles and inspect attribution. Only profile editorial use is allowed.
5. Record failed step, exact source_id/URL, locale/viewport and screenshot if safe. Never infer region/login restrictions from a timeout alone.

Remaining priorities: P1 fresh full GUI run (idle gate); P1 hosted access-control verification before sharing; P2 506.80 kB entry JS warning (gzip151.37 kB), no measured loading regression or speculative split applied.
