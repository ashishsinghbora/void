#!/usr/bin/env bash
# ==============================================================================
# ⚡ VOID - Zero-Friction One-Line Bootstrap Installer
# Repository: https://github.com/ashishsinghbora/void
# ==============================================================================

set -e

# ANSI Color Palettes
C_CYAN='\033[0;36m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[1;33m'
C_RED='\033[0;31m'
C_PURPLE='\033[0;35m'
C_RESET='\033[0m'
C_BOLD='\033[1m'

print_banner() {
    clear 2>/dev/null || true
    echo -e "${C_CYAN}${C_BOLD}"
    echo "  ██╗   ██╗ ██████╗ ██╗██████╗ "
    echo "  ██║   ██║██╔═══██╗██║██╔══██╗"
    echo "  ██║   ██║██║   ██║██║██║  ██║"
    echo "  ╚██╗ ██╔╝██║   ██║██║██║  ██║"
    echo "   ╚████╔╝ ╚██████╔╝██║██████╔╝"
    echo "    ╚═══╝   ╚═════╝ ╚═╝╚═════╝ "
    echo -e "  Enterprise Edge Agentic Platform (Android / Termux)${C_RESET}"
    echo -e "${C_PURPLE}  -------------------------------------------------------------${C_RESET}"
    echo ""
}

log_info() {
    echo -e "${C_CYAN}[INFO]${C_RESET} $1"
}

log_success() {
    echo -e "${C_GREEN}[SUCCESS]${C_RESET} $1"
}

log_warning() {
    echo -e "${C_YELLOW}[WARNING]${C_RESET} $1"
}

log_error() {
    echo -e "${C_RED}[ERROR]${C_RESET} $1"
}

# 1. Environment & Architecture Detection
print_banner
log_info "Detecting hardware architecture and host operating system..."

IS_TERMUX=0
if [ -d "/data/data/com.termux" ] || [[ "$PREFIX" == *"com.termux"* ]]; then
    IS_TERMUX=1
    log_success "Target Environment: Native Android Termux detected."
else
    log_info "Target Environment: Desktop / Non-Termux Host ($(uname -s) $(uname -m))."
    log_info "Desktop Simulator Mode will be enabled automatically."
fi

# 2. Package Prerequisites Installation
if [ "$IS_TERMUX" -eq 1 ]; then
    log_info "Updating Termux package repositories..."
    pkg update -y || true

    log_info "Installing core prerequisites: termux-api, python, git, clang, libffi, openssl, jq, curl..."
    pkg install -y termux-api python git clang libffi openssl jq curl
    # Install pre-compiled cryptography binary from Termux pkg (avoids rust compilation)
    pkg install -y python-cryptography >/dev/null 2>&1 || true

    # Check / trigger storage permission
    if [ ! -d "$HOME/storage" ]; then
        log_info "Requesting Android Storage permissions (termux-setup-storage)..."
        echo -e "${C_YELLOW}>>> If an Android permission popup appears, please tap 'ALLOW' <<<${C_RESET}"
        termux-setup-storage || true
        sleep 1
    fi

    # Acquire wake-lock to prevent OS battery murder
    if command -v termux-wake-lock >/dev/null 2>&1; then
        log_info "Acquiring Termux wake-lock to maintain continuous edge processing..."
        termux-wake-lock || true
    fi

    # Test Termux:API Companion APK
    log_info "Testing Termux:API companion service..."
    if ! termux-battery-status >/dev/null 2>&1; then
        echo ""
        log_warning "Termux:API CLI tool is installed, but Android returned an error."
        echo -e "${C_YELLOW}================================================================${C_RESET}"
        echo -e "${C_BOLD}ACTION REQUIRED: Install Termux:API Companion APK${C_RESET}"
        echo -e "Android requires the 'Termux:API' APK to bridge hardware sensors."
        echo -e "1. Download Termux:API from F-Droid (NOT Google Play):"
        echo -e "   ${C_CYAN}https://f-droid.org/packages/com.termux.api/${C_RESET}"
        echo -e "2. Grant permissions in Android Settings -> Apps -> Termux:API"
        echo -e "   (Camera, Contacts, SMS, Location, Physical Activity)"
        echo -e "${C_YELLOW}================================================================${C_RESET}"
        echo ""
    else
        log_success "Termux:API communication verified successfully."
    fi
else
    # Linux / macOS host prerequisite validation
    log_info "Checking developer toolchain (python3, git, curl)..."
    for tool in python3 git curl; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            log_error "Missing required tool: $tool. Please install it with your system package manager."
            exit 1
        fi
    done
fi

# 3. Repository Resolution or Clone
TARGET_DIR=""
# If script is run inside cloned repository
if [ -f "./termux_void.py" ] && [ -f "./app.py" ]; then
    TARGET_DIR="$(pwd)"
    log_info "Using current repository directory: $TARGET_DIR"
elif [ -d "$HOME/void" ] && [ -f "$HOME/void/app.py" ]; then
    TARGET_DIR="$HOME/void"
    log_info "Updating existing installation in $TARGET_DIR..."
    cd "$TARGET_DIR"
    git pull origin main || true
else
    TARGET_DIR="$HOME/void"
    log_info "Cloning Void repository from GitHub into $TARGET_DIR..."
    git clone https://github.com/ashishsinghbora/void.git "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

# 4. Dedicated Virtual Environment Setup
log_info "Configuring Python virtual environment in $TARGET_DIR/.venv..."
VENV_ARGS=""
if [ "$IS_TERMUX" -eq 1 ]; then
    VENV_ARGS="--system-site-packages"
fi
python3 -m venv $VENV_ARGS "$TARGET_DIR/.venv"
source "$TARGET_DIR/.venv/bin/activate"

log_info "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true

log_info "Installing Void core dependencies from requirements.txt..."
pip install --no-cache-dir -r "$TARGET_DIR/requirements.txt"

# 5. CLI Binary Symlink Registration
log_info "Registering 'void' global command launcher..."
chmod +x "$TARGET_DIR/bin/void"

BIN_DEST=""
if [ "$IS_TERMUX" -eq 1 ] && [ -d "$PREFIX/bin" ]; then
    BIN_DEST="$PREFIX/bin/void"
elif [ -w "/usr/local/bin" ]; then
    BIN_DEST="/usr/local/bin/void"
else
    mkdir -p "$HOME/.local/bin"
    BIN_DEST="$HOME/.local/bin/void"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        [ -f "$HOME/.zshrc" ] && echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    fi
fi

ln -sf "$TARGET_DIR/bin/void" "$BIN_DEST"
log_success "Global CLI executable linked at: $BIN_DEST"

# 6. Self-Verification Smoke Test
log_info "Running Void engine integrity verification..."
python3 -c "
from agents.react_agent import global_react_agent
from extensions.manager import global_extension_manager
ext_count = global_extension_manager.discover_and_load_all()
print(f'Verification: Void ReAct Engine Active | Extensions Loaded: {ext_count}')
"

# 7. Installation Completion Summary
echo ""
echo -e "${C_GREEN}${C_BOLD}================================================================${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}  ⚡ VOID INSTALLATION COMPLETE & VERIFIED SUCCESSFUL!${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}================================================================${C_RESET}"
echo ""
echo -e "${C_BOLD}Quick Launch Commands:${C_RESET}"
echo -e "  ${C_CYAN}void${C_RESET}               Launch interactive ReAct terminal session"
echo -e "  ${C_CYAN}void start${C_RESET}         Start production web dashboard & proactive daemons"
echo -e "  ${C_CYAN}void start-bg${C_RESET}      Start as background service (keeps running 24/7)"
echo -e "  ${C_CYAN}void status${C_RESET}        View active service, RAM RSS, and battery telemetry"
echo -e "  ${C_CYAN}void stop${C_RESET}          Halt background service cleanly"
echo -e "  ${C_CYAN}void test${C_RESET}          Run full automated test suite"
echo ""
echo -e "${C_BOLD}Access Dashboards:${C_RESET}"
echo -e "  • Local Web:       ${C_CYAN}http://localhost:5000${C_RESET}"
echo -e "  • GitHub Pages UI: ${C_CYAN}https://ashishsinghbora.github.io/void/${C_RESET}"
echo ""
echo -e "${C_BOLD}One-Line Command to Share with Friends:${C_RESET}"
echo -e "  ${C_YELLOW}curl -sSL https://raw.githubusercontent.com/ashishsinghbora/void/main/install.sh | bash${C_RESET}"
echo ""
