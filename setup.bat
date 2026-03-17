@echo off
REM ==========================================
REM   Chatterbox TTS Setup Script for Windows
REM   Optimized for NVIDIA GPU (CUDA)
REM ==========================================

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo   Chatterbox TTS Setup for Windows
echo   NVIDIA GPU (CUDA) Support
echo ==========================================
echo.

REM Check if Python is available
echo [*] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Found Python %PYTHON_VERSION%

REM Check for NVIDIA GPU
echo.
echo [*] Checking for NVIDIA GPU...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [WARNING] nvidia-smi not found. CUDA may not be available.
    echo Make sure NVIDIA drivers are installed.
) else (
    echo [OK] NVIDIA GPU detected
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
)

REM Create virtual environment if it doesn't exist
echo.
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo.
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

REM Upgrade pip
echo.
echo [*] Upgrading pip...
python -m pip install --upgrade pip

REM Install PyTorch with CUDA support
echo.
echo [*] Installing PyTorch with CUDA 12.1 support...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo [WARNING] CUDA 12.1 installation failed, trying CUDA 11.8...
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
)

REM Verify CUDA is available
echo.
echo [*] Verifying CUDA support...
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}' if torch.cuda.is_available() else 'No CUDA')"

REM Install remaining dependencies
echo.
echo [*] Installing dependencies...
pip install -r requirements-windows.txt
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed. Trying with regular requirements...
    pip install -r requirements.txt
)

REM Create necessary directories
echo.
echo [*] Creating directories...
if not exist "outputs" mkdir outputs
if not exist "samples" mkdir samples
if not exist "voice reference" mkdir "voice reference"

REM Check if .env exists, if not create from template
if not exist ".env" (
    if exist "env.template" (
        echo.
        echo [*] Creating .env from template...
        copy env.template .env >nul
        echo [IMPORTANT] Please edit .env and add your HuggingFace token
    )
)

REM Verify installation
echo.
echo [*] Verifying Chatterbox installation...
python -c "from chatterbox.tts import ChatterboxTTS; print('[OK] Chatterbox TTS imported successfully')" 2>nul
if errorlevel 1 (
    echo [WARNING] Could not import Chatterbox TTS. You may need to download models first.
)

echo.
echo ==========================================
echo   Setup Complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Edit .env and add your HuggingFace token
echo 2. Run: run.bat
echo.
echo Or test installation: python scripts\test_installation.py
echo.
pause
