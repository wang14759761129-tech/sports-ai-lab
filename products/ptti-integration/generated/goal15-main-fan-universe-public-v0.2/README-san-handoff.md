# GOAL15 Strict Public Package Projection v0.2

This delivery is a recursively allowlisted public projection of the existing
GOAL15 package. The original GOAL15 v0.1 package and internal review artifact
remain unchanged and must not be included in a public build.

## Consumer file

`match-library-strict-public.json`

- Contract: `ptti.match-library-index/0.1` (unchanged; no schema migration)
- Projection release: `GOAL15_MAIN_PUBLIC_PROJECTION/0.2`
- View: `STRICT_PUBLIC`
- Payload SHA-256: `1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`
- Preserved v0.1 source-package SHA-256: `ca714727ebe43fd091b7e52a2c8e31225c6deba65fde30765e9da6f360c12ee2`
- Counts: 5 matches, 15 official video-source records, 8 athlete profiles,
  5 exact match-to-video-source edges, and 10 event-level highlight sources.
- The contract-required `source_manifest` is an empty array. It is a
  repository-input/build manifest in the producer, so local paths and file
  hashes are intentionally excluded. Public evidence remains available through
  `evidence_sources` URLs and record-level evidence IDs.
- `quality_summary` is recalculated from this projection and contains only
  consumer-facing public counts. Candidate review and internal build counts are
  excluded.

## Playback and rights semantics

The 5 exact identity edges remain `HUMAN_VERIFIED` and refer to one specific
match and one specific source ID. The 10 highlight records remain event-level:
their `canonical_match_id` is `null` and `match_link_status` is `UNKNOWN`.
Content labels are source/title claims; they do not prove duration or playback.

Official page links are external navigation only. The package keeps each
record's rights fields without widening them. Embedding remains `UNKNOWN`,
thumbnail display remains `NOT_ALLOWED`, local analysis and redistribution are
not granted, desktop native playback and Vision analysis remain `NOT_TESTED`,
and current-session eligibility remains `NOT_EVALUATED_CURRENT_SESSION`.
Athlete entries contain sourced factual identity/profile metadata only; no
portrait, equipment, interview, sponsorship or coaching claim is added.

## Validation and regeneration

The payload validates against the unchanged `match-library-index-v0.1` schema.
The generator constructs every nested object from explicit field allowlists,
checks IDs and exact edges, then fails closed on public values that contain
repository-local paths or build references.

From the repository root, regenerate with:

```powershell
python products/ptti-integration/scripts/project_goal15_main_public_package_v0_2.py --generated-at 2026-10-18T12:04:47Z
```

That pinned timestamp reproduces the recorded payload hash. Omitting it stamps
the current UTC time and therefore changes the payload hash. The public build
must consume this v0.2 projection file, not the preserved v0.1 artifact. The
internal candidate-review report must remain outside public build inputs.
