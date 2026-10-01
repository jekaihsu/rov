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
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
if not exist "..\.runtime\android\platform-tools\adb.exe" (
    where adb >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Install Android Platform Tools and add its folder to PATH.
        echo Or run: python -X utf8 -m qysim.server --qirc --adb PATH_TO_ADB
        pause
        exit /b 1
    )
)
echo Connect Q-iRC by USB and select Local Data Transfer.
echo Keep FIFISH and RCTool closed while this simulator is running.
echo Open http://127.0.0.1:8080/?nointro in your browser.
echo Press Ctrl+C here to stop and reopen the original controller app.
python -X utf8 -m qysim.server --qirc --scenario open_water
pause
