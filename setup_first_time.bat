@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.6 -m venv .venv
    if errorlevel 1 exit /b 1
) else (
    echo Virtual environment already exists.
)

for /f "tokens=2" %%v in ('.venv\Scripts\python.exe --version 2^>^&1') do set PYTHON_VERSION=%%v
echo Using Python %PYTHON_VERSION%
echo %PYTHON_VERSION% | findstr /B "3.6." >nul
if errorlevel 1 (
    echo This project must run on Python 3.6.x to match the server.
    echo Delete or rename .venv, install Python 3.6, then run this script again.
    exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade "pip<22" "setuptools<60" wheel
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install --timeout 120 --retries 5 -r requirements.txt
if errorlevel 1 exit /b 1

echo Applying database migrations...
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 exit /b 1

echo Running project checks...
".venv\Scripts\python.exe" manage.py check
if errorlevel 1 exit /b 1

echo First-time setup complete.
echo Start the app with run_payroll.bat
