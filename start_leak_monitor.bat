@echo off
title Leak Monitor - Starting All Services
color 0A

echo ============================================
echo   LEAK MONITOR - STARTING ALL SERVICES
echo ============================================
echo.

:: ─────────────────────────────────────────
:: STEP 1 - Start Memurai (Redis)
:: ─────────────────────────────────────────
echo [1/3] Starting Memurai (Redis)...
net start memurai >nul 2>&1
memurai-cli ping >nul 2>&1
if %errorlevel% == 0 (
    echo        Memurai is RUNNING
) else (
    echo        Memurai FAILED - check if it is installed
    pause
    exit
)
echo.

:: ─────────────────────────────────────────
:: STEP 2 - Start Django with Daphne
:: ─────────────────────────────────────────
echo [2/3] Starting Django (Daphne)...
start "Django - Daphne" cmd /k "cd C:\leak_monitor_backend && venv\Scripts\activate && python -m daphne -p 8000 core.asgi:application"
echo        Django window opened
echo        Waiting for Django to fully start...
timeout /t 4 /nobreak >nul
echo.

:: ─────────────────────────────────────────
:: STEP 3 - Start Ngrok
:: ─────────────────────────────────────────
echo [3/3] Starting Ngrok tunnel...
start "Ngrok - Tunnel" cmd /k "cd C:\Users\kamukama\Downloads\ngrok-v3-stable-windows-amd64 && ngrok http 8000"
echo        Ngrok window opened
echo        Waiting for Ngrok to get URL...
timeout /t 3 /nobreak >nul
echo.

:: ─────────────────────────────────────────
:: DONE
:: ─────────────────────────────────────────
echo ============================================
echo   ALL SERVICES STARTED SUCCESSFULLY
echo ============================================
echo.
echo   What to do next:
echo   1. Check the Ngrok window for your public URL
echo   2. Copy the URL that looks like:
echo      https://xxxx-xxxx.ngrok-free.dev
echo   3. Send this to hardware guy as:
echo      wss://xxxx-xxxx.ngrok-free.dev/ws/sensors/
echo   4. Open your Flutter app
echo.
echo   To STOP everything just close all the windows.
echo.
echo ============================================
pause