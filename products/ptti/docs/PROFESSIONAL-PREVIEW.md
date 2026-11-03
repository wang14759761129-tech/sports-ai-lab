# PTTI v0.2 Professional Preview

Local Windows development preview. It is not a v0.2 release and does not replace v0.1.2.

## Product journey

Home → Athletes / sourced matches → Import complete local video → inspect video quality → match existing record or create a record → confirm source and rights → start analysis → jobs → match results / bounded ball-track preview → human timeline review.

The primary navigation is Home, Athletes, Matches, Video Analysis, Research Center and Settings. Synthetic CSV fixtures and the previous engineering tools remain under Developer / Demo. Ranking data is labeled by snapshot week, not implied to be live.

Professional profiles display actual linked match/video/completed-full-match counts. Missing tactical evidence remains explicitly empty. BallTrack coverage is an observation availability metric, not accuracy. Rally suggestions remain subject to human confirmation.

## Build and launch

Run the existing Python test suite and `npm --prefix frontend run build`, then `.venv\Scripts\python.exe scripts\build_professional_preview.py`.

Output: `build/professional-preview/dist/PTTI-Professional-Preview-v0.2/PTTI-Professional-Preview-v0.2.exe`. Keep the entire directory, including `_internal`.

The EXE forces DEVELOPMENT and `%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db`. A QA override is accepted only under OS temp and uses TEST. Production data is inaccessible. Dataset media/annotations are not packaged. FFmpeg/ffprobe are included for local video inspection. BallTrack inference uses the separately installed local research worker/runtime; this preview is not a self-contained GPU runtime for another PC.

Build provenance and executable SHA256 are written next to the executable. No main merge, tag or GitHub Release is performed.

## Manual desktop checklist

- First launch and onboarding; returning launch does not repeat onboarding.
- Home: 16 real athlete records and six sourced matches before adding video.
- Athletes: all groups, name search, association filter, empty search results.
- Wang Chuqin, Sora Matsushima and Tomokazu Harimoto profiles; ranking week, points, source links and actual counts.
- Match detail: final score, rights/source, no-video state and Add Local Video.
- Video import: select own legal QA file, inspect attributes, invalid file error, match mapping, permission requirement.
- Jobs: progress, pause/failure explanation, resume, result links refresh.
- Results: JSON/JSONL/CSV/HTML downloads, bounded overlay playback and local output folder.
- Human timeline: Game/Point/Rally markers, boundary adjustment, save/delete confirmation.
- Research: dataset download status, model/GPU diagnostics and truthful gates.
- Settings/theme, Developer/Demo isolation, restart persistence.

Native Save As, high-DPI/multiple-monitor behavior and print/PDF need independent manual verification unless separately documented as performed. No print/PDF capability is advertised by this preview.
