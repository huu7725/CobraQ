@echo off
chcp 65001 >nul
title CobraQ - Cai dat lan dau

echo.
echo  =============================================
echo   CobraQ - Cai dat lan dau
 echo  =============================================
echo.

:: 1) Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Chua cai Python hoac chua add PATH.
    echo  Tai: https://www.python.org/downloads/
    echo  Nho tick "Add Python to PATH".
    pause
    exit /b 1
)

:: 2) Tao virtualenv
if not exist "venv" (
    echo  [1/5] Tao virtual environment...
    python -m venv venv
) else (
    echo  [1/5] Da co virtual environment.
)

:: 3) Kich hoat venv + cai dependencies
call venv\Scripts\activate.bat
echo  [2/5] Cai dependencies...
pip install --upgrade pip -q --disable-pip-version-check
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo  [LOI] Cai dependencies that bai.
    pause
    exit /b 1
)

:: 4) Tao .env tu .env.example neu chua co
if not exist ".env" (
    if exist ".env.example" (
        echo  [3/5] Tao .env tu .env.example ...
        copy /Y ".env.example" ".env" >nul
        echo  [OK] Da tao .env. Hay sua DB_HOST/DB_USER/DB_PASSWORD neu can.
    ) else (
        echo  [3/5] Khong tim thay .env.example, bo qua.
    )
) else (
    echo  [3/5] Da co file .env.
)

:: 5) Kiem tra ket noi DB (SQLite/MySQL)
echo  [4/5] Kiem tra ket noi DB...
python -c "import os; from db import ping_db; eng=(os.getenv('DB_ENGINE','sqlite') or 'sqlite').lower(); ok=ping_db(); print(f'DB_ENGINE={eng}'); print('DB_OK' if ok else 'DB_FAIL'); import sys; sys.exit(0 if ok else 2)"
if errorlevel 2 (
    echo.
    echo  [CAN CHU Y] Chua ket noi duoc DB.
    echo  - Neu DB_ENGINE=sqlite: kiem tra quyen ghi file thu muc du an.
    echo  - Neu DB_ENGINE=mysql: kiem tra DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD va MySQL dang chay.
    echo.
) else (
    echo  [OK] Ket noi DB thanh cong.
)

:: 6) Kiem tra thu vien parse Word
echo  [5/5] Kiem tra thu vien parse...
python -c "import docx; print('python-docx OK')" >nul 2>&1
if errorlevel 1 (
    echo  [CAN CHU Y] Chua co python-docx. Dang cai them...
    pip install python-docx -q --disable-pip-version-check
)

echo.
echo  =============================================
echo   Cai dat xong.
echo   Chay ung dung bang: start.bat
echo  =============================================
echo.
pause
