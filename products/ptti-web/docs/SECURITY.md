# Local MVP security notes

- Vite serves only on `127.0.0.1:4173`; strict port mode prevents silent port changes.
- The app is static and has no API proxy, backend, credentials, cookies, database, user upload, telemetry or analytics integration.
- External routes are static source records. Links open in a new tab with `noopener noreferrer`.
- No video is embedded. There is no DRM, sign-in, subscription or territory bypass.
- User feedback is stored in local browser storage and exported only after a user action. The form asks for no contact details and limits free text to 500 characters.
- React renders user-entered text as text, not HTML.
- A Cloudflare Pages `_headers` policy is prepared at `public/_headers` and is copied into the production build. It has not been tested on a Pages response because no deployment exists. Review the preview-specific `noindex` and all header rules before any formal public release.
- The Cloudflare static-preview plan is in `docs/CLOUDFLARE_PREVIEW_PLAN.md`. Hosting account log configuration and retention were not inspected and remain unknown. No Cloudflare project, GitHub app permission, deployment, API token or public URL has been created.
