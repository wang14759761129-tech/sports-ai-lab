# Manual Review v2 contract

This contract describes user-entered observations and does not establish match identity, source rights, or independent verification. The player is responsible for establishing an identity from the exact selected media. SHA256 is a claim passed to this pure module, not proof that hashing occurred; a SESSION identity is valid only within the current browser session and must not be treated as stable across re-selection. Never use filename, size, or timestamp as proof of content identity. Do not export file paths or raw video.

`createReviewV2(media, marks)` builds a canonical export; `validateReviewV2(data, expectedMedia)` validates and rejects identity or duration mismatch. The v2 format is separate from v1 and does not automatically migrate or attach demo event records to real matches. No persistence or upload is performed. UI controls are responsible for warnings before session loss and for verifying that the player is ready before seeking.
