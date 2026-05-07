@echo off
:: One-command setup for Windows
:: Usage: Double-click this file

cd /d "%~dp0"

echo ──────────────────────────────────────
echo   ShareData — Setup
echo ──────────────────────────────────────

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Download it from https://python.org ^(check "Add to PATH"^)
    pause
    exit /b 1
)

:: Create venv
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo.
echo ShareData is ready! Launching...
echo.
python main.py

pause
