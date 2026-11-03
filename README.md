# PTTI GRAND EXPERIENCE / GEX-001

Status: PROTOTYPE. Founder brief dated 2026-10-20. Isolated from all existing PTTI repositories.

## Run

Open `PTTI-GEX-001.html` directly in a current desktop browser. It includes all artwork, styles and scripts; it does not request external assets. If the browser restricts file-origin localStorage, use Export to preserve records. Videos are never uploaded.

For local HTTP preview with Node.js 18+: `npm run build`, then `npm start`, then visit `http://127.0.0.1:4186`. This port belongs only to this prototype. Existing 4174/4175 apps are untouched. Stop this server with Ctrl+C.

## Try

1. Cinema → enter Private Theater → generate original 12-second clip. Keep tab visible during generation.
2. Click the native video Play control. Pause or scrub using the native media controls.
3. Add a note, choose 收藏此刻, inspect 赛事信息.
4. Open 我的收藏, return to the moment, or export JSON. Local file return requires reselecting the same file after reload.
5. Arena → choose A/B → reveal → next round. Reload to inspect persisted history.
6. Pro Lab explicitly shows proposed capabilities, not active AI results.

All three catalogue entries are curated demo experiences, not actual matches. Arena uses a visible fixed rule, not a model or live feed. The original silent animation is not sports footage. File input is not proof of ownership; the UI labels rights as not independently verified.

## Development and evidence

`npm test`: meaningful state tests, storage resilience, duplicate-click behavior, prediction settlement.

`npm run build`: dependency-free static build + standalone HTML.

Type checking: use TypeScript 5.9 with `tsc --allowJs --checkJs --noEmit --target ES2022 --module nodenext --lib ES2022,DOM src/app.mjs src/state.mjs`.

See `docs/PTTI_WORK_REPORT.md` for actual results and explicit browser QA limits. Do not interpret successful build/unit tests as native Windows playback acceptance.

## Ownership

Founder determines strategy and experience acceptance. BRAIN owns strategy coordination. WORK owns these design proposals and isolated prototype. HOST / MAIN / PLAYBACK / SAN receive candidate task packages only. No stable branch is merged or deployed here.

Files: `docs/strategy`, `docs/design`, `docs/innovation`, `docs/operations`, `docs/handoffs`, `tests`, `src`. Existing Premium Design remains historical baseline; proposed new tokens must be integrated through a reviewed adapter.
