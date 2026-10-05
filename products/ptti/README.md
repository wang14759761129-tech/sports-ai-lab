# PTTI 0.1.1 — Research Integration Release

Personal Table Tennis Intelligence is local-first Windows match-analysis software for the owner and Kaikai: CSV → validation → saved match → statistics/charts/evidence → point explorer → JSON/HTML export → reopen. No API key, cloud, telemetry or exaggerated AI claims. **KAIKAI TEST 01: PENDING.**

## Run

Download the [Windows release](https://github.com/wang14759761129-tech/sports-ai-lab/releases/tag/ptti-v0.1.1) when published. Extract the whole ZIP, read START-HERE.txt, open PTTI/PTTI.exe. Keep _internal beside it. Windows 10/11 x64 and Edge WebView2 Runtime required; no Python/Node/Git/Codex/VS Code needed for users.

## Architecture and research

[Research track](../../research-tracks/match-analytics/serve-third-ball-analytics/) → Protocol/schema → compatibility adapter → pure analytics → FastAPI/SQLite → React/Recharts → pywebview/PyInstaller. See [research basis](docs/RESEARCH-BASIS.md), [compatibility](docs/SCHEMA-COMPATIBILITY.md) and [evidence metric definitions](docs/EVIDENCE-METRICS.md). Pilot 1C only supports descriptive match-state records in its ten-point segment; tactical evidence remains insufficient. Pilot 2 has not started. Software output is not a scientific result.

## Supported CSV

Native 1.0.0-new: game, point, server, winner, score_a, score_b; A/B, post-point scores, original strict optional codes. Historical protocol_v0_3: game_number/point_number, player/opponent, pre-point server/receiver scores and up to all 21 research fields, auto-detected. player=A/opponent=B; enter names accordingly. Original values and uncertainty preserved. Unknown core identities/scores, mixed formats and impossible sequences reject.

Templates: data/samples/synthetic.csv and data/samples/protocol-v0.3-example.csv, both explicitly synthetic. [Fields](docs/release/DATA-FIELDS.md). Real Pilot annotations are test evidence, not a shipped training match or tactical conclusion.

## Development and release build

From products/ptti in the full monorepo, with Python 3.12+ and Node 22.12+ (or 20.19+):

```bat
setup_windows.bat
run_dev.bat
.venv\Scripts\python -m pytest -q
build_windows.bat
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_release.ps1
```

Live reload: run_backend.bat and run_frontend.bat separately. Native shell serves built frontend; rebuild after edits. Tests reference canonical research fixtures in the full monorepo. Git includes source/tests/lockfile/docs/scripts, not generated binaries or personal data. ZIP/SHA256 belong in GitHub Release assets. Packaging refuses to overwrite old handoff output.

## Storage, versions and limits

%LOCALAPPDATA%\PTTI\matches.db; PTTI_DB developer override. Close app before backup. Product/analytics/adapter 0.1.1, native schema 1.0.0-new, research protocol v0.3. Old saved 0.1.0 analyses stay unchanged and labeled; reimport CSV for new rules. Export contains raw source/provenance.

No mid-game starting state, doubles identities, cross-game service/match-length enforcement or annotation-consistency certification. Receive subtypes coarsen with warnings/raw retention. No direct third-contact success metric, data editing, JSON reimport, exact point drilldown, video/CV/LLM/cloud. Clean-machine/Kaikai testing, printing and large-match performance remain pending.

Only next external milestone: **KAIKAI TEST 01** — independent unzip/launch/sample/CSV/dashboard/explorer/restart/persistence/export. Failures become bugs; no broad v0.2 work. [Feedback](docs/USER-FEEDBACK.md), [roadmap](ROADMAP.md), [verification](docs/integration-verification.md).
