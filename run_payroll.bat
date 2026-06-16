@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run setup_first_time.bat first.
    exit /b 1
)

for /f "tokens=2" %%v in ('.venv\Scripts\python.exe --version 2^>^&1') do set PYTHON_VERSION=%%v
echo Using Python %PYTHON_VERSION%
echo %PYTHON_VERSION% | findstr /B "3.6." >nul
if errorlevel 1 (
    echo This project must run on Python 3.6.x to match the server.
    echo Recreate .venv with Python 3.6 before starting the app.
    exit /b 1
)

netstat -ano | findstr /R /C:":8004 .*LISTENING" >nul
if not errorlevel 1 (
    echo Payroll system already appears to be running at http://127.0.0.1:8004/
    exit /b 0
)

echo Starting payroll system at http://127.0.0.1:8004/
set DATABASE_URL=
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8004
