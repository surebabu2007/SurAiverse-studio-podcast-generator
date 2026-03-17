#!/bin/bash
# =============================================================================
# Chatterbox TTS - Auto-Update & Run Script
# Checks for Git updates, pulls if available, and launches the Gradio app
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}     🎙️  ${GREEN}Chatterbox TTS - Auto-Update & Run${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Function: Check if Git is available
# =============================================================================
check_git() {
    if ! command -v git &> /dev/null; then
        echo -e "${YELLOW}⚠ Git not found. Skipping update check.${NC}"
        return 1
    fi
    
    if [ ! -d ".git" ]; then
        echo -e "${YELLOW}⚠ Not a Git repository. Skipping update check.${NC}"
        return 1
    fi
    
    return 0
}

# =============================================================================
# Function: Check for Git updates
# =============================================================================
check_for_updates() {
    echo -e "${BLUE}🔍 Checking for updates...${NC}"
    
    # Get current branch
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    
    # Fetch latest from remote (suppress output)
    if ! git fetch origin "$CURRENT_BRANCH" --quiet 2>/dev/null; then
        echo -e "${YELLOW}⚠ Could not fetch from remote. Continuing with current version.${NC}"
        return 1
    fi
    
    # Get local and remote commit hashes
    LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null)
    REMOTE_HASH=$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null || echo "$LOCAL_HASH")
    
    if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
        echo -e "${GREEN}✓ Already up to date!${NC}"
        return 1
    else
        # Count commits behind
        COMMITS_BEHIND=$(git rev-list --count HEAD.."origin/$CURRENT_BRANCH" 2>/dev/null || echo "some")
        echo -e "${YELLOW}📦 Updates available! ($COMMITS_BEHIND commits behind)${NC}"
        return 0
    fi
}

# =============================================================================
# Function: Pull updates
# =============================================================================
pull_updates() {
    echo -e "${BLUE}⬇️  Pulling latest changes...${NC}"
    
    # Check for local changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "${YELLOW}⚠ You have local changes. Stashing them...${NC}"
        git stash push -m "Auto-stash before update $(date '+%Y-%m-%d %H:%M:%S')"
        STASHED=true
    fi
    
    # Pull changes
    if git pull origin "$(git rev-parse --abbrev-ref HEAD)" --quiet; then
        echo -e "${GREEN}✓ Updates pulled successfully!${NC}"
        
        # Check if requirements.txt was updated
        if git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -q "requirements.txt"; then
            echo -e "${YELLOW}📦 requirements.txt changed. Updating dependencies...${NC}"
            UPDATE_DEPS=true
        fi
    else
        echo -e "${RED}✗ Failed to pull updates. Continuing with current version.${NC}"
    fi
    
    # Restore stashed changes if any
    if [ "$STASHED" = true ]; then
        echo -e "${BLUE}📂 Restoring your local changes...${NC}"
        git stash pop --quiet 2>/dev/null || echo -e "${YELLOW}⚠ Could not restore stash. Check 'git stash list'${NC}"
    fi
}

# =============================================================================
# Function: Activate virtual environment
# =============================================================================
activate_venv() {
    if [ -d "venv" ]; then
        echo -e "${BLUE}🐍 Activating virtual environment...${NC}"
        source venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${YELLOW}⚠ Virtual environment not found. Running setup first...${NC}"
        if [ -f "setup.sh" ]; then
            bash setup.sh
            source venv/bin/activate
        else
            echo -e "${RED}✗ setup.sh not found. Please run setup manually.${NC}"
            exit 1
        fi
    fi
}

# =============================================================================
# Function: Update dependencies if needed
# =============================================================================
update_dependencies() {
    if [ "$UPDATE_DEPS" = true ]; then
        echo -e "${BLUE}📦 Installing updated dependencies...${NC}"
        pip install -r requirements.txt --quiet
        echo -e "${GREEN}✓ Dependencies updated${NC}"
    fi
}

# =============================================================================
# Function: Check for .env file
# =============================================================================
check_env_file() {
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠ .env file not found!${NC}"
        if [ -f "env.template" ]; then
            echo -e "${BLUE}📝 Creating .env from env.template...${NC}"
            cp env.template .env
            echo -e "${GREEN}✓ Created .env file. Please edit it with your API keys.${NC}"
            
            # Open .env file if on Mac
            if [[ "$OSTYPE" == "darwin"* ]]; then
                 open .env || true
            fi
            
            # Read -p "Press Enter to continue after editing .env..."
        else
            echo -e "${RED}✗ env.template not found. Please create .env manually.${NC}"
        fi
    fi
}

# =============================================================================
# Function: Kill existing Gradio process
# =============================================================================
kill_existing() {
    local target_port=${1:-7860}
    if lsof -ti:$target_port &>/dev/null; then
        echo -e "${YELLOW}🔄 Stopping existing server on port $target_port...${NC}"
        lsof -ti:$target_port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# =============================================================================
# Main Execution
# =============================================================================

# Default flags
NO_UPDATE=false
SHARE=true
# Default port variable
TARGET_PORT=7860

NO_SHARE=false
EXTRA_ARGS=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-update|-n)
            NO_UPDATE=true
            ;;
        --share|-s)
            SHARE=true
            NO_SHARE=false
            ;;
        --no-share|-l)
            NO_SHARE=true
            SHARE=false
            ;;
        --port=*)
            TARGET_PORT="${arg#*=}"
            ;;
        --help|-h)
            echo ""
            echo -e "${CYAN}Usage:${NC} ./run.sh [OPTIONS]"
            echo ""
            echo -e "${GREEN}Options:${NC}"
            echo "  --share, -s        Create a public shareable link (default)"
            echo "  --no-share, -l     Local network only, no public link"
            echo "  --no-update, -n    Skip Git update check"
            echo "  --port=PORT        Use custom port (default: 7860)"
            echo "  --help, -h         Show this help message"
            echo ""
            echo -e "${GREEN}Examples:${NC}"
            echo "  ./run.sh                    # Run with public link"
            echo "  ./run.sh --no-share         # Local network only"
            echo "  ./run.sh --port=8080        # Use port 8080"
            echo "  ./run.sh -n -l              # Quick start, local only"
            echo ""
            exit 0
            ;;
    esac
done

# Build extra args for Python
if [ "$NO_SHARE" = true ]; then
    EXTRA_ARGS="$EXTRA_ARGS --no-share"
elif [ "$SHARE" = true ]; then
    EXTRA_ARGS="$EXTRA_ARGS --share"
fi

# Pass port to Python script
EXTRA_ARGS="$EXTRA_ARGS --port=$TARGET_PORT"


# Git update check
if [ "$NO_UPDATE" = false ] && check_git; then
    if check_for_updates; then
        pull_updates
    fi
fi

# Check for .env file
check_env_file

# Activate virtual environment
activate_venv

# Update dependencies if requirements changed
update_dependencies

# Kill any existing process on target port
kill_existing "$TARGET_PORT"

# Run the app with arguments
echo ""
echo -e "${GREEN}🚀 Starting Chatterbox TTS...${NC}"
if [ "$NO_SHARE" = true ]; then
    echo -e "${YELLOW}   Mode: Local network only (Port: $TARGET_PORT)${NC}"
else
    echo -e "${CYAN}   Mode: Public sharing enabled (Port: $TARGET_PORT)${NC}"
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

python app/gradio_app.py $EXTRA_ARGS

