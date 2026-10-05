@echo off
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 exit /b 1
cd ..
.venv\Scripts\python scripts\make_icon.py
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pytest -q
if errorlevel 1 exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onedir --name PTTI --icon assets\ptti.ico --paths . --add-data "frontend/dist;frontend/dist" --add-data "data/samples;data/samples" --collect-all webview apps/desktop.py
