@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Could not find .venv Python or the Windows py launcher.
        pause
        exit /b 1
    )
    set "PYTHON=py"
)

echo Installing PsyView stage-1 fit-function interface...
"%PYTHON%" apply_fit_function_ui_stage1.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Installation did not complete. Existing modified source files were restored.
    pause
    exit /b %RC%
)

echo.
echo Done.
echo Start PsyView normally with run_psyview.bat
pause
