@echo off
echo Dang tat server CobraQ...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo Server da tat!
timeout /t 2 >nul
