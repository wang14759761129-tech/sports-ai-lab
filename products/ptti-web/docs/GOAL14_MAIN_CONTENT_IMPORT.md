# GOAL14 Main Public Content Import

San consumes the exact `STRICT_PUBLIC` artifact below. It does not read or package Main's internal-review JSON.

- Main branch: `codex/ptti-goal14-content-intelligence`
- Main commit: `e38a3ec3243f7d5e47381cdb5b77a78e5220e05b`
- Contract: `ptti.match-library-index/0.1`
- Schema: `products/ptti-integration/contracts/match-library-index-v0.1.schema.json`
- Schema SHA-256: `4d10c5cee7b2ac5c8bb533c71887ddf88431976ebc2d2b055b8e8b6e0ca05415`
- Source artifact: `products/ptti-integration/generated/goal14-main-admission/match-library-strict-public.json`
- Source artifact SHA-256: `1e42763dadbb491b439939ee31d3473241f5efa243a1e7a2f3cc9d3f967013b2`
- Candidate copy: `public/data/match-library-strict-public.json` (byte-identical; checked in `check:fan-catalog`)

## Admitted records

- Match: `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun`
- Video source: `video-source:youtube:0QgbtsBWZhk`
- Athletes: `athlete:121558` WANG Chuqin / 王楚钦 and `athlete:135977` Felix LEBRUN / 菲利克斯·勒布伦
- Match-source link: `HUMAN_VERIFIED` from official metadata/result cross-check; not visual playback verification.

## User-facing permission boundary

- Public listing: factual names, event/match summary, source attribution only.
- External viewing: official YouTube share URL only.
- Thumbnail display: `NOT_ALLOWED`; the web card uses PTTI-owned artwork.
- Embedding: `UNKNOWN`; no embedded player is created.
- Local analysis and redistribution: `NOT_GRANTED`.
- Content type is a source claim (`FULL_MATCH`); completeness is `UNVERIFIED`.
- Playback remains `NOT_TESTED`; historical embed error 150 is historical only. Territory and login status remain `UNKNOWN`; current-session eligibility remains `NOT_EVALUATED_CURRENT_SESSION`.

The strict artifact includes Main's own provenance manifest (including upstream file fingerprints) but no internal-review records, private media, thumbnails, or local paths. San does not use internal data to fill public pages.
