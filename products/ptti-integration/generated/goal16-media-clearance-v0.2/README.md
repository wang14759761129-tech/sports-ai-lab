# GOAL16.2 internal image review copies

This local-only directory contains the four source images that were visually reviewed and used to create the WebP derivatives in the separate strict-public package. The originals are ignored by Git because the Wang Manyu and Liang Jingkun Commons files contain GPS EXIF tags; do not copy originals into a public delivery. Their actual source-file SHA-256 values are recorded in `rights-review.json` and the public manifest. Public derivatives have EXIF removed.

The original files were obtained only from the four Commons source URLs listed in `rights-review.json`. To rebuild derivatives, place each original at the path recorded there and verify its SHA-256 before running:

```powershell
python products/ptti-integration/scripts/build_goal16_public_media.py --build
python products/ptti-integration/scripts/build_goal16_public_media.py --validate
```

The three personality-warning files and the file with unresolved canonical athlete identity were not downloaded. They remain internal candidates only.
