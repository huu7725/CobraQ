@echo off
setlocal
cd /d "%~dp0"

".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if not errorlevel 1 goto install

py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    py -3.12 -m venv .venv
    goto created
)
python -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))" >nul 2>&1
if not errorlevel 1 (
    python -m venv .venv
    goto created
)
set "COBRAQ_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%COBRAQ_PYTHON%" (
    "%COBRAQ_PYTHON%" -m venv .venv
    goto created
)
echo [ERROR] Python 3.12 is required.
echo Install Python from https://www.python.org/downloads/windows/ and rerun setup.bat.
exit /b 1

:created
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" exit /b 1

:install
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
set "COBRAQ_REQUIREMENTS=requirements.txt"
if exist "requirements-lock.txt" set "COBRAQ_REQUIREMENTS=requirements-lock.txt"
".venv\Scripts\python.exe" -m pip install -r "%COBRAQ_REQUIREMENTS%"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 exit /b 1
if not exist "backend\.env" copy /y "backend\.env.example" "backend\.env" >nul
echo Setup complete. Run start.bat to start CobraQ.
