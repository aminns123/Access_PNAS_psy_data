@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: PsyView's local .venv was not found.
    echo Start PsyView once with run_psyview.bat, then run this Stage-2 installer again.
    pause
    exit /b 1
)

echo Installing PsyView custom-equation fitting Stage 2...
".venv\Scripts\python.exe" apply_fit_function_stage2.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Stage-2 installation did not complete.
    echo Live target files were restored automatically.
    pause
    exit /b %RC%
)

echo.
echo Done. Start PsyView normally with run_psyview.bat
pause
