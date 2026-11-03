# Architecture

React/TypeScript/Vite and Recharts render static assets served by FastAPI. The desktop shell starts the same app on an ephemeral loopback port and opens pywebview. A future shell can reuse these HTTP endpoints. The server listens only on 127.0.0.1.

`core/engine.py`: ingestion, schema/scoring validation, independent pure analytics and deterministic structured insights. `backend/repository.py`: parameterized SQLite access. `backend/main.py`: Pydantic metadata/report models and import coordination. `apps/desktop.py`: lifecycle. `frontend/src`: desktop-first interface. No empty placeholder folders; split modules as domain size grows. The standard-library CSV parser avoids an unnecessary pandas dependency for this small point dataset.

An import validates the entire file, rejects fatal issues, computes analysis, and saves one JSON payload transactionally. Raw parsed text values are retained, not normalized in place. Reopening uses the saved versioned analysis. Future schema adapters must explicitly map fields and retain the source schema version. Future LLM adapters can consume analysis JSON without changing the calculation core; no LLM integration or network calls exist now.

API: GET `/api/health`; POST `/api/matches/import` multipart `file` and JSON `metadata`; POST `/api/matches/sample`; GET `/api/matches`; GET `/api/matches/{id}`; GET `/analysis`, `/points`, `/export`, `/report` suffixes; DELETE `/api/matches/{id}`. Validation failures return a report with `match: null`, not a saved match. Upload limit is 10 MB. Local server has no authentication and is intended for trusted personal desktop use, not deployment on a network.
