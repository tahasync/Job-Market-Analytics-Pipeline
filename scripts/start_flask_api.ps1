$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FlaskDir = Join-Path $ProjectRoot "flask_api"
$FlaskScript = Join-Path $FlaskDir "knime_flask_api.py"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KNIME Flask API - Job Market Pipeline" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host "Port:    8005"
Write-Host ""
Write-Host "Endpoints:"
Write-Host "  GET  /"
Write-Host "  GET  /status"
Write-Host "  POST /run-knime"
Write-Host ""
Write-Host 'Test: Invoke-RestMethod -Uri "http://localhost:8005/run-knime" -Method POST -Headers @{"X-API-Key"="job-market-secret-2026"}'
Write-Host "========================================" -ForegroundColor Cyan

$env:JOB_MARKET_PROJECT_DIR = $ProjectRoot
$env:KNIME_BAT_FILE = Join-Path $FlaskDir "run_job_market_cleaning.bat"
# Read KNIME_API_KEY from .env or use default
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

Set-Location $FlaskDir
python -m pip install -q -r requirements.txt 2>$null
python $FlaskScript
