@echo off
chcp 65001 >nul
title CobraQ - Khoi dong server

echo.
echo  =============================================
echo   CobraQ - He thong on tap trac nghiem
echo  =============================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Chua cai Python!
    echo  Tai Python tai: https://www.python.org/downloads/
    echo  Nho tick "Add Python to PATH" khi cai.
    pause
    exit /b 1
)

:: Tao virtual environment neu chua co
if not exist "venv" (
    echo  [1/4] Tao moi truong ao Python...
    python -m venv venv
)

:: Kich hoat venv
call venv\Scripts\activate.bat

:: Cai thu vien
echo  [2/4] Kiem tra va cai thu vien...
pip install -r requirements.txt -q --disable-pip-version-check

:: Kiem tra file main
if not exist "main_updated.py" (
    echo.
    echo  [LOI] Khong tim thay file main_updated.py
    echo  Hay dat file nay cung thu muc voi start.bat
    pause
    exit /b 1
)

:: Khoi dong frontend http server (port 5500)
echo  [3/4] Khoi dong web...
start "CobraQ-Frontend" cmd /c "cd /d %~dp0 && python -m http.server 5500 --bind 127.0.0.1"

:: Mo trinh duyet
echo  [4/4] Khoi dong backend...
echo.
echo  =============================================
echo   Backend: http://127.0.0.1:8000
echo   Frontend: http://127.0.0.1:5500/CobraQ_v3.html
echo   Nhan CTRL+C de dung backend
echo  =============================================
echo.

start "" "http://127.0.0.1:5500/CobraQ_v3.html"

:: Chay backend
uvicorn main_updated:app --host 127.0.0.1 --port 8000

pause
