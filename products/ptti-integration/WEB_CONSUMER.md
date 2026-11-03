# Read-only Web consumer for `ptti.match-media/0.2`

The integration package exposes `web_consumer.consume_contract(contract, view=...)`.
It validates the exact v0.2 version, JSON Schema, stable IDs, and references,
then returns a detached v0.2 payload. It performs no database access, network
requests, media reads, or writes.

- `view="review"` is for a trusted review surface. It retains real Match and
  VideoSource IDs, rights values, and separate playback-evidence states,
  including `UNKNOWN` and `NOT_TESTED`.
- `view="public"` additionally requires both `metadata_listing` and
  `external_viewing` to be exactly `ALLOWED`.
- Both views exclude synthetic fixtures and all `LocalVideoAsset` records.
  A thumbnail URL is returned only when `thumbnail_display` is explicitly
  `ALLOWED`. Evidence types are not promoted or combined.
- v0.1, missing versions, malformed contracts, and broken references are
  rejected; no version fallback is performed.

Run the consumer against the checked-in Alpha export (JSON is printed to
stdout; no output file or source data is changed):

```powershell
python products/ptti-integration/scripts/consume_web_export.py products/ptti-integration/generated/alpha-demo/alpha-demo-ptti.match-media-0.2.json --view review
python products/ptti-integration/scripts/consume_web_export.py products/ptti-integration/generated/alpha-demo/alpha-demo-ptti.match-media-0.2.json --view public --discipline XD
```

Filters `--match-id`, `--discipline`, and `--search` narrow the returned rows;
they do not infer missing identity or permission facts.
