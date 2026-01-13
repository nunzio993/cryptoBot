# CryptoBot - Unified Service Manager
# Run with: powershell -ExecutionPolicy Bypass -File start-all.ps1

param(
    [switch]$Stop
)

$ProjectPath = "D:\cryptoBot"
$PidFile = "$ProjectPath\.pids"

function Wait-ForDatabase {
    Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        $attempt++
        try {
            $result = docker exec binance-db pg_isready -U admin -d botdb 2>&1
            if ($result -like "*accepting connections*") {
                Write-Host "Database is ready!" -ForegroundColor Green
                return $true
            }
        }
        catch {}
        
        Write-Host "  Attempt $attempt/$maxAttempts - waiting..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
    
    Write-Host "Database failed to start!" -ForegroundColor Red
    return $false
}

function Start-Services {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   CryptoBot - Starting Services" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    Set-Location $ProjectPath

    # Start Database
    Write-Host "[1/4] Starting Database..." -ForegroundColor Yellow
    docker-compose up -d db
    
    # Wait for database to be ready
    if (-not (Wait-ForDatabase)) {
        Write-Host "Failed to start database. Exiting." -ForegroundColor Red
        return
    }

    # Start API Backend as background job
    Write-Host "[2/4] Starting API Backend (port 8001)..." -ForegroundColor Yellow
    $apiJob = Start-Job -ScriptBlock {
        Set-Location $using:ProjectPath
        $env:PYTHONPATH = $using:ProjectPath
        python -m uvicorn api.main:app --port 8001 2>&1
    }

    Start-Sleep -Seconds 3

    # Start Scheduler as background job
    Write-Host "[3/4] Starting Scheduler..." -ForegroundColor Yellow
    $schedulerJob = Start-Job -ScriptBlock {
        Set-Location $using:ProjectPath
        $env:PYTHONPATH = $using:ProjectPath
        python src/core_and_scheduler.py 2>&1
    }

    # Start Frontend as background job
    Write-Host "[4/4] Starting Frontend (port 3001)..." -ForegroundColor Yellow
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location "$using:ProjectPath\frontend"
        npm run dev -- -p 3001 2>&1
    }

    # Save job IDs
    "$($apiJob.Id),$($schedulerJob.Id),$($frontendJob.Id)" | Out-File $PidFile

    Start-Sleep -Seconds 3

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   All services started!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "   API:       http://localhost:8001" -ForegroundColor White
    Write-Host "   Frontend:  http://localhost:3001" -ForegroundColor White
    Write-Host ""
    Write-Host "   Press CTRL+C to stop all services" -ForegroundColor Gray
    Write-Host ""

    # Monitor jobs and show output
    try {
        while ($true) {
            $apiOutput = Receive-Job -Job $apiJob -ErrorAction SilentlyContinue
            $schedulerOutput = Receive-Job -Job $schedulerJob -ErrorAction SilentlyContinue
            $frontendOutput = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue

            if ($apiOutput) { 
                $apiOutput | ForEach-Object { Write-Host "[API] $_" -ForegroundColor Blue }
            }
            if ($schedulerOutput) { 
                $schedulerOutput | ForEach-Object { Write-Host "[SCH] $_" -ForegroundColor Magenta }
            }
            if ($frontendOutput) { 
                $frontendOutput | ForEach-Object { Write-Host "[FE]  $_" -ForegroundColor Cyan }
            }

            Start-Sleep -Milliseconds 500
        }
    }
    finally {
        Stop-Services
    }
}

function Stop-Services {
    Write-Host ""
    Write-Host "Stopping all services..." -ForegroundColor Yellow

    # Stop all jobs
    Get-Job | Stop-Job -PassThru | Remove-Job -Force -ErrorAction SilentlyContinue

    # Stop database
    Set-Location $ProjectPath
    docker-compose stop db 2>$null

    # Remove pid file
    if (Test-Path $PidFile) { Remove-Item $PidFile }

    Write-Host "All services stopped." -ForegroundColor Green
}

# Main
if ($Stop) {
    Stop-Services
}
else {
    Start-Services
}
