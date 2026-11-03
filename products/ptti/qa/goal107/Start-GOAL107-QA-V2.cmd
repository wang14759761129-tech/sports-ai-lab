@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -File "%~dp0Start-GOAL107-QA-V2.ps1"
set "PTTI_QA_V2_EXIT=%ERRORLEVEL%"
if not "%PTTI_QA_V2_EXIT%"=="0" (
  echo PTTI GOAL107 QA V2 stopped. Exit code: %PTTI_QA_V2_EXIT%
  pause
)
exit /b %PTTI_QA_V2_EXIT%
