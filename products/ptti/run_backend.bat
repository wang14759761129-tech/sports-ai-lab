@echo off
cd /d "%~dp0"
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
