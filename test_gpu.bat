@echo off
REM =============================================================================
REM Quick GPU Test Script for Windows
REM Verifies CUDA/PyTorch setup for your RTX 4090
REM =============================================================================

echo.
echo ==========================================
echo   GPU Test for Chatterbox TTS
echo ==========================================
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [*] Checking NVIDIA GPU...
nvidia-smi
echo.

echo [*] Testing PyTorch CUDA support...
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}' if torch.cuda.is_available() else 'CUDA not available'); print(f'GPU: {torch.cuda.get_device_name(0)}' if torch.cuda.is_available() else ''); print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB' if torch.cuda.is_available() else '')"

echo.
echo [*] Testing Chatterbox import...
python -c "from chatterbox.tts import ChatterboxTTS; print('[OK] Chatterbox TTS ready!')" 2>nul
if errorlevel 1 (
    echo [WARNING] Chatterbox not yet installed or models not downloaded.
)

echo.
pause
