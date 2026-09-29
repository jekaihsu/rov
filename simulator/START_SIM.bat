@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and tick "Add Python to PATH".
    pause
    exit /b 1
)

python -c "import numpy, websockets" >nul 2>nul
if errorlevel 1 (
    echo [SETUP] Installing packages ^(first run only^)...
    python -m pip install -r requirements.txt
)

set SCENARIO=%1
if "%SCENARIO%"=="" set SCENARIO=open_water

start "" http://127.0.0.1:8080/
python -m qysim.server --scenario %SCENARIO%
pause
