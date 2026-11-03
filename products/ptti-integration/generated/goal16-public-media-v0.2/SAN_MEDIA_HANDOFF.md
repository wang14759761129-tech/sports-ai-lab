# PTTI public profile media — San handoff v0.2

This is a separate strict-public media package. It does not alter the existing GOAL15 match library or the GOAL16.2 internal review inventory.

## Consumer contract

- Manifest: `public-media-manifest.json`
- Contract: `ptti.public-media-manifest/0.2`
- Schema: `products/ptti-integration/contracts/public-media-manifest-v0.2.schema.json`
- Validate: `python products/ptti-integration/scripts/build_goal16_public_media.py --validate`
- There are four assets, each matched by an existing stable `athlete_id`; no asset has a `match_id`.
- `use_scope` is always `ATHLETE_PROFILE_EDITORIAL_ONLY`. These are not approved for homepage hero promotion, sponsored placements, ads, or any framing that implies endorsement.
- `derivatives[].path` is relative to this directory. Use the requested resolution from the 4:5 pairs; Liang Jingkun intentionally uses full-frame 3:2 variants because a portrait crop obscured the incoming ball across his face.
- Show the complete `attribution` with a visible link to the Commons file page and license. All derivatives are distributed under the source CC BY-SA license; preserve ShareAlike terms and note modifications.
- Do not use these photos as current Goal15 match photography. All `match_id` values remain null because these photos are from different or unverified events.
- Do not interpret this package as video playback permission, athlete endorsement, or permission for any non-editorial use.

## Asset map

| athlete_id | Subject | Asset ID | Responsive files |
|---|---|---|---|
| `athlete:123980` | Tomokazu Harimoto | `commons:attc-2017:harimoto-1` | `assets/commons-attc-2017-harimoto-1-400x500.webp`, `assets/commons-attc-2017-harimoto-1-800x1000.webp` |
| `athlete:112409` | Jonathan Groth | `commons:jonathan-groth-portrait` | `assets/commons-jonathan-groth-portrait-400x500.webp`, `assets/commons-jonathan-groth-portrait-800x1000.webp` |
| `athlete:121411` | Wang Manyu | `commons:acttc-2016:wang-manyu-17` | `assets/commons-acttc-2016-wang-manyu-17-400x500.webp`, `assets/commons-acttc-2016-wang-manyu-17-800x1000.webp` |
| `athlete:119588` | Liang Jingkun | `commons:acttc-2016:liang-jingkun-8` | `assets/commons-acttc-2016-liang-jingkun-8-480x320.webp`, `assets/commons-acttc-2016-liang-jingkun-8-960x640.webp` |

Each record carries the original Commons page and file URL, photographer, license, actual original SHA-256, and SHA-256 plus dimensions for every derivative. The source bytes are not included in this strict-public folder; four local source copies are retained in the ignored internal review directory for this worktree only. Public derivatives are stripped of EXIF/GPS metadata.
