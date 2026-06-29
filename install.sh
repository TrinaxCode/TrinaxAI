#!/usr/bin/env bash
# TrinaxAI — One-Command Installer (Linux/macOS/Windows Git Bash)
# Usage: curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

usage() {
  cat <<EOF
TrinaxAI One-Command Installer

Usage:
  ./install.sh                 Automatic install (auto-detects profile)
  ./install.sh --interactive   Ask before optional choices
  ./install.sh --no-models     Skip model downloads
  ./install.sh --no-vision     Skip vision model download
  ./install.sh --no-autostart  Do not enable boot autostart
  ./install.sh --no-start      Do not start TrinaxAI after install
  ./install.sh --profile 8gb|16gb|max|ultra
  ./install.sh --help          Show this help

What it does:
  1. Installs system dependencies (Python, Node.js, npm, Git, curl, unzip)
  2. Detects RAM and recommends a hardware profile (8gb/16gb/max/ultra)
  3. Writes .env with auto-detected LAN IP and model fleet
  4. Installs Ollama if missing
  5. Creates Python virtual environment and installs dependencies
  6. Builds the PWA frontend (Node.js required)
  7. Pulls recommended Ollama models (qwen2.5-coder, llama3.2, bge-m3)
  8. Enables auto-start on boot and starts TrinaxAI

Supported: Linux (apt/dnf/pacman/zypper/apk), macOS (Homebrew), Windows (Git Bash / WSL2)

Environment variables:
  TRINAXAI_PROFILE              Override auto-detected profile (8gb/16gb/max/ultra)
  TRINAXAI_INTERACTIVE=1        Ask before optional choices
  TRINAXAI_INSTALL_MODELS=0     Skip model downloads
  TRINAXAI_INSTALL_VISION=0     Skip vision model download
  TRINAXAI_ENABLE_AUTOSTART=0   Skip boot autostart
  TRINAXAI_START_NOW=0          Skip starting TrinaxAI at the end
EOF
  exit 0
}

INTERACTIVE="${TRINAXAI_INTERACTIVE:-0}"
INSTALL_MODELS="${TRINAXAI_INSTALL_MODELS:-1}"
INSTALL_VISION="${TRINAXAI_INSTALL_VISION:-1}"
ENABLE_AUTOSTART="${TRINAXAI_ENABLE_AUTOSTART:-1}"
START_NOW="${TRINAXAI_START_NOW:-1}"
PROFILE_OVERRIDE="${TRINAXAI_PROFILE:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --interactive) INTERACTIVE=1;;
    --no-models) INSTALL_MODELS=0; INSTALL_VISION=0;;
    --no-vision) INSTALL_VISION=0;;
    --no-autostart) ENABLE_AUTOSTART=0;;
    --no-start) START_NOW=0;;
    --profile)
      shift
      PROFILE_OVERRIDE="${1:-}"
      ;;
    --profile=*) PROFILE_OVERRIDE="${1#*=}";;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
  shift
done

print_header() { echo -e "\n${BLUE}${BOLD}═══ $1 ═══${NC}\n"; }
print_ok()    { echo -e "  ${GREEN}[OK]${NC} $1"; }
print_warn()  { echo -e "  ${YELLOW}[!]${NC} $1"; }
print_err()   { echo -e "  ${RED}[X]${NC} $1"; }
print_info()  { echo -e "  ${CYAN}[i]${NC} $1"; }
ask()         { read -p "$(echo -e "${GREEN}[?]${NC} $1 ")" -r; echo "$REPLY"; }

detect_ram_gb() {
  if [ "$OS" = "linux" ] && command -v awk >/dev/null 2>&1; then
    awk '/MemTotal/ { printf "%.0f", $2/1024/1024 }' /proc/meminfo 2>/dev/null || echo "0"
  elif [ "$OS" = "macos" ]; then
    bytes=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    echo $((bytes / 1024 / 1024 / 1024))
  else
    echo "0"
  fi
}

recommended_profile() {
  ram_gb="$(detect_ram_gb)"
  if [ "${ram_gb:-0}" -ge 32 ]; then
    echo "ultra"
  elif [ "${ram_gb:-0}" -ge 20 ]; then
    echo "max"
  elif [ "${ram_gb:-0}" -le 8 ] && [ "${ram_gb:-0}" -gt 0 ]; then
    echo "8gb"
  else
    echo "16gb"
  fi
}

lan_ip() {
  if [ "$OS" = "linux" ]; then
    hostname -I 2>/dev/null | awk '{print $1}'
  elif [ "$OS" = "macos" ]; then
    ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
  else
    echo ""
  fi
}

free_disk_gb() {
  df -Pk . 2>/dev/null | awk 'NR==2 { printf "%.0f", $4/1024/1024 }' || echo "0"
}

ensure_ollama_running() {
  command -v ollama >/dev/null 2>&1 || return 1
  if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    return 0
  fi
  mkdir -p "$SCRIPT_DIR/logs"
  print_info "Starting Ollama locally..."
  OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0}" nohup ollama serve > "$SCRIPT_DIR/logs/ollama.log" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

install_linux_deps() {
  print_info "Installing packages (Python, Node.js, npm, curl, git, unzip)..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv nodejs npm curl git unzip ufw
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip nodejs npm curl git unzip
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed --noconfirm python python-pip nodejs npm curl git unzip
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper --non-interactive install python3 python3-pip nodejs npm curl git unzip
  elif command -v apk >/dev/null 2>&1; then
    sudo apk add python3 py3-pip py3-virtualenv nodejs npm curl git unzip
  else
    print_warn "Unknown Linux package manager. Install Python 3.10+, pip, venv, Node.js 18+, npm, curl, git, unzip manually."
  fi
}

OS="unknown"
case "$(uname -s)" in
  Linux*)  OS="linux";;
  Darwin*) OS="macos";;
  MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac

if [ "$OS" = "windows" ] && [ -f "install.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-ExecutionPolicy" "Bypass" "-File" "$(pwd -W 2>/dev/null || pwd)/install.ps1")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$INSTALL_MODELS" = "1" ] || PS_ARGS+=("-NoModels")
  [ "$INSTALL_VISION" = "1" ] || PS_ARGS+=("-NoVision")
  [ "$ENABLE_AUTOSTART" = "1" ] || PS_ARGS+=("-NoAutostart")
  [ "$START_NOW" = "1" ] || PS_ARGS+=("-NoStart")
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  exec powershell.exe "${PS_ARGS[@]}"
fi

echo ""
echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║        TrinaxAI — Local AI Assistant      ║${NC}"
echo -e "${BLUE}${BOLD}║    github.com/TrinaxCode/TrinaxAI         ║${NC}"
echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo -e "  ${CYAN}OS:${NC} ${GREEN}${OS}${NC}"
echo -e "  ${CYAN}Privacy:${NC} 100% local — nothing leaves your machine"
echo ""

# ── Clone repo if running from piped script ──
REPO_DIR="${HOME}/trinaxai"
if [ ! -f "rag_api.py" ] && [ ! -f "install.sh" ]; then
  print_header "0/6 Cloning TrinaxAI repository"
  if [ -d "$REPO_DIR" ]; then
    print_ok "Repository already exists at $REPO_DIR"
    cd "$REPO_DIR"
  else
    git clone https://github.com/TrinaxCode/TrinaxAI.git "$REPO_DIR" 2>/dev/null || {
      print_warn "Could not clone repo. Downloading as ZIP..."
      curl -fsSL -o /tmp/trinaxai.zip https://github.com/TrinaxCode/TrinaxAI/archive/main.zip
      unzip -qo /tmp/trinaxai.zip -d /tmp/
      mv /tmp/TrinaxAI-main "$REPO_DIR"
      rm /tmp/trinaxai.zip
    }
    cd "$REPO_DIR"
    print_ok "Repository ready at $REPO_DIR"
  fi
else
  REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

SCRIPT_DIR="$REPO_DIR"
cd "$SCRIPT_DIR"

if [ "$OS" = "windows" ] && [ -f "install.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-ExecutionPolicy" "Bypass" "-File" "$(pwd -W 2>/dev/null || pwd)/install.ps1")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$INSTALL_MODELS" = "1" ] || PS_ARGS+=("-NoModels")
  [ "$INSTALL_VISION" = "1" ] || PS_ARGS+=("-NoVision")
  [ "$ENABLE_AUTOSTART" = "1" ] || PS_ARGS+=("-NoAutostart")
  [ "$START_NOW" = "1" ] || PS_ARGS+=("-NoStart")
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  exec powershell.exe "${PS_ARGS[@]}"
fi

print_header "1/6 System Dependencies"

if [ "$OS" = "linux" ]; then
  install_linux_deps
  print_ok "Linux dependencies ready"
elif [ "$OS" = "macos" ]; then
  if ! command -v brew &>/dev/null; then
    print_info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || true
  fi
  brew install python@3.11 node curl git 2>/dev/null || true
  print_ok "macOS dependencies ready"
elif [ "$OS" = "windows" ]; then
  print_warn "Windows detected. Please ensure you have:"
  print_info "  • Python 3.10+ from https://python.org"
  print_info "  • Git from https://git-scm.com"
  print_info "  • WSL2 recommended for full functionality"
fi

# ── Profile and .env ──
print_header "1.5/6 TrinaxAI Profile"
AUTO_PROFILE="$(recommended_profile)"
RAM_GB="$(detect_ram_gb)"
echo -e "  ${CYAN}Detected RAM:${NC} ${RAM_GB:-unknown} GB"
echo -e "  ${CYAN}Recommended profile:${NC} ${GREEN}${AUTO_PROFILE}${NC}"
echo ""
if [ -n "$PROFILE_OVERRIDE" ]; then
  case "$PROFILE_OVERRIDE" in
    8gb|16gb|max|ultra) PROFILE="$PROFILE_OVERRIDE";;
    low|lite) PROFILE="8gb";;
    medium|normal) PROFILE="16gb";;
    high) PROFILE="max";;
    *) print_warn "Unknown TRINAXAI_PROFILE=$PROFILE_OVERRIDE; using $AUTO_PROFILE"; PROFILE="$AUTO_PROFILE";;
  esac
elif [ "$INTERACTIVE" = "1" ]; then
  reply=$(ask "Setup mode: Normal recommended or Advanced manual? [N/a]")
  if [[ "$reply" =~ ^[Aa] ]]; then
    echo "  1) medium  Balanced default (about 16GB RAM)"
    echo "  2) high    Stronger CPU / more RAM"
    echo "  3) ultra   32GB+ RAM + powerful GPU, bigger context"
    echo "  4) low     Low memory (about 8GB RAM)"
    reply=$(ask "Choose profile [default: $AUTO_PROFILE]")
    case "$reply" in
      1|medium|16gb|"") PROFILE="$AUTO_PROFILE";;
      2|high|max) PROFILE="max";;
      3|ultra) PROFILE="ultra";;
      4|low|8gb) PROFILE="8gb";;
      *) PROFILE="$AUTO_PROFILE";;
    esac
  else
    PROFILE="$AUTO_PROFILE"
  fi
else
  PROFILE="$AUTO_PROFILE"
fi
print_ok "Automatic setup selected: profile=$PROFILE"

LAN_IP="$(lan_ip)"
cat > .env <<EOF
# TrinaxAI — Generated configuration ($(date +%Y-%m-%d))
# See .env.example for all available options.

# Profile (auto-detected: $AUTO_PROFILE, RAM: ${RAM_GB:-unknown} GB)
TRINAXAI_PROFILE=$PROFILE

# Network
TRINAXAI_HOST=0.0.0.0
TRINAXAI_PORT=3333
OLLAMA_BASE_URL=http://localhost:11434

# Model fleet (auto-router enabled by default)
TRINAXAI_MODEL_GENERAL=llama3.2:3b
TRINAXAI_MODEL_CODE=qwen2.5-coder:3b
TRINAXAI_MODEL_DEEP=qwen2.5-coder:3b
TRINAXAI_MODEL_FAST=llama3.2:3b
TRINAXAI_AUTO_ROUTE=1

# Embeddings
TRINAXAI_EMBED_PRESET=balanced
TRINAXAI_EMBED=bge-m3
TRINAXAI_EMBED_DIMS=1024

# Reranking (off by default — enable for better precision)
TRINAXAI_RERANK=0

# Security
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334,https://localhost:3335,http://localhost:3335,https://127.0.0.1:3335,http://127.0.0.1:3335${LAN_IP:+,https://$LAN_IP:3334,http://$LAN_IP:3334,https://$LAN_IP:3335,http://$LAN_IP:3335}
TRINAXAI_ALLOW_LAN_SYSTEM=1

# Indexing
TRINAXAI_INDEX_DIR=~/Documents
EOF
if [ "$PROFILE" = "ultra" ]; then
  cat >> .env <<'EOF'
TRINAXAI_NUM_CTX=16384
TRINAXAI_EMBED_WORKERS=6
TRINAXAI_MODEL_DEEP=qwen2.5-coder:14b
VITE_TRINAXAI_VISION_QUALITY_MODEL=qwen2.5vl:7b
EOF
elif [ "$PROFILE" = "max" ]; then
  cat >> .env <<'EOF'
TRINAXAI_NUM_CTX=8192
TRINAXAI_EMBED_WORKERS=4
TRINAXAI_MODEL_DEEP=qwen2.5-coder:7b
EOF
fi
print_ok ".env written with profile=$PROFILE"

# ── 2. Ollama ──
print_header "2/6 Ollama (Local AI Engine)"

if command -v ollama &>/dev/null; then
  print_ok "Ollama already installed"
else
  print_info "Installing Ollama..."
  if [ "$OS" = "linux" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
  elif [ "$OS" = "macos" ]; then
    brew install ollama
  elif [ "$OS" = "windows" ]; then
    print_warn "Download Ollama from: https://ollama.com/download/windows"
    print_warn "Install Ollama, then re-run this script for full setup."
    print_info "Continuing with Python and frontend setup..."
  fi
  print_ok "Ollama installed"
fi

# ── 3. Python Environment ──
print_header "3/6 Python Virtual Environment"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv || python -m venv .venv || {
    print_err "Could not create Python virtual environment."
    print_info "Install Python 3.10+ with venv support, then rerun ./install.sh"
    exit 1
  }
fi

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
else
  print_err "Virtual environment exists but activation script was not found."
  exit 1
fi

pip install --upgrade pip

if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
  print_ok "Python packages installed"
else
  print_warn "requirements.txt not found — skipping"
fi

# ── 4. PWA Frontend ──
print_header "4/6 PWA Frontend"

if [ -d "chat-pwa" ]; then
  cd chat-pwa
  if command -v node &>/dev/null; then
    npm install --silent 2>/dev/null || npm install
    npm run build >/dev/null 2>&1 || print_warn "PWA build failed — you can retry with: cd chat-pwa && npm run build"
    print_ok "PWA dependencies installed"
  else
    print_warn "Node.js not found. Install from https://nodejs.org"
    print_info "The PWA needs Node.js 18+ to build and serve"
  fi
  cd ..
else
  print_warn "chat-pwa/ directory not found"
fi

# ── 5. Default Models ──
print_header "5/6 AI Models"

DISK_GB="$(free_disk_gb)"
if [ "${DISK_GB:-0}" -gt 0 ] && [ "$DISK_GB" -lt 12 ]; then
  print_warn "Only ${DISK_GB}GB free. Model downloads may fail; free disk space before pulling large models."
fi

DEFAULT_MODELS=(
  "qwen2.5-coder:3b"
  "llama3.2:3b"
  "bge-m3"
)
VISION_MODEL="qwen2.5vl:3b"
if [ "${PROFILE:-16gb}" = "max" ]; then
  DEFAULT_MODELS+=("qwen2.5-coder:7b")
  VISION_MODEL="qwen2.5vl:7b"
elif [ "${PROFILE:-16gb}" = "ultra" ]; then
  DEFAULT_MODELS+=("qwen2.5-coder:7b" "qwen2.5-coder:14b")
  VISION_MODEL="qwen2.5vl:7b"
fi

echo ""
echo -e "${YELLOW}TrinaxAI works best with these models:${NC}"
echo "  General chat:   llama3.2:3b       (~2 GB)"
echo "  Code/router:    qwen2.5-coder:3b  (~2 GB)"
echo "  Embeddings:     bge-m3            (~1.2 GB)"
echo "  Vision (opt):   qwen2.5vl:3b      (~2 GB)"
if [ "${PROFILE:-16gb}" = "ultra" ]; then
  echo "  Ultra deep:     qwen2.5-coder:14b (~9 GB)"
fi
echo ""

if [ "$INTERACTIVE" = "1" ]; then
  reply=$(ask "Download default models now? [Y/n]")
  [[ "$reply" =~ ^[Nn] ]] && INSTALL_MODELS=0
fi

if [ "$INSTALL_MODELS" = "1" ]; then
  if ensure_ollama_running; then
    for model in "${DEFAULT_MODELS[@]}"; do
      echo "  Pulling $model..."
      ollama pull "$model" && print_ok "$model" || print_err "$model failed"
    done

    if [ "$INTERACTIVE" = "1" ]; then
      reply=$(ask "Download vision model ($VISION_MODEL)? [Y/n]")
      [[ "$reply" =~ ^[Nn] ]] && INSTALL_VISION=0
    fi
    if [ "$INSTALL_VISION" = "1" ]; then
      ollama pull "$VISION_MODEL" && print_ok "$VISION_MODEL" || print_err "$VISION_MODEL failed"
    fi
  else
    print_warn "Ollama is not available yet; skipping model downloads. TrinaxAI will still install."
    print_info "After installing/starting Ollama, run: ollama pull llama3.2:3b && ollama pull qwen2.5-coder:3b && ollama pull bge-m3"
  fi
else
  print_info "Skipping model download. You can pull them later with: ollama pull <model>"
fi

# ── 6. Auto-Start Service ──
print_header "6/6 Auto-Start on Boot"

if [ "$START_NOW" = "1" ]; then
  print_info "Starting TrinaxAI services..."
  python service_manager.py start --base-dir "$SCRIPT_DIR" && print_ok "TrinaxAI started" || \
    print_warn "Could not start automatically. Run: ./startup_ai.sh"
fi

if [ "$INTERACTIVE" = "1" ]; then
  echo ""
  echo -e "${YELLOW}Start TrinaxAI automatically when your computer turns on?${NC}"
  echo "You can change this later in the PWA Settings page."
  reply=$(ask "Enable auto-start on boot? [Y/n]")
  [[ "$reply" =~ ^[Nn]$ ]] && ENABLE_AUTOSTART=0
fi

if [ "$ENABLE_AUTOSTART" = "1" ]; then
  python service_manager.py enable-autostart --base-dir "$SCRIPT_DIR" && \
    print_ok "Auto-start enabled" || \
    print_warn "Could not enable auto-start automatically. Use: python service_manager.py enable-autostart --base-dir \"$SCRIPT_DIR\""
else
  print_info "Auto-start skipped. Enable it later in PWA Settings."
fi

# ── Done ──
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║      TrinaxAI is ready!                  ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}PWA Frontend:${NC}  https://localhost:3334"
echo -e "  ${BLUE}RAG API:${NC}      https://localhost:3333/health"
echo -e "  ${BLUE}Ollama API:${NC}    http://localhost:11434"
echo ""
echo -e "  ${BLUE}Quick start:${NC}   ./startup_ai.sh"
echo -e "  ${BLUE}Shutdown:${NC}     ./shutdown_ai.sh"
echo -e "  ${BLUE}System test:${NC}   python test_system.py --verbose"
echo -e "  ${BLUE}Docs:${NC}         https://github.com/TrinaxCode/TrinaxAI"
echo ""
echo -e "  ${YELLOW}From your phone:${NC} https://[YOUR-LAN-IP]:3334"
echo -e "  (Same WiFi network required. Check firewall: ports 3333, 3334, 11434)"
echo ""
echo -e "  ${YELLOW}⭐ Star the repo:${NC} github.com/TrinaxCode/TrinaxAI"
echo -e "  ${GREEN}100% open source — AGPL-3.0-or-later${NC}"
echo ""
