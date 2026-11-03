# PTTI Web ↔ Premium Design V1.1 integration plan

Read-only Sprint 0.6 review target: `codex/ptti-premium-design-v1` commit `51e62bf1b771e79c51726b519e6d304a50368151`. The token, navigation, card, placeholder, state and responsive rules below were checked from committed files with `git show`; this Web worktree only adopts selected values and layout principles.

## Applicable pieces

| Premium Design V1.1 element | Evidence in the reviewed commit | Small Web adoption |
| --- | --- | --- |
| Dark design tokens | `products/ptti/frontend/src/design-tokens.css`: near-black background, layered charcoal surfaces, white/muted text, red brand accent, warning/error colors, 14px radius, 180ms motion and visible focus ring | Mapped selected values to the Web app's `--ptti-*` tokens. Tokens stay scoped to this app; the desktop stylesheet was not imported. |
| Compact top navigation | `StudioShell.tsx` and `studio-shell.css`: sticky 56px header, active-page treatment, search field, skip link, responsive nav | Keep the Web's three Chinese-first sections, language switch and feedback entry. Adopt spacing, active state, focus and search-field behavior; omit desktop-only pages and menu structure. |
| Cinema card | `VideoFeed.tsx` and `video-feed.css`: concise metadata, consistent card hierarchy, external-source status and 16:9 `.feed-cover` | Reuse the hierarchy and aspect ratio concept. Keep the Web card's official destination type, playback status and territory copy. Do not import the desktop player, API calls, catalog or local-video features. |
| Cover and PTTI placeholder | `.feed-cover` is 16:9 and its fallback uses a PTTI wordmark/shape. The QA report says remote thumbnails render only when a recognized permission field is explicitly `ALLOWED` and the URL is HTTPS. | Use a CSS-generated PTTI placeholder for current records. Do not copy official thumbnails or event imagery; a remote cover needs explicit display permission in Web source metadata first. |
| Status and errors | `ui.tsx` `Empty` component and feed error state; warning/error tokens, visible retry and alert/status patterns | Reuse status colors and clear empty/error treatment. Keep public Web wording and sources: `PLAYBACK_PASS`, `NOT_TESTED`, event page, video page, source only. Do not inherit internal error messages or backend status semantics. |
| Mobile layout | `studio-shell.css` moves the brand/search to row one and scrolls navigation horizontally at 640px; feed cards move through multi-column breakpoints to one column at 520px | Retain the Web's existing breakpoints and Chinese copy fit. Port only small-screen spacing, touch-target and focus principles after checking 390px and 320px widths. |

## Historical baseline and minimum integration sequence

At the time of the initial integration review, the Web app had teal surfaces and a lime accent (`src/style.css`), while the reviewed Premium tokens used charcoal surfaces and a red brand accent. The following sequence was implemented in Sprint 0.6 in the Web-owned stylesheet, without replacing its page structure:

1. Add a Web-local token map for background/surface, text/muted, border, brand/focus, warning/error, radius and motion.
2. Apply it only to the existing Web header, filters, cards, buttons and status/error states; preserve Chinese-first navigation, English support, search behavior and the source router.
3. Keep the current CSS-authored PTTI cover placeholder in a 16:9 frame. Add no remote image until a source record provides explicit `thumbnailDisplayPermission: ALLOWED` and an HTTPS URL.
4. Validate desktop, tablet and 390px/320px mobile widths before connecting any supplied shared token package or cover component.

## Sprint 0.6 Web implementation

The Web app has now applied the token mapping locally in `src/style.css`: Premium near-black/charcoal surfaces, white and muted text, WTT-red emphasis, green visual-confirmation status, amber warning, 14px match-card/hero radius, 180ms transitions, and a visible red focus ring. The Web-owned header is sticky and compact; match art stays a CSS-generated PTTI placeholder in a 16:9 frame; route and playback states remain separate badges. Chinese line height and letter spacing are tuned locally, and the 390px controls use 44px minimum input/select height. No Premium/Desktop files, official imagery, player component, API, or remote asset were copied.

The automated visual/source regression checks enforce the 16:9 placeholder, reject embedded image/video/frame elements and external image URLs, and validate the separate route/playback mapping. Actual browser layout checks at 1440px, 768px, and 390px are recorded in the Sprint 0.6 delivery report. Official external page `PLAYBACK_PASS` remains test-browser evidence only; PTTI embedding, audio output, and territory availability remain unverified.

## Cross-workspace boundary

Sprint 0.6 changed only the Web worktree. It did not copy desktop components, modify the Premium Design worktree, alter playback/Vision/security code, or grant image, embedding, or commercial-use rights. A later shared component handoff should specify stable CSS variable names and the cover-permission field shape before a shared package is introduced.

## Sprint 0.5 Web token mapping draft (historical; superseded by Sprint 0.6)

Sprint 0.5 used Premium commit `ae9b84e8da5e9ebd91fceabc2eaa17c67e070ba9` as an earlier mapping reference. The values below document that historical draft; Sprint 0.6 rechecked the specified final commit `51e62bf1b771e79c51726b519e6d304a50368151` and applied the selected values in `src/style.css`.

| Web-owned token | Current Web value | Premium V1.1 target | Integration note |
| --- | --- | --- | --- |
| `--ptti-bg` | `#0b1012` | `--bg: #0a0a0a` | Match the near-black page background. |
| `--ptti-surface` | `#11191c` | `--surface-muted: #111215` or `--card: #151619` | Choose per existing hierarchy; do not flatten raised cards. |
| `--ptti-surface-raised` | `#172124` | `--surface-elevated: #1b1d21` | Preserve the current hierarchy using charcoal. |
| `--ptti-border` | `#29383b` | `--border: #292b30` | Use across nav, filters and cards. |
| `--ptti-text` | `#f4f6f3` | `--text: #f4f4f5` | Near-white text. |
| `--ptti-muted` / `--ptti-faint` | `#a1b1ae` / `#71827f` | `--muted: #a2a4aa` | Review low-emphasis Chinese copy contrast before mapping both to one target. |
| `--ptti-accent` / `--ptti-accent-ink` | `#b8ff69` / `#10170c` | `--brand: #e53943` / `--accent-ink: #fff` | Replace lime with Premium red within this Web app only. |
| `--ptti-warning` | `#ffc878` | `--warning: #f0be64` | Keep warning distinct from playback-confirmed status. |
| status colors (to add only if needed) | currently component-specific | `--confirmed: #79d8a5`, `--error: #ff9292`, `--error-bg: #321e20` | Use for status/error semantics; retain current accurate Chinese source labels. |
| focus / motion / radius | focus uses accent; local radii 3–5px; transitions 150ms | `--focus-ring: 0 0 0 3px #e5394352`, `--duration: 180ms`, `--radius: 14px` | Apply to Web controls after checking 390px layout; do not force 14px onto every small control. |

Suggested minimal sequence: map colors/focus first in the Web-owned stylesheet; retain the Web navigation, language control, search and source router; then tune selected container radius and motion. Keep the CSS-built 16:9 PTTI placeholder. No official cover image, thumbnail or video embed is permitted by this mapping. External official-video `PLAYBACK_PASS` remains browser evidence only and is not Windows-native playback acceptance.
