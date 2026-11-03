# PTTI Integration Sprint 0.3 — San Web 0.6 handoff

Status: local integration work complete; no push, deployment, CI workflow, or main merge performed.

## Worktree and lineage

- Integration worktree: `C:\PTTI-Worktrees\integration-preview-sprint-0-1`
- Branch: `codex/ptti-integration-preview-sprint-0-1`
- Integration snapshot before this sprint: `0b5e29e6019f8b9ea4ac90179541f09bbca00e34`
- Snapshot parents: shared integration base `c18e80e5d1daf79651099664556e7e2813f25ab2`; San Web handoff `1db64bf6d746106047bca785225e2718dd933828`.
- San worktree was read-only checked at `1db64bf6d746106047bca785225e2718dd933828`, clean and tracking `origin/codex/ptti-web-mvp-v0-1`.
- This work modifies files under `products/ptti-integration/` only.

The Web handoff commit is already an ancestor of the isolated integration snapshot. No cherry-pick, reset, rebase, or change to the San worktree was needed.

## Contract mapping and gaps

The adapter now emits `ptti.match-media/0.2`. The existing `match-media-v0.1.schema.json` remains unchanged. Version 0.2 adds a typed external visual-evidence payload so the exact URL, page/title/source checks, timeline observations, prompt states, and separate audio state can travel with the result. Consumers that only accept 0.1 need an explicit version negotiation/update before integration; this local work does not declare production compatibility.

| Web field | Contract field | Mapping / missing-data rule |
| --- | --- | --- |
| `id` | `match.match_id`, `video_source.source_id` | Namespaced as `web-match:<id>` and `web-source:<id>`; duplicates are rejected. |
| `event`, `eventYear`, `discipline`, `round`, `players`, `result` | `match.event`, `match.discipline`, `match.round`, `participant_names_unassigned`, `match.result` | Player names are preserved as unassigned labels; no side assignment or stable player ID is fabricated. |
| Missing `identityStatus` / stable player IDs | `match.identity_status`, `participants[].members[].player_id` | Identity stays `UNKNOWN`; participants remain empty and stable player IDs are absent. |
| Missing `eventId` | `match.event.event_id` | A numeric ID is derived only from an official WTT `/eventInfo?...eventId=` source URL. Conflicting IDs yield null. An `artId` is an article ID, never an event ID. |
| `routeType` | `video_source.resource_kind` | `event-page` → `OFFICIAL_EVENT_PAGE`; `video-page` → `VIDEO_PAGE`; `source-only` → `UNKNOWN`. An article is represented separately as `content_type=ARTICLE` only when the source label and official WTT article URL agree. |
| `platformUrl`, `videoOriginalUrl`, `sourceEvidence` | `canonical_url`, `provenance.source_urls` | Route-appropriate HTTPS URL is retained. Source-only records use a source URL, not a generated playback URL. |
| Missing `matchLinkStatus` | `video_source.match_link_status` | Remains `UNKNOWN`; `sourceStatus=official-listing-found` is not a match-link verification. |
| `lastVerifiedAt` | `video_source.verified_at` | Valid date retained; invalid dates become null. No freshness/expiry policy is defined in the supplied contract. |
| `playbackStatus`, `playbackTested`, `playbackEvidence` | `evidence.external_video_page` | May produce only `EXTERNAL_VIDEO_PAGE_VISUAL_PASS` after every visual/source gate below passes. Audio and territory remain separate fields. |
| `embedAllowed` | `rights.embedding` | Explicit true/false maps to `ALLOWED`/`DENIED`; absent remains `UNKNOWN`. This is permission metadata, never embed-playback evidence. |
| Missing rights fields | Seven `rights` permissions | `metadata_listing`, `thumbnail_display`, `external_viewing`, `embedding`, `local_analysis`, `model_training`, and `redistribution` all remain `UNKNOWN`. Source URLs are not used as permission evidence. |
| `regionRestriction`, evidence `territory` | `video_source.territory`, external evidence `territory` | Unknown remains unknown; no successful browser playback is treated as global availability. |
| No Web local asset / timeline fields | `local_video_assets`, `timeline_mappings` | Empty; no local path, database, private media, or Vision output is serialized. |

Root required fields are `contract_version`, `matches`, `video_sources`, `local_video_assets`, and `timeline_mappings`. Match/source IDs, match identity state, event object, route state, rights, territory, provenance, and all four separate evidence objects are required. External visual evidence has stable required keys in v0.2; values that were not observed are null, `UNKNOWN`, `NOT_TESTED`, or empty. Optional facts such as match date, result, publication date, thumbnail, rights basis/review date, and provenance notes stay absent/null when unavailable. Both schemas reject unknown properties.

## External visual evidence gate

An incoming Web claim of `PLAYBACK_PASS` is accepted only when all of these conditions hold:

1. The source route is explicitly `video-page`, playback is marked tested, and requested and final HTTPS URLs are byte-for-byte equal.
2. The exact target URL occurs in source evidence, alongside an official WTT `eventInfo` page carrying the same event ID.
3. The page title includes the event name and both player names; the publisher label identifies the verified WTT YouTube channel and is supported by that official event source.
4. Finite, non-boolean timeline values advance by at least 5.0 seconds; visual frames changed; the ISO verification date is calendar-valid.
5. Login, region, and verification prompts are each explicitly recorded as not seen. Missing/positive prompt states fail closed.
6. Audio observation must be an explicit boolean and territory must be a string. `false` is retained as “audio not confirmed”; the audio result remains `UNKNOWN`. Territory `UNKNOWN` stays unknown.

Same-host redirects, a different YouTube video ID, a one-second advance, a missing publisher/date/title/source, title mismatch, or a mismatched official event ID cannot pass. A date's calendar validity is checked; this project has not defined an evidence-expiration interval.

`audio_confirmation_observed=false` maps to `audio_status=UNKNOWN`; false does not mean that silence was verified. A missing or non-boolean audio observation, or a missing/non-string territory value, makes the Web visual claim `REVIEW_REQUIRED`, matching the source Web validator. The explicit territory string `UNKNOWN` remains unknown and does not mean global availability. A Web external visual pass never sets `embed_playback`, `desktop_native_playback`, or Vision to pass. Embed and native remain `NOT_TESTED` in Web output.

The adapter verifies the supplied handoff facts and gates; this sprint did not re-open YouTube or re-run the five-second browser playback observation. The two existing `PLAYBACK_PASS` fixture claims are therefore passed through as **handoff evidence accepted by the converter**, not new playback tests.

## Four public-source fixtures and usage boundary

These are sanitized contract QA fixtures copied from the Web handoff. They contain public match labels and source URLs only. All seven content/rights permissions are `UNKNOWN`, so the four Web sources are excluded from `to_web_safe_payload`. The combined runner's one projected source is a clearly synthetic Desktop fixture, not one of these four.

| Fixture | Public factual labels retained for local QA | Canonical source URL | Contract classification | Rights / display state |
| --- | --- | --- | --- | --- |
| `doha-2023-ms-final` — Fan Zhendong vs Wang Chuqin, WTT Finals Men Doha 2023 | Names, event, year, MS, final, recorded result; event ID `2866` derived from official WTT event URL | `https://www.worldtabletennis.com/eventInfo?eventId=2866&selectedTab=Overview&innerselectedTab=Completed&subEvt=MSINGLES` | `OFFICIAL_EVENT_PAGE`; external video `NOT_TESTED`; no video URL | Rights all `UNKNOWN`; local QA only; public payload excludes it. |
| `doha-2023-ms-sf-fan-lin` — Fan Zhendong vs Lin Gaoyuan, same event | Names, event, year, MS, semifinal; prior Web handoff visual observation 0:02→1:01 | `https://www.youtube.com/watch?v=qIXmFTzXcs0` | `VIDEO_PAGE`; external visual evidence accepted from handoff; embed/native `NOT_TESTED` | Rights all `UNKNOWN`; local QA only; no thumbnail/frame/video may be copied, hosted, or embedded. |
| `singapore-2021-ws-final-wang-sun` — Wang Yidi vs Sun Yingsha, WTT Cup Finals Singapore 2021 | Names, event, year, WS, final; prior Web handoff visual observation 0:02→0:20; event ID `2536` derived from WTT event URL | `https://www.youtube.com/watch?v=XHGCGiAyKkc` | `VIDEO_PAGE`; external visual evidence accepted from handoff; embed/native `NOT_TESTED` | Rights all `UNKNOWN`; local QA only; no thumbnail/frame/video may be copied, hosted, or embedded. |
| `chongqing-2025-ws-final-sun-chen` — Sun Yingsha vs Chen Xingtong, WTT Champions Chongqing 2025 | Names, event, year, WS, final, reported result | `https://www.worldtabletennis.com/description?artId=4731` | Source article only: `content_type=ARTICLE`, `resource_kind=UNKNOWN`; playback `NOT_TESTED`; no match video URL or event ID inferred from `artId` | Rights all `UNKNOWN`; local QA only; article text/images are not copied or rehosted. |

“Retained for local QA” is not a rights grant. No fixture asserts `ALLOWED`. Production metadata listing and outbound-source projection remain gated until the relevant permission decisions have a real review basis. No official cover, thumbnail, screenshot, video frame, audio, or video file is in the fixture or authorized by this integration. The public-projection filter requires both metadata listing and external viewing to be explicitly `ALLOWED`; the four Web fixtures therefore produce zero public sources and zero public matches.

## Implemented checks

Negative regression coverage includes exact video URL mismatch (including same YouTube host/different ID), under-five-second timeline, unchanged frames, invalid/missing verification date, missing/unverified publisher, mismatched title, missing target source, wrong WTT event ID, absent prompt observations, observed login/region/verification prompts, missing/non-boolean audio, missing territory, source-only article misclassification, missing match-link status, absent player IDs, event-ID conflicts, unknown rights, and no visual-to-embed/native/Vision uplift.

`match-media-v0.1.schema.json` stays unchanged as the legacy contract. v0.2 is the local candidate needed to make the stricter audit facts explicit. Remaining integration gate: downstream consumers must agree to v0.2 or define a compatible extension before this schema becomes the shared production contract.

## Validation performed

On 2026-10-12, the lightweight local checks passed: 56 adapter/contract unit tests; fixture pipeline schema validation for four Web matches, six sources, one synthetic local asset and zero Web sources in the public projection; Python compile checks; 111 Web source/security checks; watch-filter and feedback-storage checks; and staged/unstaged `git diff --check`. The one combined public-safe source in the fixture runner is the synthetic Desktop sample, not a Web record. Two Web records carry handoff external visual evidence; no native, embed, or Vision evidence passed. No browser playback was re-run, no Windows packaging or GUI QA was run, and no GitHub Actions workflow was triggered.

The test dependency is pinned in `requirements-dev.txt` as `jsonschema==4.26.0`; it was already available in the local environment and was not installed during this sprint. Reproduce with `python -m pip install -r products/ptti-integration/requirements-dev.txt`, then run `python -m unittest discover -s products/ptti-integration/tests -v` and `python products/ptti-integration/scripts/run_fixture_integration.py`.
