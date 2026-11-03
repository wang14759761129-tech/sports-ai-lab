# PTTI Technology Radar v0.1

Audit date: 2026-10-07. Decisions apply to isolated research and development, not commercial product approval.

Full problem/current solution/before-after/benefit/cost/risk cards: `../research/vision-benchmark/TOOL_VALUE_CARDS.json`.

| Tool | Ring | Decision | Evidence / purpose |
|---|---|---|---|
| Supervision | TRIAL | B_BENCHMARK | Measured real overlay: 10 vs 10 adapter LOC, identical pixels, 0.025s vs 0.062s/240 frames; no proven code-saving benefit |
| RF-DETR | HOLD | E_REJECT | Measured pretrained Nano: 9/115 localized (7.83%), 6 FP on 125 sparse frames; NO_VALUE for replacement; no training |
| CVAT | TRIAL | C_LATER | 8 local tasks, 125 native-GT XML round-trip rows; Docker/service/UI/100-event timing NOT VERIFIED |
| uv | ADOPT | A_NOW | Fresh isolated lock rebuild reproduced all 26 package versions; Python 3.12.14 vs auto-selected 3.12.15 recorded; legacy envs unchanged |
| Ruff | ADOPT | A_NOW | New research scope lint passes; legacy scan 513 findings report-only; no automatic repository rewrite |
| ONNX Runtime | ADOPT | A_NOW | Keep existing worker; no migration required |
| Windows ML | ASSESS | C_LATER | Assessment only; test supported Windows/EP/device before delivery decision |
| DuckDB | ASSESS | C_LATER | Assess Parquet analytical layer only when query/RAM measurements show a need |
| SAM2 | TRIAL | B_BENCHMARK | Keep existing trial and recovery evidence; no reinstall or size escalation |
| Grounded SAM2 | HOLD | E_REJECT | Duplicate wrapper currently offers no proven product value |
| MMPose / RTMPose | TRIAL | D_RESEARCH_ONLY | Keep research observation UI; no stroke classifier or extra model |
| LanceDB | HOLD | C_LATER | Reassess only after Similar Rally/Video Embedding requirement |
| llama.cpp | HOLD | C_LATER | Hold until evidence-query product requirement; no LLM installed |

Existing ADOPT assets: FFmpeg, OpenCV, SQLite, ONNX Runtime, pytest/TypeScript build stack.
New ADOPT scope: uv for new isolated environments and Ruff for new research code only.
No bulk migration, formatting, model replacement, database migration or product dependency change.

Capacity policy: SQLite for transactional match metadata; streamed JSONL/CSV for current evidence.
Parquet is a possible columnar archival layer, not currently implemented. DuckDB is appropriate for future offline analytical scans over Parquet if measured scans/join costs justify it.
At 1 million observations the present verbose ~400-byte JSONL shape would be roughly 400 MB; actual schema density/compression must be measured.
This estimate is not a capacity benchmark and does not justify changing storage now.

Windows ML may manage execution providers and devices, but CUDA/NPU coverage, OS support, model operators and package delivery need an isolated deployment test.
Existing RTMPose CUDA/CPU ONNX path already works; no claim that Windows ML will remove all bundled GPU runtime.

CoTracker remains RESEARCH_ONLY outside the product path. No installation, telemetry, cloud upload or external AI API is introduced.

Official sources:
- [Supervision](https://github.com/roboflow/supervision)
- [RF-DETR](https://github.com/roboflow/rf-detr)
- [CVAT](https://docs.cvat.ai/docs/administration/community/basics/installation/)
- [uv](https://docs.astral.sh/uv/)
- [Ruff](https://docs.astral.sh/ruff/)
- [ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/)
- [Windows ML](https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/overview)
- [DuckDB](https://duckdb.org/docs/stable/)
- [SAM2](https://github.com/facebookresearch/sam2)
- [Grounded SAM2](https://github.com/IDEA-Research/Grounded-SAM-2)
- [MMPose / RTMPose](https://github.com/open-mmlab/mmpose)
- [LanceDB](https://github.com/lancedb/lancedb)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)
