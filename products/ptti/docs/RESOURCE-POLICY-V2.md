# PTTI Resource Policy V2

This policy classifies work by measured load instead of applying the desktop
build preflight to every task. It observes Windows resource state and never
changes the OS, stops applications, or fabricates measurements.

| Level | Examples | Start check | Runtime response |
| --- | --- | --- | --- |
| 1 - Light | Read-only checks, static checks, one ordinary page/link | No 2.5 GiB rule. Stop only for severe pressure: under 512 MiB available, under 1 GiB commit headroom, or commit at/above 98%. | Recheck before continuing; stop the task safely if severe pressure appears. |
| 2 - Medium | One browser video session or one WebView2 QA session | Require a measured process budget. Keep at least 512 MiB projected physical memory and 1 GiB projected commit headroom. | Sample system resources and that process tree; stop further QA steps if severe pressure appears or observed working set exceeds its budget. Do not kill the process automatically. |
| 3 - Heavy | Full EXE builds, multi-instance or other high-load work | Keep the 2.5 GiB start budget used by the build path. | Keep the existing 2 GiB runtime floor and stop safely below it. |

## Implementation

`scripts/resource_policy_v2.py` provides deterministic decisions over
`ResourceSnapshot`, Windows measurements through `psutil` and
`GetPerformanceInfo`, process-tree working-set sampling, and a bounded JSONL
monitor. All unit-test snapshots are synthetic. Live runs must record their
own measurements separately.

## Supported calls

From `products/ptti`, a light read-only check can be run without a process ID
or a RAM budget:

```powershell
.\.venv\Scripts\python.exe scripts\resource_policy_v2.py --level light
```

For one medium browser/WebView2 session, supply a measured peak budget and the
root PID; the command performs preflight and bounded runtime sampling:

```powershell
.\.venv\Scripts\python.exe scripts\resource_policy_v2.py --level medium --estimate-mib 1024 --pid <root-pid> --duration-seconds 180 --interval-seconds 2 --log-jsonl <local-log.jsonl>
```

A QA wrapper can run the same medium preflight before launch, then start a
runtime-only monitor against the launched PID:

```powershell
.\.venv\Scripts\python.exe scripts\resource_policy_v2.py --level medium --estimate-mib 1024 --preflight-only
.\.venv\Scripts\python.exe scripts\resource_policy_v2.py --level medium --estimate-mib 1024 --pid <root-pid> --duration-seconds 900 --interval-seconds 2 --runtime-only --log-jsonl <local-log.jsonl>
```

`--runtime-only` is for an already-preflighted process. The monitor reports a
normal `QA_PROCESS_EXITED` end when that PID exits and never kills it.

The GOAL107 isolated wrapper lives at `qa/goal107/Start-GOAL107-QA-V2.ps1`
and `.cmd`. Its 1024 MiB budget is based on the prior measured 627 MiB
working-set total for this R4/WebView2 process tree (about 1.6x allowance).
It runs the medium preflight before launch, then monitors only the exact PID
returned by `Start-Process` for at most 15 minutes. At a resource stop it asks
the user to close that QA window; it never terminates it or another process.
The wrapper's `-CheckOnly` mode performs validation without creating QA files
or starting an app.

For a heavy task already admitted by its build-specific 2.5 GiB preflight, use
the monitor with its root PID; this is supplemental and does not replace the
build gate:

```powershell
.\.venv\Scripts\python.exe scripts\resource_policy_v2.py --level heavy --pid <root-pid> --duration-seconds 180 --interval-seconds 2
```

The established high-load paths remain unchanged:

- `scripts/build_dual_source_v061_preview.py`: 2.5 GiB build-start gate at
  `MIN_START_RAM_BYTES` and its preflight.
- `scripts/dev_sync.py`: 2.5 GiB desktop-sync/build-start gate; its 2 GiB hard
  runtime floor is unchanged.
- `<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1`: the original native-launch
  path still has its 2.5 GiB guard. It is a single R4 launch path, not a build;
  V2 does not call or replace it because the formal launcher is out of scope.
  It can still block a medium Native QA session until separately approved.

Do not run `dev_sync.py` as part of a light/medium QA task: it may perform a
desktop update. Candidate-specific launch wrappers keep their own guards until
separately reviewed; the GOAL107 QA wrapper also retains its 2.5 GiB check.
The V2 CLI is a supported policy entry, not a launcher bypass.

Rollback: remove the new policy module, its tests, and this document. No
existing build guard, launcher, database, or desktop pointer is changed by V2.
