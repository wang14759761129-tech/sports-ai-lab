# PTTI Grand Design System — candidate v0.1

Status: PROPOSED for integration; implemented in isolated prototype.

Existing equivalent found: `products/ptti-web/docs/PREMIUM_DESIGN_INTEGRATION.md`, Premium design commit `51e62bf1b771e79c51726b519e6d304a50368151`, Web `style.css`, SAN `fan-gold.css` and `FanArtwork.tsx`. Preserve history and adapt locally; do not overwrite those files from this package.

| Token | Value | Role |
|---|---|---|
| background | #090B10 | global near-black |
| surface | #11151E | quiet secondary panels |
| gold | #D4B07A | selected navigation, editorial detail |
| red | #D94F56 | primary action / sporting tension |
| blue | #4B86D8 | technical identity; not small text |
| text | #F3EFE7 | reading and titles |
| muted | #A6ABB6 | secondary information |
| line | #2A303C | surfaces, not sole interactive boundary |

Typography: system Segoe UI / Microsoft YaHei; hero 30–58px with short English statement and Chinese context; body 15px/1.65, controls 15px. Labels ≥11px except decorative editorial microtype. Keep actual warnings readable. Spacing 8/12/20/24/32/48; cards radius 12px, buttons 5px. No downloaded fonts or copyrighted athlete images. Hero SVG is an original abstract table-tennis environment.

Desktop: 88px header, generous cinematic canvas, three curated cards; 720px breakpoint stacks cards and moves navigation to a second row. Theater details occupy a separate 290px column on wide screens and stack on narrower screens. Never overlay analysis widgets on active video.

Motion: 180ms UI transitions, 4px card lift; reduced-motion disables them. No autoplay, flashing, audio effects or forced entrance delay. Demo creation is explicit and displays progress; it produces silent original video.

Accessibility: semantic headings/nav/main; skip link; 44px minimum primary controls; visible gold focus; selected state with text/border and aria-pressed; aria-live status; labelled search/file/notes; built-in video controls; images with original-scene label. Color contrast computed for core foreground/background pairs; full visual, zoom, screen-reader and keyboard acceptance remains pending browser access.

Missing states: empty collection with next action; no-search-results; unsupported media with retry/import; storage unavailable with export advice; proposed model capabilities. Local media is never labelled LICENSED simply because it was imported.
