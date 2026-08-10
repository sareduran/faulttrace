@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo FaultTrace Python environment was not found.
    echo Expected: %CD%\.venv\Scripts\python.exe
    pause
    exit /b 1
)

netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if errorlevel 1 (
    start "FaultTrace Server" /min ".venv\Scripts\python.exe" -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=8501
    timeout /t 3 /nobreak >nul
)

start "" "http://127.0.0.1:8501"
