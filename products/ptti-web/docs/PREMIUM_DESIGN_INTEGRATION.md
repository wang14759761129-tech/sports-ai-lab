# PTTI Web ↔ Premium Design V1.1 integration plan

Read-only review target: `codex/ptti-premium-design-v1` commit `ae9b84e8da5e9ebd91fceabc2eaa17c67e070ba9`. The source worktree was dirty during review, so this plan uses only files read with `git show <commit>:<path>` and does not include later uncommitted edits.

## Applicable pieces

| Premium Design V1.1 element | Evidence in the reviewed commit | Small Web adoption |
| --- | --- | --- |
| Dark design tokens | `products/ptti/frontend/src/design-tokens.css`: near-black background, layered charcoal surfaces, white/muted text, red brand accent, warning/error colors, 14px radius, 180ms motion and visible focus ring | Map the Web app's existing `--ptti-*` tokens to the approved values in a Web-owned token file. Keep tokens scoped to this app; do not import the desktop stylesheet wholesale. |
| Compact top navigation | `StudioShell.tsx` and `studio-shell.css`: sticky 56px header, active-page treatment, search field, skip link, responsive nav | Keep the Web's three Chinese-first sections, language switch and feedback entry. Adopt spacing, active state, focus and search-field behavior; omit desktop-only pages and menu structure. |
| Cinema card | `VideoFeed.tsx` and `video-feed.css`: concise metadata, consistent card hierarchy, external-source status and 16:9 `.feed-cover` | Reuse the hierarchy and aspect ratio concept. Keep the Web card's official destination type, playback status and territory copy. Do not import the desktop player, API calls, catalog or local-video features. |
| Cover and PTTI placeholder | `.feed-cover` is 16:9 and its fallback uses a PTTI wordmark/shape. The QA report says remote thumbnails render only when a recognized permission field is explicitly `ALLOWED` and the URL is HTTPS. | Use a CSS-generated PTTI placeholder for current records. Do not copy official thumbnails or event imagery; a remote cover needs explicit display permission in Web source metadata first. |
| Status and errors | `ui.tsx` `Empty` component and feed error state; warning/error tokens, visible retry and alert/status patterns | Reuse status colors and clear empty/error treatment. Keep public Web wording and sources: `PLAYBACK_PASS`, `NOT_TESTED`, event page, video page, source only. Do not inherit internal error messages or backend status semantics. |
| Mobile layout | `studio-shell.css` moves the brand/search to row one and scrolls navigation horizontally at 640px; feed cards move through multi-column breakpoints to one column at 520px | Retain the Web's existing breakpoints and Chinese copy fit. Port only small-screen spacing, touch-target and focus principles after checking 390px and 320px widths. |

## Current mismatch and minimum integration sequence

The Web app currently has teal surfaces and a lime accent (`src/style.css`), while the reviewed Premium tokens use charcoal surfaces and a red brand accent. To reduce split-brand drift, integrate the token values in the Web app first, without replacing its page structure:

1. Add a Web-local token map for background/surface, text/muted, border, brand/focus, warning/error, radius and motion.
2. Apply it only to the existing Web header, filters, cards, buttons and status/error states; preserve Chinese-first navigation, English support, search behavior and the source router.
3. Keep the current CSS-authored PTTI cover placeholder in a 16:9 frame. Add no remote image until a source record provides explicit `thumbnailDisplayPermission: ALLOWED` and an HTTPS URL.
4. Validate desktop, tablet and 390px/320px mobile widths before connecting any supplied shared token package or cover component.

## Boundary

This is an integration proposal only. It does not copy desktop components, modify the Premium Design worktree, alter playback/Vision/security code, or grant image, embedding, or commercial-use rights. A later shared token/component handoff should specify the stable CSS variable names and the cover-permission field shape before code is integrated.
