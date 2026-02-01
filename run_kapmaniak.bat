@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"

if exist requirements.txt (
    pip install -r requirements.txt
) else (
    pip install PySide6 requests
)

python app.py
set exit_code=%errorlevel%

echo.
echo Exit code: %exit_code%
pause
exit /b %exit_code%
