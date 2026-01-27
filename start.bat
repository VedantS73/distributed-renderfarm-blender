@echo off
cd /d "%~dp0"

echo Clearing jobs and render_output...
if exist jobs rmdir /s /q jobs
if exist render_output rmdir /s /q render_output
mkdir jobs
mkdir render_output

echo Starting backend server...
start "Renderfarm-Server" cmd /k python run.py

timeout /t 3 /nobreak >nul

echo Starting worker node...
start "Renderfarm-Worker" cmd /k python worker.py

echo All processes started.
