# GOAL88 two-workspace QA selector

This is an isolated Windows selector candidate, not a production launcher. It presents two primary choices. The default build remains the original `DEV_PREVIEW` mode; the GOAL90 build mode below creates a separate candidate and does not alter existing selector builds.

- **CINEMA — DEV_PREVIEW** opens the already-running San Vite preview only after checking that the requested loopback port is owned by the expected Node/Vite process. The preview follows the live San working tree and is not a frozen desktop release.
- **CINEMA — QA_DESKTOP** (GOAL90 only) launches one fixed WebView2 desktop candidate after checking its EXE SHA-256, release-manifest SHA-256, embedded release identity, package path, and exact running-process path. It does not open the browser development preview.
- **PRO — ACCEPTED LOCAL** invokes the existing Web Pro active launcher only after checking its pinned script, active-release manifest, accepted release manifest, all 61 release/evidence hashes, and health response. The existing launcher retains its own guards.

The candidate does not start Native R4. The original R4 route remains in the untouched `PTTI Cinema.lnk` selector. The inspected R4 preview package is valid, but its separate QA database is absent and no San-to-R4 bridge is enabled. The existing R4 entry and its data must remain under the original guarded flow until a supported isolated database path is approved.

The target manifest is local-only because it contains this machine's filesystem paths. The build embeds its SHA-256 into the selector so path or target changes fail closed. The external candidate directory also contains `release.json` and the generated source for reproducibility. The selector never modifies the formal shortcut, formal launcher, R4 package, 4174, user database, Journal, or personal media.

Build with `Build-GOAL88-QA.ps1` only into a new, empty candidate directory. Run the resulting executable with `--verify-only` to perform read-only identity checks without opening Cinema or Pro. Do not run `dev_sync.py`, push, deploy, or activate this candidate as a release.

For GOAL90, pass `-CinemaMode QA_DESKTOP` and `-CinemaCandidateDirectory <exact candidate path>` to a new output directory. The desktop release must already be built and verified. The QA selector target manifest is local-only, embeds its own SHA-256 in the EXE, and pins the desktop EXE and release manifest. `--verify-only` validates identities but does not prove that either button was clicked or that a GUI window rendered.
