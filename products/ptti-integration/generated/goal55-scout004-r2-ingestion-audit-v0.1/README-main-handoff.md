# SCOUT-004 R2 original intake audit

This is a blocked-ingestion audit, not the SCOUT source package and not a catalog delta. The handoff page exposes candidate summaries and publisher-local paths, but no direct JSON or CSV download. Both expected hashes therefore remain **unverified** and no rows have been parsed from bytes.

The page-rendered candidate IDs and 10/4/1 grade counts agree with the previous GOAL55 review. One transcription mismatch is now recorded: C07's rendered highlight ID is `DHxcmcGrpn8`; the prior review ledger had `DHxcmcGrpn2`. This does not admit either source. The complete original row-level comparison remains blocked until the JSON and CSV are available.

Exact-ID dedup still identifies C07's full match as an existing strict-public source. S3's `vYsJLPTEIaI` already exists as an internal reference with no canonical match link. No other exact candidate ID appeared in the reviewed Main catalog/source inventories. Match names or similar titles were not used to create joins.

## Admission result

- New strict-public matches: 0.
- New strict-public sources: 0.
- No SCOUT candidate has been promoted from `READY FOR MAIN REVIEW` to Main admission.
- Playback remains `NOT_TESTED`; territory remains `UNKNOWN`; candidate media rights remain uncleared.

San's latest read-only snapshot is `ab484d6cf0336372c742a6a80ebc6072d14aec4e`; `check:fan-catalog` passes against `ptti.match-library-index/0.1`, but the physical catalog remains 5 matches / 15 sources / 8 stars (SHA-256 `1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930`). The Main 8/19/8 composed union and this SCOUT review are not consumed by San.

## Resume requirement

Place the original `scout-004-r2-candidates.json` and `scout-004-r2-candidates.csv` in the Main worktree or provide direct downloadable files. First verify the exact expected SHA-256 values. Only then compare every row, parse the neutral v0.2 structure, run exact-ID dedup and existing public-schema validators. Do not use this audit or the rendered webpage as an ingestion substitute.
