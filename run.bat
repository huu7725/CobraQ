@echo off
setlocal
title CobraQ Server
cd /d "%~dp0"

".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 (
    call setup.bat
    if errorlevel 1 exit /b 1
)

cd /d "%~dp0backend"
set "COBRAQ_POPPLER=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"
if exist "%COBRAQ_POPPLER%\pdftoppm.exe" set "PATH=%COBRAQ_POPPLER%;%PATH%"
set "PYTHONUTF8=1"
echo CobraQ: http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo Press Ctrl+C to stop the server.
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000 --host 127.0.0.1 --workers 1
exit /b %errorlevel%
