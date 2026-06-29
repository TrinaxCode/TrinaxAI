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

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

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

if [ -x "./shutdown_ai.sh" ]; then
  ./shutdown_ai.sh || true
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl disable --now trinaxai.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/trinaxai.service /etc/systemd/system/ai-rag.service /etc/systemd/system/trinaxai-frontend.service
  sudo systemctl daemon-reload 2>/dev/null || true
fi

if [ "$(uname -s)" = "Darwin" ]; then
  launchctl unload "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist"
fi

rm -rf .venv chat-pwa/node_modules chat-pwa/dist storage local_sources logs .env

if [ "${1:-}" = "--remove-models" ] && command -v ollama >/dev/null 2>&1; then
  for model in qwen2.5-coder:1.5b qwen2.5-coder:3b qwen2.5-coder:7b qwen2.5-coder:14b llama3.2:3b bge-m3 qwen2.5vl:3b qwen2.5vl:7b; do
    ollama rm "$model" 2>/dev/null || true
  done
fi

echo "TrinaxAI local runtime files removed."
