# Cinema 3.0 isolated Windows Alpha

Version: `0.1.10-cinema-b8017ac`, QA port `4211`.

This profile uses the existing GOAL23/30 builder and WebView2 host. It does not
change the legacy profiles, selector, Native player, user data, or release pointer.
The build pins the validated San b8017ac candidate manifest and all 35 static
files. Nine public packages retain their schema and rights semantics, including
the admitted 8-match / 19-source / 8-athlete delta. Main's observed workspace
commit and its earlier content reference are recorded separately. GEX remains
an independent prototype and is not copied into this package.

The executable is newly compiled, unsigned, and QA-only. It embeds its Host,
San, Main, Playback-interface, public-data and static-build identities. Native
bridging stays disabled. Official links are not playback or redistribution rights.

## Build and verify

Use `goal23/build_goal23.py` with `--config goal57/goal57-build.json` and the
existing explicit San/Main/static/parent-release/Python arguments. Also supply
`--playback-root` pointing to the verified Playback workspace. Use `preflight`
first, then one bounded `build`. The output root must be a new GOAL57 directory.
Existing output is refused. RAM must remain at least 2.5 GiB and natural input
idle must be at least 60 seconds before the build-tool and compilation stages.

`host/PTTI-Desktop-Fan.exe --verify-only` checks the complete payload without
starting WebView2. Normal opening uses a version/port-scoped temporary QA
profile, never the production WebView2 profile. It starts only on loopback.
Closing the candidate window shuts down its own server; no other process is
stopped. Profile data is retained for synthetic persistence acceptance.

## Acceptance and rollback

Build verification is separate from observed GUI and founder approval. Check
Grand Lobby, Cinema/search/detail, official Highlights vs Clips, Watch/return,
Collector's Lounge/save/remove/reopen, Theater information, Arena, My Matches,
Pro Lab and Demo. Check narrow and 16:10 windows only with supported GUI controls.
Record official-page opening separately from actual playback. Use synthetic data.

Rollback is to close only this QA window and open an unchanged earlier candidate
or the unchanged formal desktop entry. Do not migrate, clean, or delete profiles.
Activation, shortcut changes and publishing require separate authorization.
