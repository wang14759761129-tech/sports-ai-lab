# Alpha RC bridge — GOAL 04

This is a local data demo, not a deployed Web site or a replacement Windows
package. Run from the integration worktree root:

```powershell
python products/ptti-integration/scripts/run_alpha_bridge.py --output-dir products/ptti-integration/generated/alpha-rc
```

It reads a pinned, public four-match snapshot from San commit
`46f1826d80edf19147cc492e26c5461048841608`. Playback interfaces were inspected
read-only at `7523b9652e97da880132f5799d435bdb06e40d39`; this is not the SHA of
the user's tested executable. Input file hashes are recorded. A custom
`--web-records` file has no commit attribution unless its bytes match that pin.

## Web connection

- `web-internal-review.json`: v0.2 Match and VideoSource arrays, four matches,
  exact match/source IDs, resource kind, canonical URL, separate rights and
  evidence objects. Trusted local review only; UNKNOWN rights remain UNKNOWN.
- `web-strict-public.json`: same v0.2 shape, currently zero records due to
  unknown listing/external-view rights. Synthetic fixtures and local assets
  are never emitted to either Web view.
- San's current `MatchRecord[]` is not this shape. Connect through an explicit
  v0.2 consumer, join sources on `match_id`, retain `source_id`, and distinguish
  event/article routes from video routes. External visual playback does not
  imply embedding permission, a native pass, or analysis results.

## Windows connection and minimal compatible sidecar

`GET /api/video-evidence/videos` supplies `video_id`, `match_id`,
`source_sha256`, `hash_status`, availability and rights. The integration layer
can adapt selected, sanitized records; it must reject PENDING hashes and keep
paths inside the desktop process. It does not currently obtain an approved
cross-system Match/source/file association from this endpoint.

`ptti.source-version-binding/0.1` is a separately negotiated sidecar; no
unrecognized fields are inserted into the strict v0.2 schema. It names the
exact source ID, source version ID, local asset ID, verified bytes hash,
timeline ID, original time_base, observation PTS and origin PTS, plus dated
human association evidence. Missing/conflicting facts reject the edge. PTS
seconds are `(observation_pts - origin_pts) * time_base`, never inferred from
FPS. This establishes a single reviewed version/file edge, not an automatic
mapping between cuts. v0.1 consumers still explicitly reject v0.2.

`desktop-synthetic-sandbox.json` demonstrates this complete Match -> Source
-> LocalVideoAsset -> PTS edge in a separate synthetic namespace. Its result
is `SIMULATED_ONLY`; its hashes are fixture values, not measurements of a
research video. It cannot establish real or native playback evidence.

## User acceptance and remaining binding

`alpha-bridge-ledger.json` retains the user's explicit confirmation of native
Cinema play, pause, fast-forward, rewind and Seek as `USER_REPORTED_PASS`.
The exact tested app commit, EXE hash, asset ID/hash, test time and source
version edge were not supplied, so the assessment is
`UNBOUND_REVIEW_REQUIRED`. No contract playback status is upgraded. Vision
analysis and complete GUI QA remain NOT_TESTED. This does not require
repeating the already confirmed five operations; obtain their package/media
identity from Playback's existing session/manifest handoff first.

Next integration needs: San's explicit local v0.2 consumption, Playback's
sanitized selected-asset/manifest handoff and PTS/version data, and actual
reviewed real Match/source/asset associations. Unknown rights require their
own review. No services, GUI, CI, push, activation or databases are used here.
