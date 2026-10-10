# Dark Studio v0.7 — implementation and visual acceptance

This is a UI Preview. All source permissions, timeline identifiers, ScoreMoment
verification, UNKNOWN/null semantics and frozen research gates retain their existing
meaning. Visual changes do not validate AI accuracy or a real point boundary.

## Implemented source changes

- Global dark design tokens with explicit legacy light-preference compatibility.
- Shared shell: 232 px sidebar, 76 px collapsed navigation, 64 px top bar, real
  catalog search, grouped navigation, single local-video intake entry.
- Three-column 16:9 video feed; no fabricated thumbnails. Missing covers retain
  an explicit placeholder. Detailed source status is an expandable disclosure.
- Local review layout: dominant video column and a secondary library/review
  column; narrow windows stack the existing components without changing handlers.
- Dark score observations, field-level review styling, chart colors, scene,
  player-tracking and player-motion panels. No business gate was relaxed.
- Keyboard skip link, visible focus, native dialog Escape support, reduced motion,
  long-label wrapping and print-layout compatibility.

## Browser-host visual audit

All checks use a separate temporary TEST database. Screenshot evidence remains
local; research-video screenshots are not committed or redistributed.

| Page/state | Actual evidence | Status |
|---|---|---|
| Home/video feed | Actual source metadata, 16:9 covers, permission labels, no horizontal overflow | Checked |
| Source library | Real metadata cards, local intake and unavailable-video state | Checked |
| Match details | Existing metadata, missing authorized-video state, source and score-search UI | Checked |
| Athlete browsing | Existing athlete filters and match feed | Checked |
| Individual athlete profile | CSS migrated; individual profile interaction not exercised | Partial |
| Local player | Authorized TRAIN game_1 loaded at 1920x1080; no invented score index | Checked |
| Score navigation | Empty-index state and unchanged frontend boundary/observation tests | Checked; populated field review remains manual |
| Vision | Video-intake state and disabled controls; no model execution | Checked; populated model overlays not revalidated |
| Research | Module states and evidence panels; detected long-label overflow was fixed | Checked |
| Settings | Default dark setting, readable inputs and version metadata | Checked |
| Import/onboarding dialogs | Dark surface, readable form, close button and Escape | Checked |

Browser viewport checks: 1366x768, 1920x1080, 2560x1600 and 1024x768.
The measured document width did not exceed viewport width in the checked home
layouts. After the research-label fix, its 1366 px view measured 1351 px document
width and zero white input/card surfaces. The difference is the scrollbar.
These are browser-host checks, not native Windows scaling or GUI acceptance.

## Windows Preview

Use `scripts/build_dark_studio_v07_preview.py` with the existing guarded
PyInstaller environment. It retains the 2.5 GiB start recommendation and 2 GiB
hard runtime floor. The new executable is explicitly registered and uses
`PTTI-Dev/DarkStudio-v07-Preview`, distinct from the v0.6.1 Preview database.
Output is a new directory with `_internal`; no research video, model weight or
personal database is included.

## Remaining acceptance

`MANUAL_GUI_CHECK_REQUIRED`: native playback, actual Windows scaling, populated
score-observation review and saved-state restart in the Dark Studio executable.
Existing product and research gates are not upgraded by this UI work.
