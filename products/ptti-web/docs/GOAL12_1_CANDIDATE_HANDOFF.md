# GOAL 12.1 Candidate Handoff

- San feature source commit: `99f582b95ee8c200b7baf40a33fc857fe9d35328` (`fix(ptti-web): open insight after successful demo import`).
- Playback Core identity: `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe`; source path remains the separately managed Playback worktree.
- Candidate branch: `codex/ptti-goal12-1-candidate`.
- Candidate is local-only and not accepted for the desktop release registry. It must not be activated until the release owner records the candidate's full source hashes and validation evidence.
- 4174 accepted manifest remains unchanged. It pins 60 file hashes for the prior release; the feature commit changes six of them.
- `npm run check:cinema-insight` covers success-only Insight navigation, invalid/stale load remaining on Cinema, repeated-click prevention, zh/en labels, and the active-video-session replacement guards. This is a lightweight source-contract test, not a Chrome E2E pass.
- Golden/demo data remains `SIMULATED_ONLY`; review/public access policy is unchanged.
- No video, report, or annotation is uploaded or persisted by this candidate.
- Accepted 4174 snapshot is pinned at San `0f544307cfe0b076ada2894674f5cbc20f52e579`; all 60 registered file hashes match, and active-launcher `-CheckOnly` reused `http://127.0.0.1:4174/` with Playback `304eb661b8a16d6af78a70743bb9e1ef1bdb2fbe` (no browser opened).\n- Chrome acceptance: `NOT RUN`; final measured available RAM was 2.18 GiB (< 2.5 GiB guard), so no Chrome process was started.