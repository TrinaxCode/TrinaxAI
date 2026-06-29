#!/usr/bin/env bash
# TrinaxAI updater. Keeps local data, updates code/deps, rebuilds PWA.
set -euo pipefail

usage() {
  cat <<EOF
TrinaxAI Updater

Usage:
  ./update.sh                    Update code, Python deps, and rebuild PWA
  ./update.sh --help             Show this help

What it does:
  1. Creates a backup via backup.sh
  2. Pulls latest code from Git (fast-forward)
  3. Updates Python dependencies from requirements.txt
  4. Rebuilds the PWA frontend (npm install + npm run build)
  5. Runs the pre-release audit (public_readiness.py)

Requirements:
  - Git repository with upstream remote
  - Python virtual environment (.venv)
  - Node.js for PWA rebuild

Environment variables:
  TRINAXAI_PYTHON   Override Python executable path
  TRINAXAI_BACKUP_DIR   Backup directory for pre-update backup
EOF
  exit 0
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "== TrinaxAI update =="

if [ -x "./backup.sh" ]; then
  ./backup.sh create
fi

if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
  git pull --ff-only
else
  echo "[!] Git repository not detected. Download the latest release manually."
fi

PYTHON="${TRINAXAI_PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x ".venv/bin/python" ]; then PYTHON=".venv/bin/python";
  elif [ -x ".venv/Scripts/python.exe" ]; then PYTHON=".venv/Scripts/python.exe";
  else PYTHON="$(command -v python3 || command -v python)";
  fi
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

if [ -d "chat-pwa" ] && command -v npm >/dev/null 2>&1; then
  (cd chat-pwa && npm install && npm run build)
fi

"$PYTHON" scripts/public_readiness.py
echo "Update complete. Restart with ./startup_ai.sh"
