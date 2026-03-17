@echo off
REM =============================================================================
REM Chatterbox TTS - Auto-Update & Run Script for Windows
REM Checks for Git updates, pulls if available, and launches the Gradio app
REM =============================================================================

setlocal enabledelayedexpansion

echo.
echo ================================================================
echo      Chatterbox TTS - Auto-Update ^& Run (Windows)
echo ================================================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Default settings
set "NO_UPDATE=0"
set "SHARE=0"
set "NO_SHARE=1"
set "TARGET_PORT=7860"
set "EXTRA_ARGS="

REM Parse arguments
:parse_args
if "%~1"=="" goto :done_parsing
if /i "%~1"=="--no-update" set "NO_UPDATE=1" & shift & goto :parse_args
if /i "%~1"=="-n" set "NO_UPDATE=1" & shift & goto :parse_args
if /i "%~1"=="--share" set "SHARE=1" & set "NO_SHARE=0" & shift & goto :parse_args
if /i "%~1"=="-s" set "SHARE=1" & set "NO_SHARE=0" & shift & goto :parse_args
if /i "%~1"=="--no-share" set "NO_SHARE=1" & set "SHARE=0" & shift & goto :parse_args
if /i "%~1"=="-l" set "NO_SHARE=1" & set "SHARE=0" & shift & goto :parse_args
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
REM Handle --port=XXXX
echo %~1 | findstr /r "^--port=" >nul
if not errorlevel 1 (
    for /f "tokens=2 delims==" %%a in ("%~1") do set "TARGET_PORT=%%a"
    shift
    goto :parse_args
)
shift
goto :parse_args

:show_help
echo.
echo Usage: run.bat [OPTIONS]
echo.
echo Options:
echo   --share, -s        Create a public shareable link (default)
echo   --no-share, -l     Local network only, no public link
echo   --no-update, -n    Skip Git update check
echo   --port=PORT        Use custom port (default: 7860)
echo   --help, -h         Show this help message
echo.
echo Examples:
echo   run.bat                    # Run with public link
echo   run.bat --no-share         # Local network only
echo   run.bat --port=8080        # Use port 8080
echo   run.bat -n -l              # Quick start, local only
echo.
exit /b 0

:done_parsing

REM Build extra args for Python
if "%NO_SHARE%"=="1" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --no-share"
) else if "%SHARE%"=="1" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --share"
)
set "EXTRA_ARGS=!EXTRA_ARGS! --port=%TARGET_PORT%"

REM Git update check
if "%NO_UPDATE%"=="0" (
    git --version >nul 2>&1
    if not errorlevel 1 (
        if exist ".git" (
            echo [*] Checking for updates...
            git fetch origin >nul 2>&1
            
            for /f %%i in ('git rev-parse HEAD 2^>nul') do set "LOCAL_HASH=%%i"
            for /f %%i in ('git rev-parse @{u} 2^>nul') do set "REMOTE_HASH=%%i"
            
            if not "!LOCAL_HASH!"=="!REMOTE_HASH!" (
                echo [*] Updates available! Pulling latest changes...
                git pull origin
                
                REM Check if requirements changed
                git diff --name-only HEAD@{1} HEAD 2>nul | findstr /i "requirements" >nul
                if not errorlevel 1 (
                    echo [*] Requirements changed. Will update dependencies...
                    set "UPDATE_DEPS=1"
                )
            ) else (
                echo [OK] Already up to date!
            )
        ) else (
            echo [*] Not a Git repository. Skipping update check.
        )
    ) else (
        echo [*] Git not found. Skipping update check.
    )
)

REM Check for .env file
if not exist ".env" (
    echo [WARNING] .env file not found!
    if exist "env.template" (
        echo [*] Creating .env from env.template...
        copy env.template .env >nul
        echo [OK] Created .env file. Please edit it with your API keys.
        notepad .env
    ) else (
        echo [ERROR] env.template not found. Please create .env manually.
    )
)

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARNING] Virtual environment not found. Running setup first...
    if exist "setup.bat" (
        call setup.bat
        call venv\Scripts\activate.bat
    ) else (
        echo [ERROR] setup.bat not found. Please run setup manually.
        pause
        exit /b 1
    )
)

REM Update dependencies if requirements changed
if "%UPDATE_DEPS%"=="1" (
    echo [*] Installing updated dependencies...
    pip install -r requirements-windows.txt -q
    echo [OK] Dependencies updated
)

REM Kill any existing process on target port
echo [*] Checking for existing process on port %TARGET_PORT%...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":%TARGET_PORT%" ^| findstr "LISTENING"') do (
    if not "%%a"=="" (
        echo [*] Stopping existing server [PID: %%a]...
        taskkill /F /PID %%a >nul 2>&1
    )
)

REM Run the app
echo.
echo [*] Starting Chatterbox TTS...
if "%NO_SHARE%"=="1" (
    echo    Mode: Local network only [Port: %TARGET_PORT%]
) else (
    echo    Mode: Public sharing enabled [Port: %TARGET_PORT%]
)
echo ================================================================
echo.

python launch.py %EXTRA_ARGS%

pause
