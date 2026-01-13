@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   CryptoBot - Backend Services
echo ========================================
echo.

cd /d D:\cryptoBot

echo [1/3] Starting API Backend (port 8001)...
start "CryptoBot API" cmd /k "cd /d D:\cryptoBot && set PYTHONPATH=D:\cryptoBot && python -m uvicorn api.main:app --reload --port 8001"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Scheduler...
start "CryptoBot Scheduler" cmd /k "cd /d D:\cryptoBot && set PYTHONPATH=D:\cryptoBot && python src/core_and_scheduler.py"

timeout /t 2 /nobreak >nul

echo [3/3] Starting Telegram Bot...
start "CryptoBot Telegram" cmd /k "cd /d D:\cryptoBot && set PYTHONPATH=D:\cryptoBot && python telegram_bot.py"

echo.
echo ========================================
echo   Backend services started!
echo ========================================
echo.
echo   API:       http://localhost:8001
echo   Scheduler: Running in background
echo   Telegram:  Bot listening for /link commands
echo.
echo   Close all windows to stop services.
echo.
pause
