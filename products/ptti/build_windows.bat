@echo off
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 exit /b 1
cd ..
.venv\Scripts\python -m pytest -q
if errorlevel 1 exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onedir --name PTTI --paths . --add-data "frontend/dist;frontend/dist" --add-data "data/samples;data/samples" --collect-all webview apps/desktop.py
