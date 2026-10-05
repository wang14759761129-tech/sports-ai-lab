@echo off
setlocal
cd /d "%~dp0.."
call npm --prefix frontend run build || exit /b 1
.venv\Scripts\python.exe -m pytest -q || exit /b 1
.venv\Scripts\python.exe scripts\write_build_info.py || exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --name PTTI-Vision-Dev --icon assets\ptti.ico --collect-all webview --add-data "build/build-info.json;." --add-data "frontend/dist;frontend/dist" --add-data "data/samples;data/samples" --add-data "vision_worker/balltrack.py;vision_worker" --add-data "vision_worker/overlay.py;vision_worker" --add-data "vision_worker/candidates.py;vision_worker" --paths . apps\desktop.py
exit /b %errorlevel%
