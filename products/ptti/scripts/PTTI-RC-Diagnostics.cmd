@echo off
setlocal
chcp 65001 >nul
set "diagnosticPython=%PTTI_QA_DIAGNOSTIC_PYTHON%"
if not defined diagnosticPython set "diagnosticPython=%~dp0..\.venv\Scripts\python.exe"
if not exist "%diagnosticPython%" set "diagnosticPython=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%diagnosticPython%" (
  echo 未找到可用的隔离 Python。请交由开发会话配置，不会自动安装软件。
  pause
  exit /b 2
)
"%diagnosticPython%" "%~dp0windows_rc_diagnostics.py" %*
set "diagnosticExit=%ERRORLEVEL%"
echo.
echo 检查完成。此窗口保留结果，按任意键关闭。
pause >nul
exit /b %diagnosticExit%
