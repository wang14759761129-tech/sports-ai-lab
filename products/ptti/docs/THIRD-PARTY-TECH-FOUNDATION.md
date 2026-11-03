# Technology Foundation third-party provenance — research only

| Component | Version / source | Code license | Checkpoint license | Use |
|---|---|---|---|---|
| RF-DETR Nano | 1.11.2 / `7433d5919d0f7e72cc6cb78663e0a731afd499e0` | Apache-2.0 | Apache-2.0 core Nano; official MD5 verified; SHA in Nano report | isolated pretrained comparison only; no Plus |
| Supervision | 0.30.8 / `2c261cf98f2d412b7f87f6052b21b24019f09a96` | MIT | none | isolated annotation/video-source/sink trial |
| CVAT Community | source-audit HEAD `13475a854a02bb0714465e0edf19304e462d31b9`; not installed | MIT core; components have separate terms | none installed | local labels/export workflow prepared; service/UI untested |
| uv | 0.12.23 | MIT OR Apache-2.0 | none | isolated lock/sync/rebuild experiment |
| Ruff | 0.16.10 | MIT | none | report-only legacy lint; minimal new-research checks |

Runtime wheel/package versions and Python interpreter sources are saved in the local `stack_inventory.json`.
Fresh Supervision dependency reconstruction uses the committed lock. RF-DETR environment was installed from
pinned package versions and a locally available official torch wheel; it is not claimed to have a uv project lock.
Research environments do not modify any existing validated product/vision package directory.
Weights, videos, dataset annotations and generated research task archives remain outside Git and all shipping assets.

Existing SAM2, Grounding DINO, RT-DETR, RacketVision and RTMPose provenance stays in their prior registry/docs.
RTMPose standalone checkpoint rights remain UNKNOWN; Apache code rights do not establish those checkpoint rights.
Existing Extended OpenTTGames attribution and CC BY-NC-SA 4.0 non-commercial boundaries remain in effect.
RacketVision dataset redistribution rights are not independently established; use only existing local research access.

Official references: [RF-DETR](https://github.com/roboflow/rf-detr),
[Supervision](https://github.com/roboflow/supervision), [CVAT](https://github.com/cvat-ai/cvat),
[uv](https://github.com/astral-sh/uv), [Ruff](https://github.com/astral-sh/ruff).
