# Video-First v0.5 — M1 implementation checkpoint

## Product changes
Home shows available local videos as a discovery grid; unavailable media and metadata-only matches remain in the secondary source library. Clicking a local card opens the existing Video Evidence Player in a wide viewing layout. Score marking and evidence tools remain available through a secondary button. Athlete filtering uses only persisted associations, never filenames or inferred identities.

Thumbnails are single-frame, single-thread FFmpeg requests with a 15-second timeout and atomic publication. Missing tools do not block playback. Images load lazily; full videos are not preloaded by the home page.

Two official World Table Tennis references were verified using YouTube oEmbed and the official WTT channel linked by ITTF. They use the official IFrame Player API; playback is explicitly unverified until a real playing event occurs. Duration and publication date remain unknown. No video files or streams are downloaded. Metadata expires after 30 days; refresh automation and Data API expansion are not implemented in this checkpoint.

Official references: https://developers.google.com/youtube/iframe_api_reference and https://developers.google.com/youtube/terms/developer-policies . Channel provenance: https://www.ittf.com/2025/05/16/everything-you-need-to-know-ittf-world-table-tennis-championships-finals-doha-2025/ .

## Delivery scope
This is M1 only. M2 fixed score navigation and M3 actual BallTrack overlay are not delivered here. The existing score tools are preserved. Vision is not claimed for any video without aligned, source-bound results. Speed, spin, tactical conclusions are unavailable.

## Safety
The dedicated executable is PTTI-Video-First-v0.5-Preview, with a separate development database and the existing explicit TEST override. Packaging retains the 2 GiB available-RAM guard, clean-tree requirement, and separate output directory. It includes no videos, models or personal databases. No GAME_5, official TEST, Production database or frozen inference changes are part of this work.

## Acceptance
Implementation and automated tests alone do not establish native playback acceptance. Verify: home card → actual local video → slow playback → secondary evidence tools → back to viewing; official embed playing or explicit error; athlete filter does not invent videos. M1 remains PARTIAL until these actual user journeys and packaging are evidenced. M2/M3 should not be represented as completed.
