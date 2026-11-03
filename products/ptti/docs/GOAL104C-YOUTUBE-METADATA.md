# GOAL104C — Official YouTube metadata foundation

Status: `CODE_READY_FOR_ISOLATED_FIXTURE_TESTS`; live API `NOT_TESTED`; no credential configured.

## Existing path reused

`frontend/src/youtubeThumbnailRuntime.mjs` already normalizes a `videos.list`
response into `YoutubeThumbnailRuntime/0.1` and resolves only an exact,
current runtime record. Its TypeScript declaration is
`frontend/src/youtubeThumbnailRuntime.d.mts`; its synthetic fixture and
identity/expiry tests are in `frontend/scripts/test-youtube-thumbnail-runtime.mjs`.
Catalog `thumbnail_url` is not used by that resolver. API metadata does not
grant embed, download, cache, or redistribution permission.

The missing boundary is now prepared as a server-only transport:
`apps/youtube_data_api.py`. It accepts one exact 11-character video ID, requests
only `part=snippet` from the fixed HTTPS `videos.list` endpoint, limits the
response fields and size, returns the provider response unchanged in memory,
and does not log, cache, or persist it. It will not call transport unless an
explicitly reviewed configuration has a server-side key, YouTube Data API v3
scope, and server application restriction. The secret is read only from the
server process environment variable `PTTI_YOUTUBE_DATA_API_KEY`; no `.env`,
frontend, WebView, or EXE secret is created.

The adapter is not wired to a route or invoked by Cinema yet. Its Python tests
use an in-memory fake transport marked `SIMULATED_ONLY` and make no network
request. The existing runtime contract and client-side rendering gate remain
unchanged.

## Eight catalog entries reviewed

These are the current catalog values, not newly verified API results. A legacy
thumbnail URL containing the matching video ID proves only catalog alignment;
it does not establish current publisher identity or display permission.

| video_id | catalog event / category | listed athletes | match_id in source record | legacy thumbnail | metadata state |
|---|---|---|---|---|---|
| `0QgbtsBWZhk` | China Smash 2025 · MS final | Wang Chuqin / Félix Lebrun | `pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun` | `i.ytimg.com/vi/0QgbtsBWZhk/hqdefault.jpg` | channel ID exists only in historic player-attempt evidence, not adapter trust field; display permission absent; embed blocked |
| `vYsJLPTEIaI` | WTT Singapore 2026 · WS final | Sun Yingsha / Wang Manyu | UNKNOWN | `i.ytimg.com/vi/vYsJLPTEIaI/hqdefault.jpg` | channel ID unverified; display permission absent |
| `aFs7HJ0NX18` | ITTF Finals 2020 · MS final | Ma Long / Fan Zhendong | UNKNOWN | `i.ytimg.com/vi/aFs7HJ0NX18/hqdefault.jpg` | channel ID unverified; display permission absent |
| `JTUWXpB-NVo` | ITTF Grand Finals 2019 · MS final | Ma Long / Fan Zhendong | UNKNOWN | `i.ytimg.com/vi/JTUWXpB-NVo/hqdefault.jpg` | channel ID unverified; display permission absent |
| `H77vNFk3neg` | WTT Macao 2023 · MS final | Wang Chuqin / Ma Long | UNKNOWN | `i.ytimg.com/vi/H77vNFk3neg/hqdefault.jpg` | channel ID unverified; display permission absent |
| `ekfCZiIEYi0` | WTT Ljubljana 2023 · MS final | Wang Chuqin / Fan Zhendong | UNKNOWN | `i.ytimg.com/vi/ekfCZiIEYi0/hqdefault.jpg` | channel ID unverified; display permission absent |
| `DTPNEl3-2b0` | WTT Macao 2024 · WS round of 16 | Sun Yingsha / Kim Nayeong | UNKNOWN | `i.ytimg.com/vi/DTPNEl3-2b0/hqdefault.jpg` | channel ID unverified; display permission absent |
| `iQhVLkcGCFE` | ITTF Worlds 2021 · XD semifinal | Lin Yun-Ju / Cheng I-Ching vs Wang Chuqin / Sun Yingsha | UNKNOWN | `i.ytimg.com/vi/iQhVLkcGCFE/hqdefault.jpg` | channel ID unverified; display permission absent |

The one Bilibili entry is excluded from this adapter. Seven YouTube rows do not
carry an exact `match_id`; no event-title or player-name inference is added.
None of the eight rows has the adapter's required
`provenance.verified_youtube_channel_id` trust field. The separate channel ID
inside 0Q's historic player-attempt review is retained as evidence but is not
automatically promoted into that API trust field. No row has
`thumbnail_display_permission: ALLOWED`.

## Media and data boundaries

The existing `ptti.match-cover-manifest/0.2` remains the independent PTTI
owned/licensed distributable-media manifest. It requires explicit written
distribution permission and currently contains zero approved assets. Dynamic
YouTube metadata stays separate from this manifest and cannot satisfy its
asset gate. The manifest, official source catalog, match IDs, favorites,
Moment Cards, and Pro Lab notes are not refreshed, deleted, or migrated by this
adapter.

## Live-integration prerequisites

Before any live call: select and review the actual API client; configure a key
outside source control in the server process; restrict it to YouTube Data API
v3 and the approved server application; confirm policy/client display behavior;
then make a one-ID request and compare returned `id`, channel identity,
`publishedAt`, title, and exact provider-returned thumbnail URL. A successful
response alone does not authorize display or change embed permission.
