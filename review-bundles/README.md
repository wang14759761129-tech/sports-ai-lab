# PTTI three-line review patches — 2026-10-28

This branch holds source-review patches derived from the original local worktrees; it is not a merged, runnable release. Its parent is the already reviewed private baseline `0b4da4e106580cf93b6c8a451525a6c2aa23dcde`, not the original shared object history. Apply only after independently obtaining and reviewing the stated local source bases; the parent snapshot is not guaranteed to be those bases. Overlapping paths require human integration review.

| Patch | Exact base | Exact source HEAD | SHA256 |
|---|---|---|---|
| main.patch | `54d75007eb7dc63e33dd8ac419afc20cf7e2615c` | `938c7ea46db5b12dd5f7bf8d95bb13e85094bf26` | `509b3a4b7046842f0ddb0022346f4d7f8a43b9e48cc04a4b586cdebc7b9e91ec` |
| playback.patch | `3ec76c21b0023631f74a793f070c99207c603aa7` | `a9824180a87eb3a4b424ca35db136809bd7b4a73` | `6fe95fa859da2ee657cb09e83181ea00d18a39f1e9d203e07ea9f3f9b29f02e5` |
| san.patch | `c6b0a94a3dbbb2306c3556e3d24a24a4faff8e60` | `fc03395b78fbae0a12cb60a537712bba19c38b6b` | `3d4e333f615a7a4dadc4ec52495fb1fecf67b31070a17e61cba27d5d3b5f58a3` |

Only changed code/config/tests in selected text formats were included. Markdown documents, binaries, images, databases, node_modules, personal media and untracked files are excluded. One SAN test file `products/ptti/frontend/scripts/test-cinema-viewing.mjs` was excluded pending personal-name review. One MAIN test file `products/ptti/tests/test_youtube_data_api.py` was excluded because it contained an email-like string requiring manual review; no inference about its sensitivity is made. These are not full worktree snapshots. Basic credential, private-key, email and Windows user-path pattern scans found no matches in the included patches. This is not a comprehensive secret, licensing, or privacy certification.

Source branches remain separate; no merge, release, media permission, GUI or playback validation is implied. Founder QA and Native acceptance remain NOT_TESTED. Third-party media is not bundled by these patches. No production database or launcher is included.
