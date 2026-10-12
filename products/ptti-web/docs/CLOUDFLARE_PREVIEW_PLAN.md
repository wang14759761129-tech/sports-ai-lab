# PTTI Web static HTTPS preview — deployment plan only

**Status: READY FOR REVIEW; NOT DEPLOYED.** No Cloudflare account/project, GitHub app installation, API token, DNS record, public URL, or external participant session was created in Sprint 0.5. Publish only after the user explicitly approves the public preview and its privacy trade-offs.

Reviewed 2026-10-12 against Cloudflare's current official Pages documentation. Prices, limits and provider controls may change; recheck before any deployment.

## Proposed deployment shape

- Build the standalone app from `products/ptti-web`; upload only its generated `dist/` directory. Do not upload the repository root or any sibling application.
- Use Cloudflare Pages **Direct Upload** to a new project and a temporary `pages.dev` preview URL. Do not connect GitHub for the first trial. Direct Upload projects cannot later be converted to Git-integrated projects; if automatic builds are desired later, create a separate project and review that permission boundary then. [Direct Upload guide](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- The preview URL is public to anyone who has or discovers it. `X-Robots-Tag: noindex, nofollow` asks search crawlers not to index it; this is not authentication or an access restriction.
- Serve only the existing static Web application. No research video, user database, SQLite file, private video, desktop bundle, Vision service, credentials, telemetry, analytics SDK, feedback endpoint or server function is required.
- Keep the existing source destinations, playback labels and rights status unchanged. The page links to original publishers; it does not embed or host video.
- Feedback stays in browser `localStorage`. A participant must explicitly export the JSON and share it with the facilitator; there is no automatic upload.

## Privacy and request metadata

The public host necessarily handles network requests to return the static files. Cloudflare's logging documentation describes HTTP request log fields and related logging products, but this review did not inspect a Cloudflare account or verify which products, fields, retention periods or access settings would be enabled for this specific project. Treat account-specific log configuration and retention as **UNKNOWN** until the account owner reviews it. The site itself adds no analytics or identity collection. The proposed `Referrer-Policy: no-referrer` avoids sending the PTTI URL as a referrer when a user follows an official source link. [Cloudflare Logs reference](https://developers.cloudflare.com/logs/reference/)

Before inviting users, tell them that the URL is publicly reachable, the hosting provider processes request metadata, local feedback is not transmitted automatically, and they should not enter credentials or other personal details. Do not promise that a URL is private because it is obscure or marked `noindex`.

## Cost and limits

Cloudflare's current Pages pricing lists Free at **$0/month**. The current Free limits documentation lists 500 builds/month, up to 20,000 files per site and 25 MiB maximum per file. This proposal uses static assets only, no Pages Functions, no custom domain and no paid service. Therefore the stated hosting plan cost is $0; optional domain purchase, if ever desired, is separate and is not part of this proposal. [Pages pricing](https://www.cloudflare.com/en-ca/developer-platform/products/pages/) · [Pages limits](https://developers.cloudflare.com/pages/platform/limits/)

## GitHub and credential scope

For the first preview, do not install the Cloudflare GitHub App and do not grant repository access. Build from the approved local worktree and upload only `dist/` using Cloudflare's dashboard Direct Upload. This avoids a GitHub permission grant entirely.

If a later workflow requires the CLI, use a short-lived Cloudflare API token scoped to the intended account and Pages Write permission; never use a Global API Key, commit a token, or place it in the app's `dist/`. Cloudflare's Pages deployment API lists `Pages Write` as the accepted permission. Revoke the token after the deployment operation if it was created only for this task. [Create deployment API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/create/)

If the user later chooses Git integration instead, install the GitHub App with access to **only the `sports-ai-lab` repository**, not all repositories, and configure the app root as `products/ptti-web` with the Web-only build/output directories. Cloudflare specifically recommends limiting the GitHub app to selected repositories. [GitHub integration](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/)

## Security headers

`public/_headers` is prepared for Cloudflare Pages. Cloudflare copies a framework's `public/` contents into the build output and parses `_headers` for static responses. This app has no inline script/style, third-party assets, iframe, media element or external API call, so the policy allows same-origin app assets and fetches only, and blocks embedding/media. It also sets `nosniff`, `DENY`, `no-referrer`, a restrictive `Permissions-Policy`, HSTS without `includeSubDomains`, and `noindex`. [Cloudflare custom headers](https://developers.cloudflare.com/pages/configuration/headers/)

The local Vite server does not apply Cloudflare `_headers`; the production build can verify that the file is present, but actual response headers must be checked on a deployed Pages response after approval. A policy change that introduces remote assets, inline code, an iframe or an API must be reviewed before deploy.

## Approval-gated execution

These are proposed steps only; none has been run:

1. Recheck the clean branch and record its commit SHA. From `products/ptti-web`, run `npm ci` and `npm run build`; inspect only `dist/` for private files and verify `_headers` is present.
2. After explicit approval, sign in to Cloudflare and create a new Pages **Direct Upload** project. Choose a fresh preview name and a non-production preview branch. Do not authorize GitHub.
3. Upload only `products/ptti-web/dist/` in the Cloudflare Pages dashboard. Verify that the generated URL uses HTTPS, shows the expected commit/build, and is publicly reachable as disclosed.
4. Check response headers in the browser developer tools, then manually smoke-test Chinese/English navigation, one source link, no-route state and local-only feedback. Do not report publisher playback based on the PTTI page load.
5. Record the source commit SHA, upload date, Pages deployment ID/URL and a SHA-256 manifest of the uploaded files in the release record. Do not put credentials in that record.

Cloudflare Direct Upload supports folder uploads through the dashboard. If a CLI is later selected instead, it uses Wrangler to upload a prebuilt output directory; no token or command was run while preparing this plan. [Direct Upload guide](https://developers.cloudflare.com/pages/get-started/direct-upload/)

## Rollback and removal

- **Rollback:** in the Pages project dashboard, open Deployments, select the last known-good successful production deployment and use “Rollback to this deployment.” Cloudflare documents that preview deployments are not rollback targets, so record which deployment was production before changing anything. [Pages rollbacks](https://developers.cloudflare.com/pages/configuration/rollbacks/)
- **Pause:** if Git integration is ever added, disable production and preview branch deployments in branch controls. The proposed Direct Upload setup has no Git-triggered builds to pause.
- **Remove the preview:** after retaining any approved deployment record, delete the Pages project in Cloudflare's dashboard. Confirm the public URL no longer serves the site; do not assume search-index removal or cached-content expiry is immediate. The account owner should also revoke any one-off API token and uninstall/restrict any GitHub app if one was later granted. [Pages project API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/)
- **Version tracking:** deployment ID plus source commit SHA and file manifest hash are required for every release/rollback record. Do not rely on a mutable `pages.dev` alias alone.

## Release gate

**Not approved for publication.** The user must explicitly authorize public deployment after reviewing the public-access and request-metadata disclosure. A public URL is not needed to run the founder acceptance task on the device already serving `http://127.0.0.1:4174/`.
