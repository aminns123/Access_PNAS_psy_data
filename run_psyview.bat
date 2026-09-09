@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title PsyView Launcher

REM ============================================================
REM PsyView Windows Launcher
REM ============================================================
REM Minimum supported Python version for this project:
set "MIN_MAJOR=3"
set "MIN_MINOR=12"

echo.
echo ==========================================
echo              PsyView Launcher
echo ==========================================
echo Project: %CD%
echo Required Python: %MIN_MAJOR%.%MIN_MINOR% or newer
echo.

REM ------------------------------------------------------------
REM Basic project check
REM ------------------------------------------------------------
if not exist "pyproject.toml" (
    echo ERROR: pyproject.toml was not found.
    echo.
    echo Put this launcher in the root of the PsyView project,
    echo alongside pyproject.toml, and run it again.
    echo.
    pause
    exit /b 1
)

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

REM ------------------------------------------------------------
REM 1. Re-use an existing local .venv if it is compatible.
REM ------------------------------------------------------------
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_MAJOR%,%MIN_MINOR%) else 1)" >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%V in ('"%VENV_PYTHON%" --version 2^>^&1') do set "VENV_VERSION=%%V"
        echo [PsyView] Existing environment found: !VENV_VERSION!
        goto :venv_ready
    )

    echo [PsyView] Existing .venv uses an older/incompatible Python.
    echo [PsyView] A compatible system Python will be searched for.
    echo.
)

REM ------------------------------------------------------------
REM 2. Search the computer for Python.
REM
REM We distinguish:
REM   A) compatible Python found -> continue automatically
REM   B) Python exists but is too old -> explain that an update is needed
REM   C) no Python detected -> explain that Python must be installed
REM ------------------------------------------------------------
set "PY_CMD="
set "PY_ARGS="
set "FOUND_ANY_PYTHON=0"
set "FOUND_VERSION="

REM ----- Preferred route: Windows Python Launcher ("py") -----
where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_ANY_PYTHON=1"
        for /f "delims=" %%V in ('py -3 --version 2^>^&1') do set "FOUND_VERSION=%%V"

        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_MAJOR%,%MIN_MINOR%) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=py"
            set "PY_ARGS=-3"
            goto :python_found
        )
    )
)

REM ----- Fallback: "python" on PATH -----
where python >nul 2>&1
if not errorlevel 1 (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_ANY_PYTHON=1"
        for /f "delims=" %%V in ('python --version 2^>^&1') do set "FOUND_VERSION=%%V"

        python -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_MAJOR%,%MIN_MINOR%) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=python"
            set "PY_ARGS="
            goto :python_found
        )
    )
)

REM ----- Fallback: "python3" on PATH -----
where python3 >nul 2>&1
if not errorlevel 1 (
    python3 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_ANY_PYTHON=1"
        for /f "delims=" %%V in ('python3 --version 2^>^&1') do set "FOUND_VERSION=%%V"

        python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (%MIN_MAJOR%,%MIN_MINOR%) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=python3"
            set "PY_ARGS="
            goto :python_found
        )
    )
)

REM ------------------------------------------------------------
REM No compatible Python was found.
REM Report whether Python is absent or merely too old.
REM ------------------------------------------------------------
echo.
if "%FOUND_ANY_PYTHON%"=="1" (
    echo ERROR: Python is installed, but no compatible version was found.
    if defined FOUND_VERSION echo Detected version: %FOUND_VERSION%
    echo.
    echo PsyView requires Python %MIN_MAJOR%.%MIN_MINOR% or newer.
    echo Please install a current Python 3 release, then run this file again.
) else (
    echo ERROR: Python could not be detected on this computer.
    echo.
    echo PsyView requires Python %MIN_MAJOR%.%MIN_MINOR% or newer.
    echo Please install Python, then run this file again.
)

echo.
where py >nul 2>&1
if not errorlevel 1 (
    echo Installed versions reported by the Windows Python Launcher:
    py --list 2>nul
    echo.
)

echo Recommended Windows installation options:
echo.
echo   1. Python website:
echo      https://www.python.org/downloads/windows/
echo.
echo   2. Windows Package Manager:
echo      winget install Python.Python.3.13
echo.
echo After Python is installed or updated, double-click this file again.
echo PsyView will take care of the local environment and package dependencies.
echo.
pause
exit /b 1

:python_found
for /f "delims=" %%V in ('%PY_CMD% %PY_ARGS% --version 2^>^&1') do set "SYSTEM_PY_VERSION=%%V"
echo [PsyView] Compatible Python found: !SYSTEM_PY_VERSION!

REM Preserve incompatible environments; create with the selected Python.
%PY_CMD% %PY_ARGS% "scripts\launcher_setup.py" --create
if errorlevel 1 (
    echo ERROR: venv creation failed. See the specific error above.
    pause
    exit /b 1
)

:venv_ready
REM No pip process or network access occurs when the successful hash matches.
"%VENV_PYTHON%" "scripts\launcher_setup.py"
if errorlevel 1 (
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 4. Launch PsyView.
REM ------------------------------------------------------------
echo.
echo [PsyView] Starting PsyView
echo.

"%VENV_PYTHON%" -m psyview %*
set "APP_EXIT=!ERRORLEVEL!"

if not "%APP_EXIT%"=="0" (
    echo.
    echo ERROR: PsyView runtime failure, exit code %APP_EXIT%.
    echo Review the messages above for details.
    echo.
    pause
    exit /b %APP_EXIT%
)

echo.
echo PsyView closed normally.
exit /b 0
