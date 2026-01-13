# CryptoBot - Stop Script (PowerShell)
Write-Host "Stopping CryptoBot services..." -ForegroundColor Yellow

# Kill Python processes for API and Scheduler
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force

# Kill Node processes for Frontend
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop database
Set-Location "D:\cryptoBot"
docker-compose stop db

Write-Host ""
Write-Host "All services stopped." -ForegroundColor Green
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
