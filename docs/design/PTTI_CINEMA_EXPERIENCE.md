# Cinema / The Grand Theater

Core journey: Grand Lobby → browse/search → Private Theater → separate Match Room → Moment → Collector’s Lounge → return to same time → Grand Lobby. Implemented as hash navigation in the prototype; existing SAN routes must use a mapping rather than copying hash handling.

Lobby: a single major visual and direct theater action, three demo programmes, then a bridge to Arena. Cards truthfully say DEMO. Tonight is an editorial grouping here, not a verified current schedule.

Theater: native video controls, opt-in original generated video or selected local media, readable source status, lights-dim toggle, independent information pane, time marker plus 160-character personal note. No video leaves the device. On navigation away, pause playback. On source replacement, pause and revoke the old object URL. On pagehide release media URL. No codec guarantees.

Collection: exact time, title, user note, media kind, revisit, remove and JSON export. Storage namespace `ptti.gex001.v1`; capped at 500 moments in this demo. Avoid repeated click duplicates within one second for the same media. After refresh, local files must be selected again. Local filename/size/time is only a convenience identity and MUST NOT become an evidence identity in production. Export includes these user-provided metadata and notes; keep private.

Information architecture proposal for integration: Cinema contains Lobby, Watch, Stars, Pulse/Clips, Rivalries, Collection and personal Corner. Keep current SAN fan pages reachable and preserve return context. Premiere Night, official content ingestion, Originals and cross-device collection are PENDING, not implemented.

Acceptance examples: bookmark actual current media time; refreshing preserves records when storage available; return does not autoplay; wrong video never silently seeks based on another identity; source rights are independent of playback; content panel cannot cover video. Browser/native checks remain separate.
