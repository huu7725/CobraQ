@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import fastapi, dotenv, passlib, jose, psutil" >nul 2>&1
if errorlevel 1 (
    call setup.bat
    if errorlevel 1 exit /b 1
)
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" tools\sandbox.py init
exit /b %errorlevel%
