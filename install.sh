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
  ./install.sh                 Guided install (asks optional choices)
  ./install.sh --interactive   Guided install (default)
  ./install.sh --non-interactive  Automatic install for CI/scripts
  ./install.sh --no-models     Skip model downloads
  ./install.sh --no-vision     Compatibility flag; vision downloads on first use
  ./install.sh --no-autostart  Do not enable boot autostart
  ./install.sh --no-auto-update Do not enable the weekly automatic update
  ./install.sh --no-start      Do not start TrinaxAI after install
  ./install.sh --lan-system    Enable LAN system-control endpoints (requires admin token)
  ./install.sh --profile 8gb|16gb|max|ultra
  ./install.sh --install-dir PATH  Choose the application directory
  ./install.sh --help          Show this help

What it does:
  1. Installs system dependencies (Python, Node.js, npm, Git, curl, unzip)
  2. Detects RAM and recommends a hardware profile (8gb/16gb/max/ultra)
  3. Writes .env with auto-detected LAN IP and model fleet
  4. Installs Ollama if missing
  5. Creates Python virtual environment and installs dependencies
  6. Builds the PWA frontend (Node.js required)
  7. Asks whether to pull recommended text/RAG Ollama models
  8. Asks whether to enable auto-start on boot and start TrinaxAI now
  9. Enables a safe weekly GitHub update check

Supported: Linux (apt/dnf/pacman/zypper/apk), macOS (Homebrew), Windows (Git Bash / WSL2)

Environment variables:
  TRINAXAI_PROFILE              Override auto-detected profile (8gb/16gb/max/ultra)
  TRINAXAI_INTERACTIVE=1        Ask before optional choices
  TRINAXAI_NONINTERACTIVE=1     Do not ask optional choices
  TRINAXAI_INSTALL_MODELS=0     Skip model downloads
  TRINAXAI_INSTALL_VISION=0     Compatibility env; vision downloads on first use
  TRINAXAI_ENABLE_AUTOSTART=0   Skip boot autostart
  TRINAXAI_ENABLE_AUTO_UPDATE=0 Skip weekly automatic updates
  TRINAXAI_START_NOW=0          Skip starting TrinaxAI at the end
  TRINAXAI_ALLOW_LAN_SYSTEM=1   Enable LAN system-control endpoints
  TRINAXAI_ADMIN_TOKEN=...      Admin token required for sensitive system endpoints
  TRINAXAI_HOME=...             Application directory override
EOF
  exit 0
}

INTERACTIVE="${TRINAXAI_INTERACTIVE:-1}"
NONINTERACTIVE="${TRINAXAI_NONINTERACTIVE:-0}"
if [ "$NONINTERACTIVE" = "1" ]; then
  INTERACTIVE=0
fi
INSTALL_MODELS="${TRINAXAI_INSTALL_MODELS:-1}"
INSTALL_VISION="${TRINAXAI_INSTALL_VISION:-1}"
ENABLE_AUTOSTART="${TRINAXAI_ENABLE_AUTOSTART:-1}"
ENABLE_AUTO_UPDATE="${TRINAXAI_ENABLE_AUTO_UPDATE:-1}"
START_NOW="${TRINAXAI_START_NOW:-1}"
PROFILE_OVERRIDE="${TRINAXAI_PROFILE:-}"
ENABLE_LAN_SYSTEM="${TRINAXAI_ALLOW_LAN_SYSTEM:-0}"
ADMIN_TOKEN="${TRINAXAI_ADMIN_TOKEN:-}"
INSTALL_DIR="${TRINAXAI_HOME:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --interactive) INTERACTIVE=1; NONINTERACTIVE=0;;
    --non-interactive|--yes|-y) INTERACTIVE=0; NONINTERACTIVE=1;;
    --no-models) INSTALL_MODELS=0; INSTALL_VISION=0;;
    --no-vision) INSTALL_VISION=0;;
    --no-autostart) ENABLE_AUTOSTART=0;;
    --no-auto-update) ENABLE_AUTO_UPDATE=0;;
    --no-start) START_NOW=0;;
    --lan-system) ENABLE_LAN_SYSTEM=1;;
    --profile)
      shift
      PROFILE_OVERRIDE="${1:-}"
      ;;
    --profile=*) PROFILE_OVERRIDE="${1#*=}";;
    --install-dir)
      shift
      INSTALL_DIR="${1:-}"
      [ -n "$INSTALL_DIR" ] || { echo "--install-dir requires a path" >&2; exit 2; }
      ;;
    --install-dir=*) INSTALL_DIR="${1#*=}";;
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
ensure_cli_path() {
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) return 0 ;;
  esac
  local profile line
  case "${SHELL:-}" in
    */fish)
      profile="$HOME/.config/fish/config.fish"
      line='fish_add_path "$HOME/.local/bin"'
      ;;
    */zsh)
      profile="$HOME/.zshrc"
      line='export PATH="$HOME/.local/bin:$PATH"'
      ;;
    */bash)
      if [ "${OS:-}" = "macos" ]; then profile="$HOME/.bash_profile"; else profile="$HOME/.bashrc"; fi
      line='export PATH="$HOME/.local/bin:$PATH"'
      ;;
    *)
      profile="$HOME/.profile"
      line='export PATH="$HOME/.local/bin:$PATH"'
      ;;
  esac
  mkdir -p "$(dirname "$profile")"
  if ! grep -Fq '# >>> TrinaxAI CLI >>>' "$profile" 2>/dev/null; then
    printf '\n%s\n%s\n%s\n' '# >>> TrinaxAI CLI >>>' "$line" '# <<< TrinaxAI CLI <<<' >> "$profile"
    print_ok "CLI PATH saved in $profile"
  fi
  PATH="$HOME/.local/bin:$PATH"
  export PATH
}
as_root() {
  if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    print_err "Administrator access is required for: $*"
    print_info "Install the system dependencies manually, then run this installer again."
    return 127
  fi
}
ask() {
  local prompt="$1" reply=""
  if [ "${INTERACTIVE:-1}" != "1" ]; then
    echo ""
    return 0
  fi
  if [ -r /dev/tty ]; then
    read -r -p "$(echo -e "${GREEN}[?]${NC} $prompt ")" reply </dev/tty || reply=""
  elif [ -t 0 ]; then
    read -r -p "$(echo -e "${GREEN}[?]${NC} $prompt ")" reply || reply=""
  else
    echo -e "${YELLOW}[!]${NC} No interactive terminal; using default answer for: $prompt" >&2
  fi
  echo "$reply"
}
ask_default() {
  prompt="$1"
  default="$2"
  reply=$(ask "$prompt [$default]")
  if [ -z "$reply" ]; then
    echo "$default"
  else
    echo "$reply"
  fi
}
ask_yes_no() {
  local prompt="$1" default="${2:-y}" reply=""
  if [ "${INTERACTIVE:-1}" != "1" ]; then
    [[ "$default" =~ ^[Yy]$ ]]
    return $?
  fi
  if [[ "$default" =~ ^[Yy]$ ]]; then
    reply="$(ask "$prompt [Y/n]")"
    [[ "$reply" =~ ^[Nn] ]] && return 1
    return 0
  fi
  reply="$(ask "$prompt [y/N]")"
  [[ "$reply" =~ ^[Yy] ]] && return 0
  return 1
}

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
  OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}" nohup ollama serve > "$SCRIPT_DIR/logs/ollama.log" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

ensure_https_certificate() {
  mkdir -p "$SCRIPT_DIR/chat-pwa/certs"
  cert_key="$SCRIPT_DIR/chat-pwa/certs/localhost-key.pem"
  cert_file="$SCRIPT_DIR/chat-pwa/certs/localhost.pem"
  cert_crt="$SCRIPT_DIR/chat-pwa/certs/trinaxai-local.crt"
  if [ -f "$cert_key" ] && [ -f "$cert_file" ]; then
    print_ok "HTTPS certificate found"
    return 0
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    print_warn "OpenSSL was not found. HTTPS certificate generation skipped."
    print_warn "The PWA may run as HTTP or show a browser security warning."
    return 0
  fi
  print_info "Creating local HTTPS certificate for TrinaxAI..."
  san_entries="DNS:localhost,DNS:$(hostname 2>/dev/null || echo trinaxai),IP:127.0.0.1,IP:::1"
  if [ -n "${LAN_IP:-}" ]; then
    san_entries="$san_entries,IP:$LAN_IP"
  fi
  openssl req -x509 -newkey rsa:2048 -sha256 -days 1825 -nodes \
    -keyout "$cert_key" \
    -out "$cert_file" \
    -subj "/CN=TrinaxAI Local HTTPS" \
    -addext "subjectAltName=$san_entries" >/dev/null 2>&1 || {
      print_warn "Could not generate HTTPS certificate."
      return 0
    }
  cp "$cert_file" "$cert_crt"
  chmod 600 "$cert_key" 2>/dev/null || true
  print_ok "HTTPS certificate generated"

  if [ "$OS" = "macos" ]; then
    security add-trusted-cert -d -r trustRoot -k "$HOME/Library/Keychains/login.keychain-db" "$cert_crt" >/dev/null 2>&1 && \
      print_ok "HTTPS certificate trusted in macOS login keychain" || \
      print_warn "Could not auto-trust the certificate. Add $cert_crt to Keychain Access and trust it."
  elif [ "$OS" = "linux" ]; then
    if command -v update-ca-certificates >/dev/null 2>&1; then
      as_root cp "$cert_crt" /usr/local/share/ca-certificates/trinaxai-local.crt >/dev/null 2>&1 && \
      as_root update-ca-certificates >/dev/null 2>&1 && \
        print_ok "HTTPS certificate trusted in system CA store" || \
        print_warn "Could not auto-trust the certificate. Import $cert_crt manually in your browser/system."
    elif command -v update-ca-trust >/dev/null 2>&1; then
      as_root cp "$cert_crt" /etc/pki/ca-trust/source/anchors/trinaxai-local.crt >/dev/null 2>&1 && \
      as_root update-ca-trust >/dev/null 2>&1 && \
        print_ok "HTTPS certificate trusted in system CA store" || \
        print_warn "Could not auto-trust the certificate. Import $cert_crt manually in your browser/system."
    else
      print_warn "No supported CA trust updater found. Import $cert_crt manually in your browser/system."
    fi
  fi
}

install_linux_deps() {
  print_info "Installing packages (Python, Node.js, npm, curl, git, unzip)..."
  if command -v apt-get >/dev/null 2>&1; then
    as_root apt-get update -qq
    # npm ships with NodeSource/Node.js, but the distro npm package may conflict.
    # Try nodejs + npm together; if that fails, install nodejs alone.
    as_root apt-get install -y python3 python3-pip python3-venv curl git unzip ufw openssl
    if ! command -v node >/dev/null 2>&1; then
      as_root apt-get install -y nodejs npm 2>/dev/null || as_root apt-get install -y nodejs || true
    fi
    if ! command -v npm >/dev/null 2>&1; then
      print_warn "npm was not installed. Node.js may be missing or installed from NodeSource."
      print_info "Install Node.js 18+ with npm from https://nodejs.org or use your package manager."
    fi
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf install -y python3 python3-pip nodejs npm curl git unzip openssl
  elif command -v pacman >/dev/null 2>&1; then
    as_root pacman -Sy --needed --noconfirm python python-pip nodejs npm curl git unzip openssl
  elif command -v zypper >/dev/null 2>&1; then
    as_root zypper --non-interactive install python3 python3-pip nodejs npm curl git unzip openssl
  elif command -v apk >/dev/null 2>&1; then
    as_root apk add python3 py3-pip py3-virtualenv nodejs npm curl git unzip openssl
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

if [ -z "$INSTALL_DIR" ]; then
  if [ -f "$HOME/trinaxai/rag_api.py" ]; then
    INSTALL_DIR="$HOME/trinaxai"
  elif [ "$OS" = "macos" ]; then
    INSTALL_DIR="$HOME/Library/Application Support/TrinaxAI"
  else
    INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/trinaxai"
  fi
fi

if [ "$OS" = "windows" ] && [ -f "install.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-ExecutionPolicy" "Bypass" "-File" "$(pwd -W 2>/dev/null || pwd)/install.ps1")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$INSTALL_MODELS" = "1" ] || PS_ARGS+=("-NoModels")
  [ "$INSTALL_VISION" = "1" ] || PS_ARGS+=("-NoVision")
  [ "$ENABLE_AUTOSTART" = "1" ] || PS_ARGS+=("-NoAutostart")
  [ "$ENABLE_AUTO_UPDATE" = "1" ] || PS_ARGS+=("-NoAutoUpdate")
  [ "$START_NOW" = "1" ] || PS_ARGS+=("-NoStart")
  [ "$ENABLE_LAN_SYSTEM" = "1" ] && PS_ARGS+=("-LanSystem")
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  [ -z "$INSTALL_DIR" ] || PS_ARGS+=("-InstallDir" "$INSTALL_DIR")
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
REPO_DIR="$INSTALL_DIR"
MANAGED_INSTALL=0
if [ ! -f "rag_api.py" ]; then
  print_header "0/6 Cloning TrinaxAI repository"
  if [ -d "$REPO_DIR" ]; then
    if [ ! -f "$REPO_DIR/rag_api.py" ] || [ ! -f "$REPO_DIR/pyproject.toml" ]; then
      print_err "Install directory exists but is not a TrinaxAI installation: $REPO_DIR"
      print_info "Choose another location with --install-dir PATH."
      exit 1
    fi
    print_ok "Existing TrinaxAI installation found at $REPO_DIR"
    cd "$REPO_DIR"
  else
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone https://github.com/TrinaxCode/TrinaxAI.git "$REPO_DIR" 2>/dev/null || {
      print_warn "Could not clone repo. Downloading a source archive..."
      temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/trinaxai.XXXXXX")"
      curl -fsSL -o "$temp_dir/trinaxai.tar.gz" https://github.com/TrinaxCode/TrinaxAI/archive/refs/heads/main.tar.gz
      tar -xzf "$temp_dir/trinaxai.tar.gz" -C "$temp_dir"
      mv "$temp_dir/TrinaxAI-main" "$REPO_DIR"
      rm -rf "$temp_dir"
    }
    MANAGED_INSTALL=1
    cd "$REPO_DIR"
    print_ok "Repository ready at $REPO_DIR"
  fi
else
  REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

SCRIPT_DIR="$REPO_DIR"
cd "$SCRIPT_DIR"
if [ "$MANAGED_INSTALL" = "1" ]; then
  printf '%s\n' "Managed by the TrinaxAI installer." > .trinaxai-managed
fi

if [ "$OS" = "windows" ] && [ -f "install.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-ExecutionPolicy" "Bypass" "-File" "$(pwd -W 2>/dev/null || pwd)/install.ps1")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$INSTALL_MODELS" = "1" ] || PS_ARGS+=("-NoModels")
  [ "$INSTALL_VISION" = "1" ] || PS_ARGS+=("-NoVision")
  [ "$ENABLE_AUTOSTART" = "1" ] || PS_ARGS+=("-NoAutostart")
  [ "$ENABLE_AUTO_UPDATE" = "1" ] || PS_ARGS+=("-NoAutoUpdate")
  [ "$START_NOW" = "1" ] || PS_ARGS+=("-NoStart")
  [ "$ENABLE_LAN_SYSTEM" = "1" ] && PS_ARGS+=("-LanSystem")
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  [ -z "$INSTALL_DIR" ] || PS_ARGS+=("-InstallDir" "$INSTALL_DIR")
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
    if [ -x /opt/homebrew/bin/brew ]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi
  brew install python@3.11 node curl git openssl 2>/dev/null || true
  print_ok "macOS dependencies ready"
elif [ "$OS" = "windows" ]; then
  print_warn "Windows detected. Please ensure you have:"
  print_info "  • Python 3.10+ from https://python.org"
  print_info "  • Git from https://git-scm.com"
  print_info "  • WSL2 recommended for full functionality"
fi

PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  print_err "Python 3.10 or newer was not found."
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' 2>/dev/null; then
  print_err "Node.js 18 or newer is required. Install an active Node.js LTS release and run the installer again."
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  print_err "npm was not found next to Node.js. Install the complete Node.js distribution and retry."
  exit 1
fi
print_ok "Runtime versions ready: $($PYTHON_BIN --version 2>&1), Node $(node --version)"

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

MODEL_GENERAL="qwen3.5:9b"
MODEL_CODE="qwen2.5-coder:3b"
MODEL_DEEP="qwen3.5:9b"
MODEL_FAST="granite4:3b"
EMBED_PRESET="balanced"
EMBED_MODEL="bge-m3"
EMBED_DIMS="1024"
EMBED_BATCH="8"
EMBED_KEEP_ALIVE="15m"
VISION_MODEL="qwen3-vl:4b-instruct"
if [ "$PROFILE" = "8gb" ]; then
  MODEL_GENERAL="qwen3.5:4b"
  MODEL_CODE="qwen2.5-coder:1.5b"
  MODEL_DEEP="qwen3.5:4b"
  MODEL_FAST="qwen3.5:0.8b"
  EMBED_PRESET="balanced"
  EMBED_MODEL="bge-m3"
  EMBED_DIMS="1024"
  EMBED_BATCH="1"
  EMBED_KEEP_ALIVE="5m"
  VISION_MODEL="qwen3-vl:2b-instruct"
elif [ "$PROFILE" = "max" ]; then
  MODEL_GENERAL="qwen3.5:27b"
  MODEL_CODE="qwen2.5-coder:7b"
  MODEL_DEEP="qwen3.5:27b"
  MODEL_FAST="qwen3.5:4b"
  VISION_MODEL="qwen3-vl:8b-instruct"
  EMBED_KEEP_ALIVE="30m"
elif [ "$PROFILE" = "ultra" ]; then
  MODEL_GENERAL="qwen3.5:35b-a3b"
  MODEL_CODE="qwen2.5-coder:14b"
  MODEL_DEEP="qwen3.5:35b-a3b"
  MODEL_FAST="qwen3.5:4b"
  VISION_MODEL="qwen3-vl:30b-a3b-instruct"
  EMBED_BATCH="16"
  EMBED_KEEP_ALIVE="30m"
fi

echo ""
echo -e "${CYAN}Model roles TrinaxAI needs:${NC}"
echo "  General chat: conversation and everyday questions"
echo "  Code/deep:    code, reasoning, refactors, project analysis"
echo "  Embeddings:   RAG indexing and semantic search"
echo "  Vision:       image and screenshot analysis"
reply="r"
if [ "$INTERACTIVE" = "1" ]; then
  reply=$(ask "Use recommended Ollama models, or configure your own? [R/o]")
fi
if [[ "$reply" =~ ^[Oo]$ ]]; then
  MODEL_GENERAL="$(ask_default "General chat model" "$MODEL_GENERAL")"
  MODEL_CODE="$(ask_default "Code model" "$MODEL_CODE")"
  MODEL_DEEP="$(ask_default "Deep analysis model" "$MODEL_DEEP")"
  MODEL_FAST="$(ask_default "Fast model" "$MODEL_FAST")"
  EMBED_MODEL="$(ask_default "Embedding model for RAG" "$EMBED_MODEL")"
  VISION_MODEL="$(ask_default "Vision/image model" "$VISION_MODEL")"
fi

# ── LAN System Control ──
if [ "$ENABLE_LAN_SYSTEM" != "1" ]; then
  echo ""
  echo -e "${YELLOW}Security option: LAN system control${NC}"
  echo "This allows devices on your local network to call sensitive system endpoints"
  echo "(shutdown, startup, reload, indexing, file watchers, collection management)."
  echo "Only enable this if you trust your local network and use a strong admin token."
  if [ "$INTERACTIVE" != "1" ]; then
    echo -e "  ${CYAN}Default: disabled.${NC} Use --lan-system to enable non-interactively."
  fi
  if ask_yes_no "Enable LAN system control?" n; then
    ENABLE_LAN_SYSTEM=1
  else
    ENABLE_LAN_SYSTEM=0
  fi
fi

if [ "$ENABLE_LAN_SYSTEM" = "1" ] && [ -z "$ADMIN_TOKEN" ]; then
  ADMIN_TOKEN="$(openssl rand -hex 32 2>/dev/null || "$PYTHON_BIN" -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || true)"
  if [ -z "$ADMIN_TOKEN" ]; then
    print_err "Could not generate admin token. Install openssl or Python 3.6+."
    exit 1
  fi
  print_ok "Admin token generated and saved to .env"
fi

LAN_IP="$(lan_ip)"
cat > .env <<EOF
# TrinaxAI — Generated configuration ($(date +%Y-%m-%d))
# See .env.example for all available options.

# Profile (auto-detected: $AUTO_PROFILE, RAM: ${RAM_GB:-unknown} GB)
TRINAXAI_HOME="$SCRIPT_DIR"
TRINAXAI_PROFILE=$PROFILE
TRINAXAI_PERFORMANCE_MODE=fast

# Network
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1:11434
TRINAXAI_FRONTEND_URL=https://localhost:3334
TRINAXAI_FRONTEND_MODE=preview
TRINAXAI_RAG_HTTPS=1
TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=https://127.0.0.1:3333

# Model fleet (auto-router enabled by default)
TRINAXAI_MODEL_GENERAL=$MODEL_GENERAL
TRINAXAI_MODEL_CODE=$MODEL_CODE
TRINAXAI_MODEL_DEEP=$MODEL_DEEP
TRINAXAI_MODEL_FAST=$MODEL_FAST
TRINAXAI_AUTO_ROUTE=1

# Embeddings
TRINAXAI_EMBED_PRESET=$EMBED_PRESET
TRINAXAI_EMBED=$EMBED_MODEL
TRINAXAI_EMBED_DIMS=$EMBED_DIMS
TRINAXAI_EMBED_BATCH=$EMBED_BATCH
TRINAXAI_EMBED_KEEP_ALIVE=$EMBED_KEEP_ALIVE

# Vision
VITE_TRINAXAI_VISION_MODEL=$VISION_MODEL

# Reranking (off by default — enable for better precision)
TRINAXAI_RERANK=0

# Security
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334,https://localhost:3335,http://localhost:3335,https://127.0.0.1:3335,http://127.0.0.1:3335${LAN_IP:+,https://$LAN_IP:3334,http://$LAN_IP:3334,https://$LAN_IP:3335,http://$LAN_IP:3335}
TRINAXAI_ALLOW_LAN_SYSTEM=$ENABLE_LAN_SYSTEM
TRINAXAI_ADMIN_TOKEN=$ADMIN_TOKEN

# Indexing
TRINAXAI_INDEX_DIR=~/Documents
EOF
if [ "$PROFILE" = "ultra" ]; then
  cat >> .env <<'EOF'
TRINAXAI_NUM_CTX=16384
TRINAXAI_EMBED_WORKERS=6
EOF
elif [ "$PROFILE" = "max" ]; then
  cat >> .env <<'EOF'
TRINAXAI_NUM_CTX=8192
TRINAXAI_EMBED_WORKERS=4
EOF
fi
print_ok ".env written with profile=$PROFILE"

ensure_https_certificate

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

cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv || {
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

python -m pip install --upgrade pip

if [ -f "requirements.lock" ]; then
  python -m pip install -r requirements.lock
  print_ok "Locked Python packages installed"
elif [ -f "requirements.txt" ]; then
  python -m pip install -r requirements.txt
  print_ok "Python packages installed"
else
  print_warn "requirements.txt not found — skipping"
fi

python -m pip install -e .
print_ok "TrinaxAI CLI installed in editable mode"

if [ "$OS" = "linux" ] || [ "$OS" = "macos" ]; then
  mkdir -p "$HOME/.local/bin"
  CLI_TARGET="$SCRIPT_DIR/.venv/bin/trinaxai"
  if [ -x "$CLI_TARGET" ]; then
    ln -sfn "$CLI_TARGET" "$HOME/.local/bin/trinaxai"
    print_ok "CLI command linked: $HOME/.local/bin/trinaxai"
    ensure_cli_path
  else
    print_warn "CLI entry point was not found at $CLI_TARGET"
  fi
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

DEFAULT_MODELS=()
for model in "$MODEL_CODE" "$MODEL_DEEP" "$MODEL_GENERAL" "$MODEL_FAST" "$EMBED_MODEL"; do
  [ -n "$model" ] || continue
  case " ${DEFAULT_MODELS[*]} " in
    *" $model "*) ;;
    *) DEFAULT_MODELS+=("$model");;
  esac
done

echo ""
echo -e "${YELLOW}TrinaxAI works best with these models:${NC}"
echo "  General chat:   $MODEL_GENERAL"
echo "  Code/router:    $MODEL_CODE"
echo "  Deep analysis:  $MODEL_DEEP"
echo "  Embeddings:     $EMBED_MODEL"
echo "  Vision (lazy):  $VISION_MODEL"
echo ""

if [ "$INSTALL_MODELS" = "1" ]; then
  if ask_yes_no "Download the configured Ollama models now? Choose N if you will use models you already have." y; then
    INSTALL_MODELS=1
  else
    INSTALL_MODELS=0
  fi
fi

if [ "$INSTALL_MODELS" = "1" ]; then
  if ensure_ollama_running; then
    for model in "${DEFAULT_MODELS[@]}"; do
      echo "  Pulling $model..."
      ollama pull "$model" && print_ok "$model" || print_err "$model failed"
    done

    print_info "Vision model $VISION_MODEL will download on first image analysis."
  else
    print_warn "Ollama is not available yet; skipping model downloads. TrinaxAI will still install."
    print_info "After installing/starting Ollama, run: ollama pull qwen3.5:9b && ollama pull granite4:3b && ollama pull bge-m3"
  fi
else
  print_info "Skipping model download. You can pull them later with: ollama pull <model>"
fi

# ── 6. Auto-Start Service ──
print_header "6/6 Auto-Start on Boot"

if [ "$START_NOW" = "1" ]; then
  if ask_yes_no "Start TrinaxAI now after install?" y; then
    print_info "Starting TrinaxAI services..."
    python service_manager.py start --base-dir "$SCRIPT_DIR" && print_ok "TrinaxAI started" || \
      print_warn "Could not start automatically. Run: ./startup_ai.sh"
  else
    START_NOW=0
    print_info "Start skipped. Run ./startup_ai.sh or trinaxai start when ready."
  fi
fi

if [ "$ENABLE_AUTOSTART" = "1" ]; then
  echo ""
  echo -e "${YELLOW}Start TrinaxAI automatically when your computer turns on?${NC}"
  echo "You can change this later in the PWA Settings page."
  if ask_yes_no "Enable auto-start on boot?" y; then
    ENABLE_AUTOSTART=1
  else
    ENABLE_AUTOSTART=0
  fi
fi

if [ "$ENABLE_AUTO_UPDATE" = "1" ] && [ -f "$SCRIPT_DIR/scripts/auto_update.py" ]; then
  print_info "Enabling safe weekly updates from GitHub…"
  python scripts/auto_update.py enable --base-dir "$SCRIPT_DIR" && \
    print_ok "Automatic updates enabled (weekly)" || \
    print_warn "Could not enable the weekly task. Run: python scripts/auto_update.py enable"
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
echo -e "  ${BLUE}CLI:${NC}           trinaxai"
echo -e "  ${BLUE}New terminal:${NC}  Open one if your current shell cannot find the new CLI yet"
echo -e "  ${BLUE}Shutdown:${NC}     ./shutdown_ai.sh"
echo -e "  ${BLUE}System test:${NC}   python test_system.py --verbose"
echo -e "  ${BLUE}Updates:${NC}       Automatic check every week"
echo -e "  ${BLUE}Docs:${NC}         https://github.com/TrinaxCode/TrinaxAI"
echo ""
echo -e "  ${YELLOW}From your phone:${NC} https://[YOUR-LAN-IP]:3334"
echo -e "  (Same WiFi network required. Check firewall: ports 3333, 3334)"
echo ""
if [ "$ENABLE_LAN_SYSTEM" = "1" ]; then
  echo -e "  ${YELLOW}LAN system control:${NC} enabled"
  echo -e "  ${YELLOW}Admin token:${NC} saved in .env (TRINAXAI_ADMIN_TOKEN)"
  echo ""
else
  echo -e "  ${YELLOW}LAN system control:${NC} disabled by default"
  echo -e "  To enable later: set TRINAXAI_ALLOW_LAN_SYSTEM=1 and TRINAXAI_ADMIN_TOKEN in .env"
  echo ""
fi
echo -e "  ${YELLOW}⭐ Star the repo:${NC} github.com/TrinaxCode/TrinaxAI"
echo -e "  ${GREEN}100% open source — AGPL-3.0-or-later${NC}"
echo ""
