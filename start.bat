@echo off
cd /d "%~dp0"

echo Starting backend server (run.py)...
start "Renderfarm-Server" cmd /k python run.py
timeout /t 3 /nobreak >nul
echo Starting worker node (worker.py)...
start "Renderfarm-Worker" cmd /k python worker.py

echo All processes started.
