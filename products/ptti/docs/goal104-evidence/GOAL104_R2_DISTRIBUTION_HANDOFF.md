# GOAL104-R2 — distribution hold supersedes GOAL104 photo admission

The earlier technical image/identity/browser results remain historical evidence.
They do **not** establish permission to include the JPEG in downloadable software
or a public Web build. Do not use the old v0.1 public manifest for delivery.

## Current delivery state

- Actual WTT asset: `NEEDS_PERMISSION_FOR_DISTRIBUTION`.
- Active manifest: `data/professional/cover_review/public-match-cover-manifest.v0.2.json`.
- Approved distribution assets: **0**. The v0.2 manifest adds `withheld_assets`,
  explicit distribution policy and target-specific written-permission requirements.
- Original v0.1 manifest, its hash, nine-source review and browser screenshot
  are retained unchanged for provenance; they are not active release manifests.
- JPEG moved byte-for-byte from Vite `public` to
  `docs/goal104-evidence/restricted-media/wtt-53034902256.jpg`.
- Original SHA-256 remains
  `faaaa29e1872b917fa3e548f1d829c7e5dbe91703152075e80be69b095bf00d5`.
- The exact source binding, attribution and image adapter remain. Current runtime
  denies the real photo and uses the existing fallback. No other media permission
  or watching/Story/favorite behavior is broadened.

## Enforced build path

Vite's build plugin validates `public` before building, emits the active manifest
into `dist/media-distribution-manifest.json`, then checks the actual output. Unknown
raster files, withheld image hashes (even renamed), missing images, inconsistent
manifests, unsupported versions and insufficient permission stop the build.

The standard R4 builder `scripts/build_dual_source_v061_preview.py` checks the
frontend before PyInstaller and the full package afterward. Its staged professional
catalog excludes historical/internal `cover_review` files and includes only the
active v0.2 manifest. Source evidence is never removed by this staging step.

Commands from `frontend`:

```text
npm run test:media-distribution
npm run test:match-photo
npm run test:feed
npm run test:goal99-story
npm run test:youtube-thumbnail
npm run build
node scripts/check-media-distribution.mjs dist
node scripts/check-media-distribution.mjs dist --windows
node scripts/check-media-distribution.mjs <WINDOWS_PACKAGE_ROOT> --windows --package
```

The old generated dist was actually rejected for containing the withheld JPEG.
The rebuilt dist passes with zero admitted images. Windows staging and package
gate are verified without producing or launching a Windows EXE.

## Minimal written-permission checklist for WTT

Contact: redacted@example.invalid. No email has been sent.

Request a reply identifying this exact photo (and any additional photo IDs), PTTI,
the intended match-card use, and the following independent terms:

| Term | Required clarification |
|---|---|
| Platforms | Web, Windows desktop, or both |
| Local distribution | May JPEG bytes be bundled with downloadable apps, installers and Web assets? |
| Remote-only display | If local distribution is disallowed, is remote display allowed, from which supplied URL and under which conditions? |
| Image changes | May PTTI resize, re-encode or crop? Must logos/watermarks remain? |
| Attribution | Exact copyright/photographer credit, placement and required links |
| Duration/territories | Start/end date, territory and withdrawal conditions |
| Commercial context | Whether the intended free/paid/sponsored product context is covered; no implied athlete endorsement |
| Other photographs | Exact additional IDs and whether the same grant covers them |

After receiving a reply, Main must review and retain the evidence privately, record
an evidence ID/SHA, and approve only its actual scope. A hash is not proof of rights.
For the current shared local-asset pipeline, both WEB and WINDOWS_DESKTOP packaging
must be explicitly covered. A Web-only or remote-only grant cannot enable it unchanged.

If local packaging for both targets is approved: update the existing photo sidecar
with `WTT_WRITTEN_PERMISSION`, targets, expiry and `written_permission`; add that
same asset/hash/path to the active manifest; restore the preserved bytes to its
existing public path; regenerate the manifest checksum; run the gates and regression
tests, then hand the exact new source SHA to HOST. No new UI or player is required.
The adapter currently preserves the full frame and watermark; broader crop/promotion
rights would require a separately reviewed change.

If permission is narrower, keep this build blocked for that asset and implement only
the specifically allowed delivery path after review. Do not infer permission for
video embedding, downloading, analysis, other matches or raw photo redistribution.
