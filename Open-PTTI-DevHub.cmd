@echo off
powershell.exe -NoProfile -File "%~dp0Update-DevHub.ps1" -Open
if errorlevel 1 pause
