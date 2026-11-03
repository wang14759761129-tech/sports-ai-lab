# GOAL14 Main Content Expansion — San Handoff

Review date: 2026-10-18
Expansion review: `ptti.main-content-expansion-review/0.1`
Consumed package contract: `ptti.match-library-index/0.1` (`STRICT_PUBLIC`)

## Deliverables

Run from the repository root:

```powershell
python products/ptti-integration/scripts/build_goal14_main_content_expansion.py --generated-at 2026-10-18T10:46:06Z
python -m unittest products.ptti-integration.tests.test_goal14_main_content_expansion products.ptti-integration.tests.test_goal14_main_public_admission -v
```

The builder creates a separate additive package and a per-candidate audit:

- `products/ptti-integration/generated/goal14-main-content-expansion-v0.1/match-library-strict-public.json`
- `products/ptti-integration/generated/goal14-main-content-expansion-v0.1/candidate-review-internal.json`

The accepted v0.1 package at `generated/goal14-main-admission/match-library-strict-public.json` is unchanged. No internal-review package is a fallback for Web consumption.

## What is admitted

The expanded package contains 3 match records, 13 distinct official YouTube source records, and 3 narrowly scoped athlete records. The 13 sources comprise the prior Wang Chuqin–Felix Lebrun China Smash final, two newly cross-checked match videos, and ten event-level highlights with exact video IDs. The ten highlight links have `canonical_match_id=null` and `match_link_status=UNKNOWN`; none is attached to an athlete or match.

| Match | PTTI match ID | Official video ID | Evidence and status |
|---|---|---|---|
| WANG Chuqin vs Felix LEBRUN — China Smash 2025 MS Final | `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun` | `0QgbtsBWZhk` | Prior admitted record; WTT result and exact WTT YouTube metadata cross-check. |
| Tomokazu HARIMOTO vs Jonathan GROTH — WTT Star Contender Doha 2025 MS Final | `pro:wtt:doha-star-contender-2025:harimoto-jonathan-groth` | `jv_XQ6oKaDU` | WTT event record and exact verified World Table Tennis video metadata cross-check. Provider match ID remains null. |
| Chen Xingtong vs Wang Manyu — WTT Finals Fukuoka 2024 WS Final | `pro:wtt:wtt-finals-fukuoka-2024:chen-xingtong-wang-manyu-ws-final` | `lb4UMbE8Pfs` | WTT event result and exact verified World Table Tennis video metadata cross-check. Provider match ID and both stable athlete IDs remain null. |

The third public athlete record is Tomokazu Harimoto (`athlete:123980`), limited to factual English name, stable registry ID, and official profile link. Chinese name, association, portrait, biography, equipment, and sponsorship details are omitted or unknown in this projection.

## Twenty existing candidate audit

Ten have an exact official video ID/title and verified WTT publisher in the recorded source snapshot, so the package admits their official outbound link only:

- Yokohama 2025: `xef0VQVV-OE` (Day 1), `WF0H02Br3LE` (Day 3), `zfrkMx5DdRo` (Day 4), `fa2j70xjqoU` (Day 5), `0820Zo3UaGM` (Top 10).
- Doha 2025: `y9AYI43XtMI` (Qualifying), `YNtnXjGiAcQ` (Day 4), `JZhxfSdn3E4` (Top 10).
- Europe Smash Sweden 2025: `AgIDgIo7bSY` (Qualifying).
- Chongqing 2025: `DRWntK5EJj0` (The Highlights Show).

Ten remain `INTERNAL_ONLY_VIDEO_ID_UNRESOLVED`: Yokohama Day 2; Doha Days 2 and 3; Europe Smash Days 1–6; Singapore Smash Top 10. The official event page's related-video title is not a unique video URL, so these are not counted as sources or public video entries.

## Permission and evidence boundaries

- `public_listing=ALLOWED` is scoped to factual event/match/source metadata and attribution only.
- `external_viewing=ALLOWED` is scoped to the official YouTube share URL. YouTube documents copying a video link to share elsewhere; this is not an embed or media-use grant: https://support.google.com/youtube/answer/57741?hl=en
- Embedding stays `UNKNOWN`; thumbnails are not displayed and are marked `NOT_ALLOWED`; local analysis, download, and redistribution remain `NOT_GRANTED`.
- Every video has `external_video_visual_latest_recorded=NOT_TESTED`, `desktop_native_playback=NOT_TESTED`, `vision_analysis=NOT_TESTED`, territory `UNKNOWN`, and current-session eligibility `NOT_EVALUATED_CURRENT_SESSION`.
- `FULL MATCH` is not inferred from a final title. Both new match videos use `content_type_claim=UNKNOWN` and `completeness_status=UNVERIFIED`.
- The WTT pages are dynamic. Current open in this review yielded their consent shell, so the record relies on official WTT indexed event result/listing material plus exact verified WTT YouTube metadata. This is identity/metadata evidence, not a current rendered-page or playback pass.

Primary source URLs:

- WTT Star Contender Doha 2025, event 3083: https://www.worldtabletennis.com/eventInfo?eventId=3083
- WTT Finals Fukuoka 2024, event 2947: https://www.worldtabletennis.com/eventInfo?eventId=2947
- Doha official video: https://www.youtube.com/watch?v=jv_XQ6oKaDU
- Fukuoka official video: https://www.youtube.com/watch?v=lb4UMbE8Pfs
- Tomokazu Harimoto WTT profile: https://www.worldtabletennis.com/player/123980/Tomokazu-HARIMOTO

## San integration notes

San can pass the expanded JSON to its existing `consumeFanCatalog` implementation without a schema change. The read-only current-consumer check accepted 3 matches, 13 sources, and 3 stars. Use only the versioned `STRICT_PUBLIC` path above. The `match-library-index-v0.1.schema.json` remains the package schema; `goal14-main-content-candidate-audit-v0.1.schema.json` validates the separate internal audit artifact.

Do not map event highlight sources to a match or player. Use `official_url` only when the UI action means “open the official platform.” Do not render thumbnails, embed players, or enable local analysis from these entries. A successful consumer/schema check does not verify external playback or territory availability.
