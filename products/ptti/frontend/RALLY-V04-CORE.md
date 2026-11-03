# Rally v0.4 isolated core

`createReviewV3` validates manual start/end, result, tag and notes without associating a match. Include the existing `local_content_fingerprint` when exporting. `prepareReviewV3Import` validates the selected video's chunk fingerprint and duration before returning a preview; v2 imports preserve marks with an empty rally list. The caller must explicitly confirm before replacing state, and should warn before replacing unsaved work. The fingerprint is not the file's complete SHA-256.

Use `createRallyPlaybackCoordinator(core, adapter)` as the sole owner of manual Moment seek and rally playlist commands. Its `cancel` must be called before media replacement or component unmount. It delegates endpoint pause, repeat and seek timeout to the existing Playback Core; timeupdate-based boundary checks may overshoot and do not promise frame precision. Controllers must not bypass the coordinator with direct adapter seeks while a rally runs. Actual video playback, timeout behavior and end precision require browser validation.

This isolated core does not add a user-facing editor or wire v3 export into LocalManualLab. Existing v0.3 exports and imports remain unchanged until a separately reviewed UI integration.
