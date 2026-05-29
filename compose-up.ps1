# One-command startup: KNIME Flask API (Windows host) + Docker stack (Airflow + n8n)
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$FlaskDir = Join-Path $ProjectRoot "flask_api"
$FlaskScript = Join-Path $FlaskDir "knime_flask_api.py"

function Test-FlaskApi {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8005/" -UseBasicParsing -TimeoutSec 3
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-DockerEngine {
    param([int]$TimeoutSeconds = 120)
    Write-Host "Waiting for Docker Desktop engine..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $null = docker info 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Docker engine is ready." -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
    }
    Write-Host "ERROR: Docker engine not reachable." -ForegroundColor Red
    Write-Host "  1. Open Docker Desktop and wait until it shows 'Engine running'." -ForegroundColor Red
    Write-Host "  2. If needed: Docker Desktop -> Troubleshoot -> Restart Docker Desktop." -ForegroundColor Red
    Write-Host "  3. Run this script again." -ForegroundColor Red
    return $false
}

Write-Host "Job Market Pipeline - starting services..." -ForegroundColor Cyan

if (-not (Wait-DockerEngine)) { exit 1 }

if (-not (Test-FlaskApi)) {
    Write-Host "Starting KNIME Flask API on port 8005 (background)..." -ForegroundColor Yellow
    $env:JOB_MARKET_PROJECT_DIR = $ProjectRoot
    $env:KNIME_BAT_FILE = Join-Path $FlaskDir "run_job_market_cleaning.bat"
    # Read KNIME_API_KEY from .env or default
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        $envVars = Get-Content $envFile | Where-Object { $_ -match '^[^#]' }
        foreach ($line in $envVars) {
            $parts = $line -split '=', 2
            if ($parts[0] -eq "KNIME_API_KEY") {
                $env:KNIME_API_KEY = $parts[1]
                break
            }
        }
    }
    if (-not $env:KNIME_API_KEY) {
        $env:KNIME_API_KEY = "job-market-secret-2026"
    }
    Start-Process -FilePath "python" `
        -ArgumentList $FlaskScript `
        -WorkingDirectory $FlaskDir `
        -WindowStyle Minimized `
        -PassThru | Out-Null

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-FlaskApi) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-FlaskApi)) {
        Write-Host "ERROR: Flask API did not start. Run manually: .\scripts\start_flask_api.ps1" -ForegroundColor Red
        exit 1
    }
    Write-Host "Flask API is ready at http://localhost:8005" -ForegroundColor Green
} else {
    Write-Host "Flask API already running on port 8005" -ForegroundColor Green
}

Set-Location $ProjectRoot
Write-Host 'Starting Docker Compose (Airflow and n8n)...' -ForegroundColor Cyan
docker compose up
