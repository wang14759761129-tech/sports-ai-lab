# Local MVP security notes

- Vite serves only on `127.0.0.1:4173`; strict port mode prevents silent port changes.
- The app is static and has no API proxy, backend, credentials, cookies, database, user upload, telemetry or analytics integration.
- External routes are static source records. Links open in a new tab with `noopener noreferrer`.
- No video is embedded. There is no DRM, sign-in, subscription or territory bypass.
- User feedback is stored in local browser storage and exported only after a user action. The form asks for no contact details and limits free text to 500 characters.
- React renders user-entered text as text, not HTML.
- Before a public HTTPS deployment, add deployment-specific security headers and review the hosting provider, data retention, privacy notice and current external-link inventory. This build is not deployed.
