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
else
  echo "[!] Python not found. Set TRINAXAI_PYTHON or create .venv first." >&2
  exit 1
fi

NPM_CMD=()
if is_windows && command -v npm.cmd >/dev/null 2>&1; then
  NPM_CMD=(npm.cmd)
elif command -v npm >/dev/null 2>&1; then
  NPM_CMD=(npm)
fi

export PYTHONDONTWRITEBYTECODE=1

echo "== TrinaxAI update =="

if [ -f "./backup.sh" ]; then
  bash ./backup.sh create || echo "[!] Backup failed; continuing update."
fi

if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
  git pull --ff-only
else
  echo "[!] Git repository not detected. Download the latest release manually."
fi

"${PYTHON_CMD[@]}" -m pip install --upgrade pip
"${PYTHON_CMD[@]}" -m pip install -r requirements.txt

if [ -d "chat-pwa" ] && [ "${#NPM_CMD[@]}" -gt 0 ]; then
  if ! (cd chat-pwa && "${NPM_CMD[@]}" install && "${NPM_CMD[@]}" run build); then
    if is_windows; then
      cat >&2 <<'EOF'
[!] PWA build failed on Windows.
    If the error is "spawn EPERM" and the project is under C:\Windows\System32,
    run this script from an elevated Git Bash/PowerShell or move the repo to a
    normal user directory such as C:\Users\<you>\TrinaxAI.
EOF
    fi
    exit 1
  fi
elif [ -d "chat-pwa" ]; then
  echo "[!] npm not found; skipped PWA rebuild."
fi

"${PYTHON_CMD[@]}" scripts/public_readiness.py
echo "Update complete. Restart with ./startup_ai.sh"
