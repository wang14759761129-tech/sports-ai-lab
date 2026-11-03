# GOAL16 Main media handoff — v0.1

Manifest: `public-media-manifest.json`  
Contract: `ptti.public-media-manifest/0.1`  
JSON Schema: `products/ptti-integration/contracts/public-media-manifest-v0.1.schema.json`

## Integration rule

This is an **internal review inventory**, not a production-ready image feed. San may read it to understand candidate identity, source, attribution and rights gaps. Render only assets whose `display_permission` is explicitly `ALLOWED` in a separately reviewed delivery. In this version every candidate is `NOT_CLEARED`; the strict-public projection therefore has zero assets. Do not infer permission from Commons category membership, a CC copyright license, an athlete ID, or a source page being reachable.

The candidate file URLs point to Wikimedia Commons' `Special:FilePath` endpoint. The manifest records page-reported resolution and author, not a locally fetched or visually verified binary. `media_sha256` is null with `NOT_COMPUTED_NO_DOWNLOAD`; do not treat a Commons SHA-1 or a filename as SHA-256. No image was downloaded, copied, converted, bundled, or delivered to the Web app in this handoff.

`match_id` remains null for every candidate. Photos from other events may be considered for a clearly labeled athlete profile only after the additional likeness/promotional-context review; they must not be presented as a Goal15 match photograph. Current-match photo evidence count is zero. The unresolved 2026 Worlds lead has empty `athlete_ids` and `depicted_athletes`; category association was not accepted as proof of who appears in the image.

## Coverage and remaining work

- 9 high-resolution Commons candidates have metadata/license records, covering 6 of the 8 current Goal15 star profiles plus all 3 other named participants (9 Goal15 target people; this count does not count every additional person named in group-photo captions).
- Lin Shidong and Kuai Man still lack a candidate accepted as depicting them.
- 0 assets are cleared for PTTI display; 0 link to one of the current five Goal15 matches; 0 binary SHA-256 values exist.
- Felix Lebrun's candidate page carries an explicit personality-rights warning. CC BY-SA requires attribution and share-alike for adaptations and does not itself settle the depicted person's rights or imply endorsement.
- One Wang Chuqin/Tomokazu Harimoto YOG candidate was rejected because the filename/title and page caption conflict on the event category; it is recorded under `rejected_candidates` and is not counted as a depiction.
- Candidate pages for the YOG and Commons portrait files identify photography from different events; keep those event labels visible and never substitute them as current-match action photography.

## Validate

From the repository root, run:

```powershell
python products/ptti-integration/scripts/validate_public_media_manifest.py
python -m unittest discover -s products/ptti-integration/tests -p test_goal16_public_media_manifest.py
```

The validator is deliberately fail-closed: it rejects unknown fields, duplicate asset IDs, a populated match ID, an invented/uncomputed media SHA, a category-only identity promotion, and any attempt to mark an asset display-approved in this candidate review package. It also confirms the pre-existing `ptti.match-library-index/0.1` strict-public package remains a five-match `STRICT_PUBLIC` view; it does not rewrite that package.

Before any asset can enter San's production rendering path, obtain and record a specific rights decision for the intended display context, visually inspect the correct source image and crop, confirm attribution/ShareAlike handling, create only permitted derivatives, hash the actual reviewed file, and issue a separately reviewed delivery manifest. Match-specific imagery additionally requires direct evidence linking the image to that exact match.
