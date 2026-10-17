@echo off
title Mirror Cast - Screen Mirroring
cd /d "%~dp0"

echo ===================================================
echo       Mirror Cast - Mobile to PC Mirroring
echo ===================================================
echo.
echo Launching Mirror Cast Application...
echo.

python mirror_cast_app.py
if errorlevel 1 (
    echo.
    echo [Fallback] Trying with venv...
    venv\Scripts\python.exe mirror_cast_app.py
)

pause
