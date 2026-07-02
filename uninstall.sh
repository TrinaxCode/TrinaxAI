#!/usr/bin/env bash
# TrinaxAI uninstaller. Stops services and removes local runtime files.
set -euo pipefail

usage() {
  cat <<EOF
TrinaxAI Uninstaller

Usage:
  ./uninstall.sh                 Interactive uninstall (asks for confirmation)
  ./uninstall.sh --remove-models Also remove Ollama models
  ./uninstall.sh --help          Show this help

What it removes:
  - .venv (Python virtual environment)
  - chat-pwa/node_modules, chat-pwa/dist
  - storage/, local_sources/, logs/
  - Generated .env
  - Systemd units (Linux) or LaunchAgents (macOS)
  - Optional: Ollama models (with --remove-models)

What it keeps:
  - Git repository and source code
  - Shell scripts (backup.sh, update.sh, etc.)
  - certs/, docs/, scripts/
  - Ollama models (unless --remove-models is passed)
EOF
  exit 0
}

REMOVE_MODELS=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --remove-models) REMOVE_MODELS=1; shift;;
    *) echo "Unknown option: $1" >&2; usage;;
  esac
done

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

is_windows() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

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
      "$ROOT"/*|"$ROOT") ;;
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

echo "This will stop TrinaxAI and remove local runtime data from:"
echo "  $ROOT"
echo ""
echo "It will remove .venv, chat-pwa/node_modules, chat-pwa/dist, storage, local_sources, logs, and generated .env."
echo "It will NOT remove Ollama models unless you pass --remove-models."
echo ""
read -r -p "Type UNINSTALL to continue: " confirm
if [ "$confirm" != "UNINSTALL" ]; then
  echo "Cancelled."
  exit 0
fi

if [ "${#PYTHON_CMD[@]}" -gt 0 ] && [ -f "$ROOT/service_manager.py" ]; then
  TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" stop-all --base-dir "$ROOT" || true
  TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" disable-autostart --base-dir "$ROOT" || true
elif [ -f "./shutdown_ai.sh" ]; then
  bash ./shutdown_ai.sh || true
fi

safe_remove .venv chat-pwa/node_modules chat-pwa/dist storage local_sources logs .env

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now trinaxai.service 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/trinaxai.service"
  systemctl --user daemon-reload 2>/dev/null || true
  sudo rm -f /etc/systemd/system/trinaxai.service /etc/systemd/system/ai-rag.service /etc/systemd/system/trinaxai-frontend.service 2>/dev/null || true
  sudo systemctl daemon-reload 2>/dev/null || true
fi

if [ "$(uname -s)" = "Darwin" ]; then
  launchctl unload "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist"
fi

if [ "$REMOVE_MODELS" = "1" ] && command -v ollama >/dev/null 2>&1; then
  for model in qwen2.5-coder:1.5b qwen2.5-coder:3b qwen2.5-coder:7b qwen2.5-coder:14b llama3.2:3b bge-m3 qwen2.5vl:3b qwen2.5vl:7b; do
    ollama rm "$model" 2>/dev/null || true
  done
fi

echo "TrinaxAI local runtime files removed."
