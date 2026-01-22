@echo off
REM Simple Photo Meta - Run Script (Windows)
REM Starts the local FastAPI server and opens the browser
REM NO external dependencies beyond Python

setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set BACKEND_DIR=%PROJECT_DIR%\backend

echo === Simple Photo Meta ===
echo.

REM Check if virtual environment exists
if not exist "%PROJECT_DIR%\.venv" (
    echo Creating virtual environment...
    python -m venv "%PROJECT_DIR%\.venv"
)

REM Activate virtual environment
call "%PROJECT_DIR%\.venv\Scripts\activate.bat"

REM Install backend dependencies
echo Installing dependencies...
pip install -q fastapi uvicorn pillow pillow-heif appdirs

REM Build C++ bindings if needed
python -c "from simple_photo_meta.exiv2bind import Exiv2Bind" 2>nul
if errorlevel 1 (
    echo Building C++ metadata bindings...
    cd "%PROJECT_DIR%"
    pip install -e .
)

REM Set port
if "%PORT%"=="" set PORT=8080

echo.
echo =========================================
echo   Simple Photo Meta
echo   Open: http://127.0.0.1:%PORT%
echo   Press Ctrl+C to stop
echo =========================================
echo.

REM Open browser
start "" "http://127.0.0.1:%PORT%"

REM Run the development server with uvicorn
cd "%BACKEND_DIR%"
python -m uvicorn main:app --host 127.0.0.1 --port %PORT%

endlocal
