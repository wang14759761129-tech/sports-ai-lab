# R4 restoration checkpoint — internal, not release

Original source: 5cc753886b112305736fcc14ea77b37662726c9f. Founder reference screenshot SHA-256: 6c9724e5ae3d520533c8879545ce67ac6ff83d32dde5be6041b40adf6317528a, retained outside the repository at C:/PTTI-Worktrees/ptti-r4-original-restore-evidence/founder-original-5cc.png.

The source is a confirmed ancestor of 54d75007eb7dc63e33dd8ac419afc20cf7e2615c, but VideoFeed, CSS and navigation differ. The reference screenshot is founder-supplied evidence; no new screenshot or pixel comparison was made.

This candidate preserves original VideoFeed and CSS. Original direct official thumbnail_url is disabled because display rights have not been established. The legacy embed decision additionally rejects EMBED_BLOCKED and mismatched video identity. These changes are not a complete replacement for the later media gate and this checkpoint is NOT APPROVED TO RUN OR DISTRIBUTE. Preserve all existing user data and formal launcher.

Foundation identity and playback projection modules are copied as standalone, read-only building blocks. They are not connected to the product runtime. Moment restore, Playback, Pro Lab and validated later fixes require selective integration and tests. Do not claim feature or GUI acceptance.

Any changes to VideoFeed, navigation, layout or CSS require separate review against the screenshot and original source. Windows packaging requires complete later rights/media gate integration, build verification, isolated QA database and browser profile, permitted GUI comparison, and separate HOST review; do not overwrite R4 or activate its launcher. Roll back by choosing original 5cc in a new independent checkout; do not reset any existing working tree.

## 2026-10-28 identity and selective integration

5cc is an ancestor of 54d7500, M1A 1fe1cff, D2 f3c40f7, and P1 a2a8304. Compared to 5cc, each has the same historical VideoFeed / CSS / main diff (245 additions, 29 deletions): GrandNavigation and workspace wrappers, FeedCoverFallback in place of missing-image text, secondary actions and added styling. These are source differences; no same-size visual comparison was performed. P1 differs from M1A in VideoFeed and MomentCardsPage, adding a local-video callback. Its runtime entry is not yet ported because 5cc has no corresponding MomentCards page; preserve its exact-ID and manual-seek semantics when integrating, with no wholesale replacement of VideoFeed.

M1A localPlayback, Foundation bridge, GEX evidence and import, and UserCollection projection were copied selectively as standalone modules; arena-events is a transitive evidence dependency, not an Arena UI integration. These modules are not wired into R4 runtime. The synthetic cross-module regression uses rally.mp4 and the matching JSON from the GEX06 isolated source and passed 5/5. No GUI, native runtime, media-distribution gate, or production build was performed. Existing official thumbnail and embed limitations remain as stated above.
