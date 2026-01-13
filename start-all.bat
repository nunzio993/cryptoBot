@echo off
echo ========================================
echo   CryptoBot - Startup Script
echo ========================================
echo.

REM Start Database
echo [1/4] Starting Database...
docker-compose up -d db
timeout /t 3 /nobreak > nul

REM Start API Backend
echo [2/4] Starting API Backend...
start "CryptoBot API" cmd /k "cd /d D:\cryptoBot && python -m uvicorn api.main:app --reload --port 8001"
timeout /t 2 /nobreak > nul

REM Start Scheduler
echo [3/4] Starting Scheduler...
start "CryptoBot Scheduler" cmd /k "cd /d D:\cryptoBot && python src/core_and_scheduler.py"
timeout /t 2 /nobreak > nul

REM Start Frontend
echo [4/4] Starting Frontend...
start "CryptoBot Frontend" cmd /k "cd /d D:\cryptoBot\frontend && npm run dev -- -p 3001"

echo.
echo ========================================
echo   All services started!
echo ========================================
echo.
echo   API:       http://localhost:8001
echo   Frontend:  http://localhost:3001
echo.
echo   Press any key to exit this window...
pause > nul
