# =============================================================================
#  SurAIverse TTS Studio — Windows Installer
#  by Suresh Pydikondala  |  youtube.com/@suraiverse
# =============================================================================

# Use Continue so native cmdlet errors don't bypass our branded error handling
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "SurAIverse TTS Studio — Installer"

try { $Host.UI.RawUI.BufferSize  = New-Object System.Management.Automation.Host.Size(72, 3000) } catch {}
try { $Host.UI.RawUI.WindowSize  = New-Object System.Management.Automation.Host.Size(72, 48)  } catch {}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

# ── Colour helpers ────────────────────────────────────────────────────────────
function Cyan   { param($t) Write-Host $t -ForegroundColor Cyan    -NoNewline }
function Yellow { param($t) Write-Host $t -ForegroundColor Yellow  -NoNewline }
function Green  { param($t) Write-Host $t -ForegroundColor Green   -NoNewline }
function Red    { param($t) Write-Host $t -ForegroundColor Red     -NoNewline }
function Gray   { param($t) Write-Host $t -ForegroundColor Gray    -NoNewline }
function White  { param($t) Write-Host $t -ForegroundColor White   -NoNewline }
function NL     { Write-Host "" }

function OK   { param($msg) Green "  [+] "; White "$msg"; NL }
function WARN  { param($msg) Yellow "  [!] "; White "$msg"; NL }
function ERR  { param($msg) Red   "  [x] "; White "$msg"; NL }
function INFO { param($msg) Cyan  "  >>  "; Gray  "$msg"; NL }

# ── Banner ────────────────────────────────────────────────────────────────────
function Show-Banner {
    Clear-Host
    NL
    Cyan  "  ╔══════════════════════════════════════════════════════════════╗"; NL
    Cyan  "  ║"; White "                                                            "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ███████╗██╗   ██╗██████╗  █████╗ ██╗██╗   ██╗███████╗ "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ██╔════╝██║   ██║██╔══██╗██╔══██╗██║██║   ██║██╔════╝ "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ███████╗██║   ██║██████╔╝███████║██║██║   ██║█████╗   "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ╚════██║██║   ██║██╔══██╗██╔══██║██║╚██╗ ██╔╝██╔══╝   "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ███████║╚██████╔╝██║  ██║██║  ██║██║ ╚████╔╝ ███████╗ "; Cyan "║"; NL
    Cyan  "  ║"; Cyan  "    ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝ "; Cyan "║"; NL
    Cyan  "  ║"; White "                                                            "; Cyan "║"; NL
    Cyan  "  ║"; Yellow "                    TTS  Studio                             "; Cyan "║"; NL
    Cyan  "  ║"; Gray  "               by Suresh Pydikondala                        "; Cyan "║"; NL
    Cyan  "  ║"; White "                                                            "; Cyan "║"; NL
    Cyan  "  ╠══════════════════════════════════════════════════════════════╣"; NL
    Cyan  "  ║"; NL
    Cyan  "  ║"; Yellow "   ▶  YouTube  "; White "youtube.com/@suraiverse                       "; Cyan "║"; NL
    Cyan  "  ║"; Yellow "   ★  If this helps you, please SUBSCRIBE!                 "; Cyan "║"; NL
    Cyan  "  ║"; White "                                                            "; Cyan "║"; NL
    Cyan  "  ╠══════════════════════════════════════════════════════════════╣"; NL
    Cyan  "  ║"; Gray  "  Tested on: Windows 11  |  NVIDIA RTX 4090  |  24 GB VRAM "; Cyan "║"; NL
    Cyan  "  ║"; Gray  "  Inference speed will vary depending on your hardware.     "; Cyan "║"; NL
    Cyan  "  ╚══════════════════════════════════════════════════════════════╝"; NL
    NL
}

# ── Progress bar ──────────────────────────────────────────────────────────────
function Show-Progress {
    param([int]$Step, [int]$Total, [string]$Label)

    $pct     = [int](($Step / $Total) * 100)
    $filled  = [int]($pct / 5)          # out of 20 blocks
    $empty   = 20 - $filled
    $bar     = ("█" * $filled) + ("░" * $empty)

    NL
    Cyan  "  ┌─ Step $Step of $Total "; Gray "─────────────────────────────────────────────┐"; NL
    Cyan  "  │ "; Yellow "$bar "; White "$pct%"; NL
    Cyan  "  │ "; White "$Label"; NL
    Cyan  "  └─────────────────────────────────────────────────────────────┘"; NL
    NL
}

# ── Fatal exit ────────────────────────────────────────────────────────────────
function Fail {
    param([string]$Reason)
    NL
    Red "  ╔══════════════════════════════════════╗"; NL
    Red "  ║        Installation Failed           ║"; NL
    Red "  ╚══════════════════════════════════════╝"; NL
    NL
    ERR $Reason
    NL
    Write-Host "  Press Enter to exit..." -ForegroundColor Gray
    Read-Host | Out-Null
    exit 1
}

# =============================================================================
#  START
# =============================================================================
Show-Banner
Write-Host "  Starting installation in: " -ForegroundColor Gray -NoNewline
Write-Host $ROOT -ForegroundColor Cyan
NL
Write-Host "  Press Enter to begin, or Ctrl+C to cancel." -ForegroundColor Gray
Read-Host | Out-Null

# =============================================================================
#  STEP 1 — Python
# =============================================================================
Show-Banner
Show-Progress 1 7 "Checking system requirements..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $verStr = & $cmd --version 2>&1
        if ($verStr -match "Python (\d+)\.(\d+)") {
            $maj = [int]$Matches[1]; $min = [int]$Matches[2]
            if ($maj -eq 3 -and $min -ge 10) {
                $pythonCmd = $cmd
                OK "Python $maj.$min found  ($cmd)"
                break
            } else {
                WARN "Found Python $maj.$min — version 3.10+ required."
            }
        }
    } catch {}
}

if ($null -eq $pythonCmd) {
    NL
    ERR "Python 3.10 or newer was not found."
    INFO "Download from:  https://www.python.org/downloads/"
    INFO "Recommended:    Python 3.11"
    INFO "During install, tick 'Add Python to PATH'."
    NL
    Fail "Python not found. Install it and re-run INSTALL.bat."
}

# NVIDIA GPU
INFO "Checking NVIDIA GPU..."
try {
    $gpuRaw = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>&1
    if ($LASTEXITCODE -eq 0 -and $gpuRaw) {
        OK "GPU detected: $gpuRaw"
    } else { throw }
} catch {
    WARN "nvidia-smi not found — CUDA detection skipped."
    INFO "Make sure NVIDIA drivers are installed:"
    INFO "https://www.nvidia.com/en-us/drivers/"
}

# =============================================================================
#  STEP 2 — Virtual environment
# =============================================================================
Show-Banner
Show-Progress 2 7 "Creating virtual environment..."

$venvPath = Join-Path $ROOT "venv"
if (Test-Path (Join-Path $venvPath "Scripts\python.exe")) {
    OK "Virtual environment already exists — skipping creation."
} else {
    INFO "Running: $pythonCmd -m venv venv"
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { Fail "Could not create virtual environment." }
    OK "Virtual environment created."
}

$pip    = Join-Path $venvPath "Scripts\pip.exe"
$python = Join-Path $venvPath "Scripts\python.exe"

# =============================================================================
#  STEP 3 — Pip upgrade
# =============================================================================
Show-Banner
Show-Progress 3 7 "Upgrading pip..."

INFO "Upgrading pip..."
& $pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { WARN "pip upgrade failed — continuing anyway." }
else { OK "pip upgraded to latest version." }

# =============================================================================
#  STEP 4 — PyTorch + CUDA
# =============================================================================
Show-Banner
Show-Progress 4 7 "Installing PyTorch with CUDA support..."

WARN "This step downloads ~2.5 GB.  Please be patient — do not close this window."
NL

$torchOk = $false
$cudaVersions = @(
    @{ Label = "CUDA 12.1"; Url = "https://download.pytorch.org/whl/cu121" },
    @{ Label = "CUDA 11.8"; Url = "https://download.pytorch.org/whl/cu118" },
    @{ Label = "CUDA 12.4"; Url = "https://download.pytorch.org/whl/cu124" }
)

foreach ($cv in $cudaVersions) {
    INFO "Trying PyTorch with $($cv.Label)..."
    & $pip install torch torchaudio --index-url $cv.Url
    if ($LASTEXITCODE -eq 0) {
        OK "PyTorch installed with $($cv.Label)."
        $torchOk = $true
        break
    }
    WARN "$($cv.Label) failed — trying next version..."
}

if (-not $torchOk) {
    WARN "All CUDA versions failed. Installing CPU-only PyTorch..."
    & $pip install torch torchaudio
    if ($LASTEXITCODE -ne 0) { Fail "PyTorch installation failed." }
    WARN "Installed CPU-only PyTorch. Generation will be slower without a GPU."
}

# Quick CUDA check
INFO "Verifying PyTorch CUDA..."
$cudaResult = & $python -c @"
import torch
cuda = torch.cuda.is_available()
if cuda:
    print('CUDA OK - ' + torch.cuda.get_device_name(0) + ' | VRAM: ' + str(round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)) + ' GB')
else:
    print('CUDA not available - running on CPU')
"@ 2>&1
OK $cudaResult

# =============================================================================
#  STEP 5 — Project dependencies
# =============================================================================
Show-Banner
Show-Progress 5 7 "Installing project dependencies..."

$reqFile = Join-Path $ROOT "requirements-windows.txt"
if (-not (Test-Path $reqFile)) { $reqFile = Join-Path $ROOT "requirements.txt" }

# Build a filtered requirements file that skips torch/torchaudio — already
# installed in Step 4 with the correct CUDA index-url. Re-running pip against
# a different index-url for torch risks downgrading or breaking CUDA support.
$filteredReq = Join-Path $ROOT "requirements-windows-filtered.txt"
try {
    Get-Content $reqFile |
        Where-Object { $_ -notmatch '^\s*(torch|torchaudio)\b' -and $_ -notmatch 'download\.pytorch\.org' } |
        Set-Content $filteredReq
    INFO "Installing from: $(Split-Path $reqFile -Leaf)  (torch already installed, skipped)"
    & $pip install -r $filteredReq
    if ($LASTEXITCODE -ne 0) {
        WARN "Some packages had issues. Retrying with base requirements.txt..."
        Get-Content (Join-Path $ROOT "requirements.txt") |
            Where-Object { $_ -notmatch '^\s*(torch|torchaudio)\b' -and $_ -notmatch 'download\.pytorch\.org' } |
            Set-Content $filteredReq
        & $pip install -r $filteredReq
        if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed." }
    }
} finally {
    if (Test-Path $filteredReq) { Remove-Item $filteredReq -Force -ErrorAction SilentlyContinue }
}
OK "All project dependencies installed."

# =============================================================================
#  STEP 6 — Project setup
# =============================================================================
Show-Banner
Show-Progress 6 7 "Configuring project files..."

# Directories
foreach ($d in @("outputs", "samples", "voice reference")) {
    $dp = Join-Path $ROOT $d
    if (-not (Test-Path $dp)) {
        New-Item -ItemType Directory -Path $dp | Out-Null
        OK "Created folder: '$d'"
    } else {
        OK "Folder exists:  '$d'"
    }
}

# .env — create from template first
$envFile     = Join-Path $ROOT ".env"
$envTemplate = Join-Path $ROOT "env.template"
try {
    if (-not (Test-Path $envFile)) {
        if (Test-Path $envTemplate) {
            Copy-Item $envTemplate $envFile
            OK "Created .env from env.template"
        } else {
            WARN "env.template not found — .env was not created."
        }
    } else {
        OK ".env already exists — skipping template copy."
    }
} catch {
    WARN "Could not create .env — $_"
}

# ── API Key prompt ─────────────────────────────────────────────────────────────
# Check if .env already has real (non-placeholder) keys so we don't
# prompt unnecessarily on a re-run and risk overwriting valid keys.
$envExists      = Test-Path $envFile
$hfAlreadySet   = $false
$geminiAlready  = $false
if ($envExists) {
    $existing = Get-Content $envFile -Raw
    $hfAlreadySet  = ($existing -match "HUGGINGFACE_TOKEN=(?!your_token_here).+")
    $geminiAlready = ($existing -match "GOOGLE_GEMINI_API_KEY=(?!your_gemini_api_key_here).+")
}

NL
Cyan  "  ┌─ API Keys Setup ────────────────────────────────────────────────┐"; NL
Cyan  "  │                                                                 │"; NL
Cyan  "  │  "; White "You can enter your API keys now, or skip and add them later  "; Cyan "│"; NL
Cyan  "  │  "; White "in the "; Yellow "Settings tab"; White " once you launch the app.             "; Cyan "│"; NL
Cyan  "  │                                                                 │"; NL
Cyan  "  │  "; Gray  "Just press Enter to skip any key.                            "; Cyan "│"; NL
Cyan  "  └─────────────────────────────────────────────────────────────────┘"; NL
NL

# HuggingFace Token
if ($hfAlreadySet) {
    OK "HuggingFace token already set in .env — skipping prompt."
    $hfToken = ""
} else {
    Write-Host "  HuggingFace Token" -ForegroundColor White
    Write-Host "  Needed before first speech generation (free at huggingface.co)" -ForegroundColor DarkGray
    Write-Host "  > " -ForegroundColor Cyan -NoNewline
    $hfToken = Read-Host
}

# Gemini API Key
NL
if ($geminiAlready) {
    OK "Gemini API key already set in .env — skipping prompt."
    $geminiKey = ""
} else {
    Write-Host "  Google Gemini API Key" -ForegroundColor White
    Write-Host "  Needed for Podcast generation & Enhance (free at aistudio.google.com)" -ForegroundColor DarkGray
    Write-Host "  > " -ForegroundColor Cyan -NoNewline
    $geminiKey = Read-Host
}

# Write keys into .env
# IMPORTANT: writes BOTH HUGGINGFACE_TOKEN (read by model_manager.py) AND
# HF_TOKEN (read directly by the chatterbox library's snapshot_download calls).
if ($envExists) {
    try {
        $envContent = Get-Content $envFile -Raw

        if ($hfToken -and $hfToken.Trim() -ne "") {
            $t = $hfToken.Trim()
            $envContent = $envContent -replace "(?m)^HUGGINGFACE_TOKEN=.*", "HUGGINGFACE_TOKEN=$t"
            # Also set HF_TOKEN — the chatterbox library reads this directly
            if ($envContent -match "(?m)^HF_TOKEN=") {
                $envContent = $envContent -replace "(?m)^HF_TOKEN=.*", "HF_TOKEN=$t"
            } else {
                $envContent = $envContent.TrimEnd() + "`r`nHF_TOKEN=$t`r`n"
            }
            OK "HuggingFace token saved  (HUGGINGFACE_TOKEN + HF_TOKEN)."
        } elseif (-not $hfAlreadySet) {
            WARN "HuggingFace token skipped — add it in Settings before first use."
        }

        if ($geminiKey -and $geminiKey.Trim() -ne "") {
            $g = $geminiKey.Trim()
            $envContent = $envContent -replace "(?m)^GOOGLE_GEMINI_API_KEY=.*", "GOOGLE_GEMINI_API_KEY=$g"
            OK "Gemini API key saved."
        } elseif (-not $geminiAlready) {
            WARN "Gemini API key skipped — Podcast & Enhance won't work until added."
        }

        [System.IO.File]::WriteAllText($envFile, $envContent, [System.Text.Encoding]::UTF8)
    } catch {
        WARN "Could not write keys to .env — $_"
        WARN "You can add them manually in the Settings tab after launch."
    }
}

NL
Gray  "  You can add or change API keys anytime in the "; Yellow "Settings"; Gray " tab"; NL
Gray  "  inside the app, or by editing the "; Cyan ".env"; Gray " file directly."; NL

# Launch script
$launchPath = Join-Path $ROOT "Launch SurAIverse.bat"
$launchContent = @"
@echo off
title SurAIverse TTS Studio
color 0B
echo.
echo   Starting SurAIverse TTS Studio...
echo   Open your browser at:  http://localhost:7860
echo.
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0app\gradio_app.py" %*
pause
"@
[System.IO.File]::WriteAllText($launchPath, $launchContent, [System.Text.Encoding]::ASCII)
OK "Created 'Launch SurAIverse.bat'"

# =============================================================================
#  STEP 7 — Verify
# =============================================================================
Show-Banner
Show-Progress 7 7 "Verifying installation..."

$checks = @(
    @{ Name = "Chatterbox TTS";  Code = "from chatterbox.tts import ChatterboxTTS; print('ok')" },
    @{ Name = "Gradio";          Code = "import gradio; print(gradio.__version__)" },
    @{ Name = "PyTorch";         Code = "import torch; print(torch.__version__)" },
    @{ Name = "Google Gemini";   Code = "import google.generativeai; print('ok')" },
    @{ Name = "FastAPI";         Code = "import fastapi; print(fastapi.__version__)" }
)

foreach ($c in $checks) {
    $result = & $python -c $c.Code 2>&1
    if ($LASTEXITCODE -eq 0) {
        OK "$($c.Name) — $result"
    } else {
        WARN "$($c.Name) — import failed (may still work at runtime)"
    }
}

# =============================================================================
#  SUCCESS SCREEN
# =============================================================================
Show-Banner
NL
Green "  ╔══════════════════════════════════════════════════════════════╗"; NL
Green "  ║                                                              ║"; NL
Green "  ║            Installation Complete!                           ║"; NL
Green "  ║                                                              ║"; NL
Green "  ╚══════════════════════════════════════════════════════════════╝"; NL
NL
Write-Host "  NEXT STEPS" -ForegroundColor White
NL
Write-Host "  1." -ForegroundColor Yellow -NoNewline
Write-Host " If you skipped API keys, add them in the " -ForegroundColor White -NoNewline
Write-Host "Settings" -ForegroundColor Cyan -NoNewline
Write-Host " tab after launch," -ForegroundColor White
Write-Host "     or open " -ForegroundColor Gray -NoNewline
Write-Host ".env" -ForegroundColor Cyan -NoNewline
Write-Host " and fill in:" -ForegroundColor Gray
Write-Host "     HUGGINGFACE_TOKEN      " -ForegroundColor Gray -NoNewline
Write-Host "(model downloads — free at huggingface.co)" -ForegroundColor DarkGray
Write-Host "     GOOGLE_GEMINI_API_KEY  " -ForegroundColor Gray -NoNewline
Write-Host "(Podcast & Enhance — free at aistudio.google.com)" -ForegroundColor DarkGray
NL
Write-Host "  2." -ForegroundColor Yellow -NoNewline
Write-Host " Double-click " -ForegroundColor White -NoNewline
Write-Host "'Launch SurAIverse.bat'" -ForegroundColor Cyan
Write-Host "     Then open your browser at:" -ForegroundColor Gray -NoNewline
Write-Host "  http://localhost:7860" -ForegroundColor Cyan
NL
Write-Host "  3." -ForegroundColor Yellow -NoNewline
Write-Host " On first launch, models (~2 GB) will download automatically." -ForegroundColor White
NL
Cyan  "  ─────────────────────────────────────────────────────────────────"; NL
NL
Yellow "  Tested on: "; White "Windows 11  +  NVIDIA RTX 4090  (24 GB VRAM)"; NL
Gray  "  Speed varies by GPU. CPU-only is supported but much slower."; NL
NL
Cyan  "  ─────────────────────────────────────────────────────────────────"; NL
NL
Write-Host "  Enjoying SurAIverse? Please SUBSCRIBE on YouTube!" -ForegroundColor Yellow
NL
Yellow "  ▶  "; Cyan "youtube.com/@suraiverse"; NL
NL
Cyan  "  ─────────────────────────────────────────────────────────────────"; NL
NL
Write-Host "  Happy creating!  — Suresh Pydikondala" -ForegroundColor White
NL
Write-Host "  Press Enter to exit the installer." -ForegroundColor Gray
Read-Host | Out-Null
