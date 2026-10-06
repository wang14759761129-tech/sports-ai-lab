# Local video sources and rights

PTTI does not bypass third-party access controls.

Supported source records:

- Local video: a user-provided local MP4/MOV/MKV/AVI with source/rights notes.
- RacketVision: explicitly downloaded official small benchmark, pinned dataset revision, clip identifier and research provenance.
- Licensed WTT Media: the user logs into WTT through the permitted workflow, obtains authorised download/licence, downloads the file, then imports that local file. PTTI records provider, asset/record ID, event, players, round, licence reference and rights notes. A licence reference is user-supplied metadata, not software verification of legal title.
- External reference: URL/title/event/players/notes saved locally only. A reference URL is never fetched or downloaded.

PTTI has no WTT login, password, cookie/session extraction, scraper, m3u8 downloader, DRM bypass, browser recording, stream capture, hidden API or archive downloader. Processing remains local; videos are not uploaded to a third party. WTT account-side licence approval and the actual licensed file are supplied by the user, not fabricated by the product.

Professional WTT inbox copies and their registered metadata live under the active isolated database's data directory; explicitly selected files are copied, not moved. Short-clip analysis uses the configured vision folders. Dataset/model/cache/video/output folders are ignored by Git. Original local files are retained unchanged. Do not commit broadcast media or user video to the repository. The RacketVision dataset card declares MIT; that does not prove a particular WTT broadcast licence, and no WTT download has been performed.
