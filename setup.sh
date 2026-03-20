#!/bin/bash
# Chatterbox TTS Setup Script for Mac (Apple Silicon)
# This script sets up the complete environment

set -e  # Exit on error

echo "=========================================="
echo "  Chatterbox TTS Setup for Mac (Apple Silicon)"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python 3.11+ is available
echo -e "\n${YELLOW}Checking Python version...${NC}"
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
        PYTHON_CMD=python3
    else
        echo -e "${RED}Python 3.11+ is required. Found: $PYTHON_VERSION${NC}"
        echo "Please install Python 3.11: brew install python@3.11"
        exit 1
    fi
else
    echo -e "${RED}Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python: $($PYTHON_CMD --version)${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv venv
    echo -e "${GREEN}Virtual environment created${NC}"
else
    echo -e "${GREEN}Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "\n${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install PyTorch with MPS support first
echo -e "\n${YELLOW}Installing PyTorch for Apple Silicon (MPS-capable wheel)...${NC}"
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Verify MPS is available
echo -e "\n${YELLOW}Verifying MPS (Metal Performance Shaders) support...${NC}"
python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"

# Install remaining dependencies (filter out torch/torchaudio to avoid index conflicts)
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install -r <(grep -v -E "^(torch|torchaudio|--extra-index-url)" requirements.txt)

# Create necessary directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p outputs samples "voice reference"

# Check if .env exists, if not create from template
if [ ! -f ".env" ]; then
    if [ -f "env.template" ]; then
        echo -e "\n${YELLOW}Creating .env from template...${NC}"
        cp env.template .env
        echo -e "${RED}IMPORTANT: Please edit .env and add your HuggingFace token${NC}"
    fi
fi

# Verify installation
echo -e "\n${YELLOW}Verifying Chatterbox installation...${NC}"
python -c "from chatterbox.tts import ChatterboxTTS; print('Chatterbox TTS imported successfully')" 2>/dev/null && \
    echo -e "${GREEN}Chatterbox TTS is ready!${NC}" || \
    echo -e "${RED}Warning: Could not import Chatterbox TTS. You may need to download models first.${NC}"

# Create the double-clickable Mac launcher
echo -e "\n${YELLOW}Creating Mac launcher...${NC}"
cat > "Launch SurAIverse.command" << 'EOF'
#!/bin/bash
# SurAIverse TTS Studio — Mac one-click launcher
# Double-click this file in Finder to launch the app

# Change to the directory containing this script
cd "$(dirname "$0")"

# Hand off to run.sh (handles venv, updates, and launch)
bash run.sh "$@"
EOF
chmod +x "Launch SurAIverse.command"
echo -e "${GREEN}✓ Created 'Launch SurAIverse.command' — double-click it in Finder to start the app${NC}"

echo -e "\n=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo -e "\nNext steps:"
echo "1. Edit .env and add your HuggingFace token"
echo "2. Double-click 'Launch SurAIverse.command' in Finder to start the app"
echo "   (or run: bash run.sh)"

