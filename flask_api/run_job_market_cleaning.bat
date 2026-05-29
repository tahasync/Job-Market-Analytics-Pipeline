@echo off
REM Airflow (Docker) -> Flask API -> this batch file -> KNIME

set "KNIME_EXE=C:\Program Files\KNIME\knime.exe"
set "WORKFLOW_FILE=C:\Users\Tahan\Desktop\Assignment 3\knime_workflow\job_market_cleaning\job_market_cleaning.knwf"
set "OUTPUT_CSV=C:\Users\Tahan\Desktop\Assignment 3\data\processed\clean_ai_ml_data_jobs.csv"
set "LOG_FILE=C:\Users\Tahan\Desktop\Assignment 3\flask_api\knime_run.log"

echo [%DATE% %TIME%] Starting KNIME batch execution... > "%LOG_FILE%"
echo Workflow: %WORKFLOW_FILE% >> "%LOG_FILE%"

if not exist "%KNIME_EXE%" (
    echo [ERROR] KNIME not found at %KNIME_EXE% >> "%LOG_FILE%"
    exit /b 1
)
if not exist "%WORKFLOW_FILE%" (
    echo [ERROR] Workflow not found at %WORKFLOW_FILE% >> "%LOG_FILE%"
    exit /b 1
)

if exist "%OUTPUT_CSV%" del /f /q "%OUTPUT_CSV%"

echo Launching KNIME batch... >> "%LOG_FILE%"

"%KNIME_EXE%" ^
    -nosave ^
    -consoleLog ^
    -nosplash ^
    -reset ^
    -application org.knime.product.KNIME_BATCH_APPLICATION ^
    -workflowFile="%WORKFLOW_FILE%" >> "%LOG_FILE%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
echo KNIME exit code: %EXIT_CODE% >> "%LOG_FILE%"

if exist "%OUTPUT_CSV%" (
    echo [SUCCESS] Output CSV created >> "%LOG_FILE%"
    exit /b 0
)

echo [ERROR] Output CSV not generated >> "%LOG_FILE%"
exit /b 1
