@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   CryptoBot - Starting Services
echo ========================================
echo.

cd /d D:\cryptoBot

echo [1/4] Starting Database...
docker-compose up -d db

echo Waiting for database...
:wait_db
docker exec binance-db pg_isready -U admin -d botdb >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_db
)
echo Database ready!

set PYTHONPATH=D:\cryptoBot

echo [2/4] Starting API Backend...
start /b cmd /c "python -m uvicorn api.main:app --port 8001 2>&1"

timeout /t 3 /nobreak >nul

echo [3/4] Starting Scheduler...
start /b cmd /c "python src/core_and_scheduler.py 2>&1"

echo [4/4] Starting Frontend...
cd frontend
start /b cmd /c "npm run dev -- -p 3001 2>&1"
cd ..

echo.
echo ========================================
echo   All services started!
echo ========================================
echo.
echo   API:       http://localhost:8001
echo   Frontend:  http://localhost:3001
echo.
echo   Press CTRL+C to stop all services
echo.

:loop
timeout /t 5 /nobreak >nul
goto loop
