@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL.ps1" %*
if errorlevel 1 (echo Installation failed. No user database was removed.)
pause
