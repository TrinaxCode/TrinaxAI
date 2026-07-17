#!/usr/bin/env bash
# TrinaxAI uninstaller. Stops services and removes selected local runtime files.
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
print_step() { echo -e "\n${BLUE}${BOLD}┌─ $1${NC}"; }
print_ok() { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

as_root() {
  if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    return 127
  fi
}

usage() {
  cat <<EOF
TrinaxAI Uninstaller

Usage:
  ./uninstall.sh                 Guided uninstall (asks every optional removal)
  ./uninstall.sh --yes           Non-interactive uninstall with safe defaults
  ./uninstall.sh --remove-data   Also remove RAG storage and local_sources
  ./uninstall.sh --remove-models Also remove known Ollama models
  ./uninstall.sh --remove-ollama Also remove the Ollama application
  ./uninstall.sh --purge         Remove all generated data, certs, models, and Ollama
  ./uninstall.sh --keep-env      Keep generated .env
  ./uninstall.sh --remove-certs  Remove generated local HTTPS cert files
  ./uninstall.sh --help          Show this help

What it asks:
  - Stop running TrinaxAI services
  - Disable boot autostart
  - Remove .venv
  - Remove chat-pwa/node_modules and chat-pwa/dist
  - Remove logs
  - Remove generated .env
  - Remove RAG index/memory data
  - Remove generated local HTTPS cert files
  - Remove known Ollama models
  - Remove the Ollama application

What it always keeps:
  - Git repository and source code
  - Shell scripts, docs, tests, and project files
  - Ollama application unless you choose to remove it
EOF
  exit 0
}

INTERACTIVE="${TRINAXAI_INTERACTIVE:-1}"
NONINTERACTIVE="${TRINAXAI_NONINTERACTIVE:-0}"
if [ "$NONINTERACTIVE" = "1" ]; then
  INTERACTIVE=0
fi

CONFIRM_UNINSTALL=0
STOP_SERVICES=1
DISABLE_AUTOSTART=1
REMOVE_VENV=1
REMOVE_FRONTEND=1
REMOVE_LOGS=1
REMOVE_ENV=1
REMOVE_DATA=0
REMOVE_CERTS=0
REMOVE_MODELS=0
REMOVE_MODELS_SET=0
REMOVE_OLLAMA=0
PURGE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --interactive) INTERACTIVE=1; NONINTERACTIVE=0;;
    --non-interactive) INTERACTIVE=0; NONINTERACTIVE=1;;
    --yes|-y) INTERACTIVE=0; NONINTERACTIVE=1; CONFIRM_UNINSTALL=1;;
    --keep-services) STOP_SERVICES=0;;
    --keep-autostart) DISABLE_AUTOSTART=0;;
    --keep-venv) REMOVE_VENV=0;;
    --keep-frontend) REMOVE_FRONTEND=0;;
    --keep-logs) REMOVE_LOGS=0;;
    --keep-env) REMOVE_ENV=0;;
    --remove-env) REMOVE_ENV=1;;
    --remove-data) REMOVE_DATA=1;;
    --keep-data) REMOVE_DATA=0;;
    --remove-certs) REMOVE_CERTS=1;;
    --keep-certs) REMOVE_CERTS=0;;
    --remove-models) REMOVE_MODELS=1; REMOVE_MODELS_SET=1;;
    --keep-models) REMOVE_MODELS=0; REMOVE_MODELS_SET=1;;
    --remove-ollama) REMOVE_OLLAMA=1; REMOVE_MODELS=1; REMOVE_MODELS_SET=1;;
    --purge) PURGE=1; REMOVE_DATA=1; REMOVE_CERTS=1; REMOVE_MODELS=1; REMOVE_OLLAMA=1; REMOVE_MODELS_SET=1;;
    *) echo "Unknown option: $1" >&2; usage;;
  esac
  shift
done

ask() {
  local prompt="$1" reply=""
  if [ "$INTERACTIVE" != "1" ]; then
    echo ""
    return 0
  fi
  if [ -r /dev/tty ]; then
    read -r -p "[?] $prompt " reply </dev/tty || reply=""
  elif [ -t 0 ]; then
    read -r -p "[?] $prompt " reply || reply=""
  else
    echo "[!] No interactive terminal; using default answer for: $prompt" >&2
  fi
  echo "$reply"
}

ask_yes_no() {
  local prompt="$1" default="${2:-y}" reply=""
  if [ "$INTERACTIVE" != "1" ]; then
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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

is_windows() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

if is_windows && [ -f "$ROOT/uninstall.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-NoProfile" "-ExecutionPolicy" "Bypass" "-File" "$(cygpath -w "$ROOT/uninstall.ps1" 2>/dev/null || printf '%s' "$ROOT/uninstall.ps1")")
  [ "$CONFIRM_UNINSTALL" = "1" ] && PS_ARGS+=("-Yes")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$STOP_SERVICES" = "0" ] && PS_ARGS+=("-KeepServices")
  [ "$DISABLE_AUTOSTART" = "0" ] && PS_ARGS+=("-KeepAutostart")
  [ "$REMOVE_VENV" = "0" ] && PS_ARGS+=("-KeepVenv")
  [ "$REMOVE_FRONTEND" = "0" ] && PS_ARGS+=("-KeepFrontend")
  [ "$REMOVE_LOGS" = "0" ] && PS_ARGS+=("-KeepLogs")
  [ "$REMOVE_ENV" = "0" ] && PS_ARGS+=("-KeepEnv")
  [ "$REMOVE_DATA" = "1" ] && PS_ARGS+=("-RemoveData")
  [ "$REMOVE_CERTS" = "1" ] && PS_ARGS+=("-RemoveCerts")
  [ "$REMOVE_MODELS" = "1" ] && PS_ARGS+=("-RemoveModels")
  [ "$REMOVE_OLLAMA" = "1" ] && PS_ARGS+=("-RemoveOllama")
  [ "$PURGE" = "1" ] && PS_ARGS+=("-Purge")
  exec powershell.exe "${PS_ARGS[@]}"
fi

PYTHON_CMD=()
if [ -n "${TRINAXAI_PYTHON:-}" ]; then
  PYTHON_CMD=("$TRINAXAI_PYTHON")
elif [ -x ".venv/bin/python" ]; then
  PYTHON_CMD=(".venv/bin/python")
elif [ -x ".venv/Scripts/python.exe" ]; then
  PYTHON_CMD=(".venv/Scripts/python.exe")
elif is_windows && command -v py.exe >/dev/null 2>&1; then
  PYTHON_CMD=(py.exe -3)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
fi

abs_path() {
  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$1"
  else
    (cd "$(dirname "$1")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "$1")")
  fi
}

safe_remove() {
  local target abs win_path
  for target in "$@"; do
    [ -e "$target" ] || continue
    abs="$(abs_path "$target")"
    case "$abs" in
      "$ROOT") echo "Refusing to remove project root: $abs" >&2; exit 1 ;;
      "$ROOT"/*) ;;
      *) echo "Refusing to remove path outside project: $abs" >&2; exit 1 ;;
    esac
    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
      win_path="$(cygpath -w "$abs" 2>/dev/null || printf '%s' "$abs")"
      powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
        'param([string]$Path) if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop }' \
        "$win_path"
    else
      rm -rf -- "$abs"
    fi
  done
}

remove_cli_path_block() {
  local profile tmp
  for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" "$HOME/.config/fish/config.fish"; do
    [ -f "$profile" ] || continue
    grep -Fq '# >>> TrinaxAI CLI >>>' "$profile" || continue
    tmp="${profile}.trinaxai.tmp"
    awk '
      $0 == "# >>> TrinaxAI CLI >>>" { skip=1; next }
      $0 == "# <<< TrinaxAI CLI <<<" { skip=0; next }
      !skip { print }
    ' "$profile" > "$tmp"
    cat "$tmp" > "$profile"
    rm -f "$tmp"
    echo "[OK] Removed TrinaxAI PATH entry from $profile"
  done
}

echo -e "\n${BLUE}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║        TrinaxAI · Clean Uninstaller       ║${NC}"
echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo -e "  ${CYAN}Location:${NC} $ROOT"
echo -e "  ${GREEN}Protected by default:${NC} source code, indexes, and Ollama models"
echo ""

if [ "$INTERACTIVE" = "1" ]; then
  confirm="$(ask "Type UNINSTALL to continue:")"
  if [ "$confirm" != "UNINSTALL" ]; then
    echo "Cancelled."
    exit 0
  fi
elif [ "$CONFIRM_UNINSTALL" != "1" ]; then
  echo "[!] Non-interactive uninstall requires --yes." >&2
  exit 1
fi

if [ "$INTERACTIVE" = "1" ]; then
  ask_yes_no "Stop running TrinaxAI services now?" y || STOP_SERVICES=0
  ask_yes_no "Disable TrinaxAI auto-start on boot?" y || DISABLE_AUTOSTART=0
  ask_yes_no "Remove Python virtual environment (.venv)?" y || REMOVE_VENV=0
  ask_yes_no "Remove frontend dependencies/build (chat-pwa/node_modules and dist)?" y || REMOVE_FRONTEND=0
  ask_yes_no "Remove logs/?" y || REMOVE_LOGS=0
  ask_yes_no "Remove generated .env configuration and admin token?" y || REMOVE_ENV=0
  if ask_yes_no "Remove RAG index, memory, and local_sources data?" n; then
    REMOVE_DATA=1
  fi
  if ask_yes_no "Remove generated local HTTPS cert files?" n; then
    REMOVE_CERTS=1
  fi
  if [ "$REMOVE_MODELS_SET" != "1" ]; then
    if ask_yes_no "Remove known Ollama models used by TrinaxAI?" n; then
      REMOVE_MODELS=1
    fi
  fi
  if ask_yes_no "Remove Ollama application too?" n; then
    REMOVE_OLLAMA=1
    REMOVE_MODELS=1
  fi
fi

if [ "$STOP_SERVICES" = "1" ]; then
  print_step "Stopping Services"
  if [ "${#PYTHON_CMD[@]}" -gt 0 ] && [ -f "$ROOT/service_manager.py" ]; then
    TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" stop-all --base-dir "$ROOT" || true
  elif [ -f "./shutdown_ai.sh" ]; then
    bash ./shutdown_ai.sh || true
  fi
fi

print_step "Automatic Updates"
if [ "${#PYTHON_CMD[@]}" -gt 0 ] && [ -f "$ROOT/scripts/auto_update.py" ]; then
  "${PYTHON_CMD[@]}" "$ROOT/scripts/auto_update.py" disable --base-dir "$ROOT" || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now trinaxai-update.timer 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/trinaxai-update.timer" "$HOME/.config/systemd/user/trinaxai-update.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi
if [ "$(uname -s)" = "Darwin" ]; then
  launchctl unload "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.update.plist" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.update.plist"
fi
print_ok "Weekly update task removed"

if [ "$DISABLE_AUTOSTART" = "1" ]; then
  print_step "Boot Auto-Start"
  if [ "${#PYTHON_CMD[@]}" -gt 0 ] && [ -f "$ROOT/service_manager.py" ]; then
    TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" disable-autostart --base-dir "$ROOT" || true
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now trinaxai.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/trinaxai.service"
    systemctl --user daemon-reload 2>/dev/null || true
    as_root rm -f /etc/systemd/system/trinaxai.service /etc/systemd/system/ai-rag.service /etc/systemd/system/trinaxai-frontend.service 2>/dev/null || true
    as_root systemctl daemon-reload 2>/dev/null || true
  fi
  if [ "$(uname -s)" = "Darwin" ]; then
    launchctl unload "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist"
  fi
fi

if [ "$REMOVE_CERTS" = "1" ]; then
  if [ "$(uname -s)" = "Darwin" ] && command -v security >/dev/null 2>&1; then
    security delete-certificate -c "TrinaxAI Local HTTPS" "$HOME/Library/Keychains/login.keychain-db" >/dev/null 2>&1 || true
  elif [ "$(uname -s)" = "Linux" ]; then
    as_root rm -f /usr/local/share/ca-certificates/trinaxai-local.crt /etc/pki/ca-trust/source/anchors/trinaxai-local.crt 2>/dev/null || true
    command -v update-ca-certificates >/dev/null 2>&1 && as_root update-ca-certificates >/dev/null 2>&1 || true
    command -v update-ca-trust >/dev/null 2>&1 && as_root update-ca-trust >/dev/null 2>&1 || true
  fi
fi

REMOVE_TARGETS=()
[ "$REMOVE_VENV" = "1" ] && REMOVE_TARGETS+=(".venv")
[ "$REMOVE_FRONTEND" = "1" ] && REMOVE_TARGETS+=("chat-pwa/node_modules" "chat-pwa/dist")
[ "$REMOVE_LOGS" = "1" ] && REMOVE_TARGETS+=("logs")
[ "$REMOVE_ENV" = "1" ] && REMOVE_TARGETS+=(".env")
[ "$REMOVE_DATA" = "1" ] && REMOVE_TARGETS+=("storage" "local_sources")
[ "$REMOVE_CERTS" = "1" ] && REMOVE_TARGETS+=("chat-pwa/certs")

if [ "${#REMOVE_TARGETS[@]}" -gt 0 ]; then
  safe_remove "${REMOVE_TARGETS[@]}"
fi

# Remove only the launcher that belongs to this installation. Never delete a
# different user's command or a regular file with the same name.
CLI_LINK="$HOME/.local/bin/trinaxai"
if [ -L "$CLI_LINK" ]; then
  LINK_TARGET="$(readlink "$CLI_LINK" 2>/dev/null || true)"
  case "$LINK_TARGET" in
    "$ROOT/.venv/bin/trinaxai"|"$ROOT/.venv/Scripts/trinaxai"|"$ROOT/.venv/Scripts/trinaxai.exe")
      rm -f "$CLI_LINK"
      echo "[OK] Removed CLI launcher: $CLI_LINK"
      ;;
  esac
fi
if [ "$REMOVE_VENV" = "1" ]; then
  remove_cli_path_block
fi

if [ "$REMOVE_MODELS" = "1" ] && command -v ollama >/dev/null 2>&1; then
  for model in qwen3.5:9b qwen3.5:4b qwen3.5:2b qwen3.5:0.8b granite4:3b qwen3-vl:4b-instruct qwen3-vl:8b-instruct qwen3:4b-instruct-2507-q4_K_M qwen3:30b-a3b-instruct-2507-q4_K_M qwen2.5-coder:1.5b qwen2.5-coder:3b qwen2.5-coder:7b qwen3-coder:30b llama3.2:1b bge-m3 qwen3-vl:2b qwen3-vl:4b qwen3-vl:8b qwen3-vl:32b qwen2.5-coder:14b llama3.2:3b nomic-embed-text moondream qwen2.5vl:3b qwen2.5vl:7b llava:7b; do
    ollama rm "$model" 2>/dev/null || true
  done
elif [ "$REMOVE_MODELS" = "1" ]; then
  echo "[!] Ollama not found; model removal skipped."
fi

if [ "$REMOVE_OLLAMA" = "1" ]; then
  pkill -TERM -f "ollama" 2>/dev/null || true
  sleep 1
  pkill -KILL -f "ollama" 2>/dev/null || true
  if command -v brew >/dev/null 2>&1; then
    brew uninstall ollama 2>/dev/null || true
  elif command -v apt-get >/dev/null 2>&1; then
    as_root apt-get remove -y ollama 2>/dev/null || true
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf remove -y ollama 2>/dev/null || true
  elif command -v pacman >/dev/null 2>&1; then
    as_root pacman -Rns --noconfirm ollama 2>/dev/null || true
  fi
  if [ -n "${HOME:-}" ] && [ -d "$HOME/.ollama" ]; then
    rm -rf -- "$HOME/.ollama"
  fi
fi

echo "TrinaxAI uninstall finished."
