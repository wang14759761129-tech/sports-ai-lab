# Current player and match architecture

## Before the professional registry

The local match-analysis model stored players as display strings (`player_a` and `player_b`) inside each match JSON payload. Those values describe the two sides of one local match; they do not identify a person across matches. Synthetic fixtures used names such as Wang Chenxiang and Kaikai, and the existing match table and analytics depend on that payload shape.

The backend is FastAPI with SQLite. The frontend is a React/Vite single-page application served by the desktop wrapper. Point-level analysis and source provenance belong to the local match payload. Video analysis is a separate experimental module; there was no shared professional athlete identity or professional event catalogue.

## Additive professional layer

The professional foundation adds relational tables for `athletes`, editable `athlete_groups` and memberships, `professional_sources`, immutable `athlete_ranking_history` snapshots, `professional_matches`, and match-source links. Existing local match JSON, CSV import, point analytics, and their API routes remain unchanged. Professional athlete identity uses stable internal IDs, with display names treated only as labels.

Seed data is versioned and applied once per manifest version. It does not overwrite an edited group or replace prior weekly ranking rows. Each profile or match response exposes provenance references. Facts not present in a verified source remain null or explicitly unverified.

Professional matches are catalogue records independent of local point-analysis matches. Their rights-aware video state separates an external reference from an authorized local media file. Only the latter can become `VIDEO_READY`; metadata-only/reference records stay `NOT_ANALYZED`.

## Database safety

Professional seed and API operations use the repository selected by the normal environment guard. Automated tests use OS temporary databases, development uses `PTTI-Dev`, and the formal production database is outside this change. No production data was read or modified for this feature.

## Current limits

Ranking history currently contains one sourced week, so it cannot show a trend. The small professional match catalogue is factual metadata only; it has no point data, rally segmentation, video, or TTI tactical analysis. Existing legacy local match records are not migrated to athlete IDs because their names are not sufficient identity evidence.
