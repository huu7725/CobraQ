@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" tools\sandbox.py stop
exit /b %errorlevel%
