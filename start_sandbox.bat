@echo off
setlocal
cd /d "%~dp0"
call setup_sandbox.bat
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"
set "COBRAQ_POPPLER=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"
if exist "%COBRAQ_POPPLER%\pdftoppm.exe" set "PATH=%COBRAQ_POPPLER%;%PATH%"
".venv\Scripts\python.exe" tools\sandbox.py serve
exit /b %errorlevel%
