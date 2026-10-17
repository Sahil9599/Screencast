@echo off
title Push Mirror Cast to GitHub
cd /d "%~dp0"

echo ====================================================
echo        Pushing Mirror Cast to GitHub
echo ====================================================
echo.

set GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe

if not exist "%GIT_EXE%" (
    set GIT_EXE=git
)

echo Remote URL: https://github.com/Sahil9599/Screencast.git
echo Branch: main
echo.

"%GIT_EXE%" remote set-url origin https://github.com/Sahil9599/Screencast.git
"%GIT_EXE%" push -u origin main

if errorlevel 1 (
    echo.
    echo ====================================================
    echo [NOTE] Agar authentication maang raha hai:
    echo 1. Browser me GitHub login karein.
    echo 2. Ya fir GitHub Personal Access Token use karein.
    echo ====================================================
) else (
    echo.
    echo [SUCCESS] Code successfully pushed to GitHub!
)

pause
