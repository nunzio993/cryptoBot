@echo off
echo Stopping CryptoBot services...

REM Close windows by name
taskkill /FI "WINDOWTITLE eq CryptoBot API*" /F 2>nul
taskkill /FI "WINDOWTITLE eq CryptoBot Scheduler*" /F 2>nul
taskkill /FI "WINDOWTITLE eq CryptoBot Frontend*" /F 2>nul

REM Stop database container
docker-compose stop db

echo.
echo All services stopped.
pause
