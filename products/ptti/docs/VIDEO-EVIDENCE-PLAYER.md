# Video Evidence Player v0.1

Local Video → Manual Evidence → Clip Playlist → Replay → Persistent Knowledge.

## Existing capability audit

| State | Capability |
|---|---|
| ALREADY_WORKS | pywebview / WebView2, local FastAPI server bound to 127.0.0.1, HTML video, registered-match video endpoint, manual Game/Point/Rally timeline, existing Hit candidate evidence UI |
| NEEDS_EXTENSION | Source-independent clip library, source identity, local-file relink, playlists, manual review records |
| MISSING → ADDED | Independent Video ID + Evidence ID + Collection ID, tags/notes/search, ordered cross-source playback, durable evidence audit |
| BROKEN → FIXED | FFprobe locale decoding broke Chinese paths; explicit UTF-8 fixes it. Buffered media could retain old Windows file handles; cancellable streaming and player teardown release them |

The implementation extends the existing HTML video / loopback FastAPI / guarded SQLite stack. It does not install a second player framework or a GPU runtime.

## Source and persistence

- Register a **reference** to the original authorized local file. No full-video copy or full decode at import.
- Probe metadata; calculate SHA256 in a single background worker using 1 MiB blocks. Playback is available before hashing finishes.
- Media requests contain a registered Video ID, never a user-provided file path. GET/HEAD and single-byte Range/206 use bounded 64 KiB streaming within the existing loopback service. Disconnect or page exit closes the file handle; full videos are not loaded into RAM. Multipart ranges are explicitly refused with 416.
- Verify size, mtime, and file identity before serving. Missing sources retain their evidence. Relink requires matching size and full SHA256, not just a filename.
- New SQLite tables are additive: `evidence_videos`, `video_evidence`, `evidence_collections`, `evidence_audit`. Existing match tables are preserved.
- The new store rejects Production mode before opening any database connection. Preview uses `%LOCALAPPDATA%/PTTI-Dev/VideoEvidencePreview/matches.db`; QA can use an explicit OS-temp database.
- Loopback client, Host, and same-origin checks prevent third-party websites from reading registered local media through this router. Remote/UNC media sources are not supported.

## Athlete workflow

1. Import an authorized local video and confirm its source/use rights.
2. Play, seek, slow down, or approximately step using the source frame rate. Frame stepping is explicitly approximate.
3. Mark start/end, write notes, choose custom tags, and save.
4. Filter clips; select several clips into a named collection. Order them with up/down controls.
5. Play sequentially across original sources; use previous/next/replay, single-clip loop, playlist loop, and context padding.
6. Reopen the app. Sources, notes, tags, clips, collection order, and audit records persist.

No automatic tactical assertions are generated from manual labels.

## AI adapter boundary

`EvidenceStore.import_ai_candidate(video_id, candidate)` is an internal adapter contract. It requires a verified registered video SHA matching `candidate.video_sha256`, a bounded canonical timestamp, and the original event ID. The entire RAW candidate is retained.

- Import: `source=AI_SUGGESTED`, `review_status=REVIEW_REQUIRED`.
- Human review: `source=AI_REVIEWED`, with RAW unchanged and an append-only audit.
- It cannot silently become `MANUAL_CONFIRMED`.

The frozen research outputs are not exposed through a new arbitrary file-reading endpoint. Automatic ingestion from Hit v0.3 is **not enabled** in this preview. A future product adapter must verify the original full-video identity and global timestamp mapping before calling this contract. No official TEST annotations are read.

## Build and limitations

Frontend: `npm run build`. Backend: `pytest` and Ruff on the new modules. Windows: `python scripts/build_video_evidence_preview.py` in the existing desktop build environment.

Output is a distinct `PTTI-Video-Evidence-Preview` onedir build. It includes FFmpeg/FFprobe and the frontend, not research videos, model weights, or databases. It is not a formal release and is not merged into main.

H.264 MP4 playback is the supported acceptance path. MOV/MKV/AVI or other codecs may not play in WebView2; no automatic multi-gigabyte transcoding is performed. Exact frame stepping, measured athlete time savings, and AI automatic event accuracy are not claimed.

Research Gate stays `HIT_EVENT_V0_3_CONFIG_FROZEN`; Hit product Gate stays `HIT_EVENT_V0_2_PARTIAL`. GAME_5 downloading and evaluation remain separate and untouched.

## Browser-hosted desktop frontend QA (2026-10-08)

- Registered full, lawful TRAIN videos game_4 (3,947,371,986 bytes, 1920×1080, 526 s) and game_3 (4,637,044,123 bytes, 1920×1080, 618 s) by reference. No research annotation parsing or GPU inference.
- Saved ten distinct game_4 intervals through the UI with three custom QA tags and notes; they persisted after a page reload. An eleventh game_3 clip verified cross-source playlists.
- Cross-source playlist, previous/next, replay, 0.5× / 2×, single-clip and playlist loops were clicked. Playback switched to the correct original Video ID and source interval.
- A Chinese-path QA hardlink was moved while the original research file remained untouched. Missing File preserved evidence; full-SHA relink restored playback. After the cancellable-stream fix, leaving the player released the file handle and the QA alias could move without stopping the server.
- Full suite: 438 passed, 0 failed, 1 skipped (optional isolated vision runtime absent from this worktree), 1 existing Starlette/httpx deprecation warning. New-module Ruff and frontend production build passed. Final streaming changes additionally passed all 14 player tests.
- Native packaged Windows acceptance is recorded separately after the preview build; this browser QA alone is not native GUI acceptance.
