# P1 experience integration

Baseline: f3c40f7841a4414c919576abf1f220745654c49b; verified M1A -> D2 -> D3 ancestry. Frontend between M1A and D3 unchanged.

Before: a Moment bound to a registered LOCAL video showed no official link and had no route to the existing local viewer.
After: the same registered local source ID routes through VideoFeed's existing onPlay callback; scroll context is saved. The action explicitly asks for manual positioning at the Moment timestamp, because onPlay has no timestamp contract. No precise Seek is invented. Unresolved historical video keys retain the record without a fake playback route. Official links and rights gates unchanged.

Files changed: MomentCardsPage.tsx (optional local-view callback and action), VideoFeed.tsx (wire existing local route), test-moment-card-view.mjs (local/missing identity render cases). No stylesheet, navigation hierarchy, SQLite persistence, localStorage key, Foundation, or player replacement.

Validation: npm run build (complete tsc -b and Vite) PASS; test:moment-view, test:moments, test:feed, test:goal99-story, test:favorite-persistence, test:foundation, test:foundation-playback, test:media-distribution PASS. npm run test:m1a with the handoff rally.mp4 and roundtrip-example.json: 5/5 PASS, synthetic/local logic only. The SSR tests prove rendering, not actual callback click/navigation or video playback.

GUI=NOT_TESTED
NATIVE=NOT_TESTED
REAL_PLAYBACK=NOT_TESTED
CINEMA_VISUAL=NOT_TESTED

Rollback: use unchanged D3 source or D2 desktop package; this branch is isolated and no desktop candidate was replaced. No service launch, production DB/media access, push, merge or deployment performed.
