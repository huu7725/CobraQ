@echo off
setlocal
cd /d "%~dp0"
call setup_sandbox.bat
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" tools\sandbox.py smoke
exit /b %errorlevel%
