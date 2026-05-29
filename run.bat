@echo off
title CobraQ Server
cd /d "%~dp0backend"
echo Starting CobraQ Backend...
start "" "http://127.0.0.1:8000"
d:\CobraQ\venv2\Scripts\uvicorn.exe app.main:app --reload --port 8000 --host 0.0.0.0
