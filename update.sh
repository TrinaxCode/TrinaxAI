#!/usr/bin/env bash
# TrinaxAI updater. Keeps local data, updates code/deps, rebuilds PWA.
set -euo pipefail

usage() {
  cat <<EOF
TrinaxAI Updater

Usage:
  ./update.sh                    Guided update (asks optional choices)
  ./update.sh --non-interactive  Automatic update for CI/scripts
  ./update.sh --no-backup        Skip pre-update backup
  ./update.sh --no-pull          Skip Git pull
  ./update.sh --models           Pull/update configured Ollama models
  ./update.sh --no-models        Do not pull Ollama models
  ./update.sh --restart          Restart TrinaxAI after update
  ./update.sh --no-restart       Do not restart after update
  ./update.sh --enable-autostart Enable boot autostart after update
  ./update.sh --disable-autostart Disable boot autostart after update
  ./update.sh --no-audit         Skip public readiness audit
  ./update.sh --help             Show this help

What it asks:
  - Create a backup before updating
  - Pull latest code from Git
  - Pull/update configured Ollama models
  - Change boot autostart setting
  - Restart TrinaxAI after update
  - Run the public readiness audit

Required update work stays automatic:
  - Python dependency refresh from requirements.txt
  - Editable CLI reinstall
  - PWA npm install and production build

Environment variables:
  TRINAXAI_PYTHON             Override Python executable path
  TRINAXAI_BACKUP_DIR         Backup directory for pre-update backup
  TRINAXAI_INTERACTIVE=0      Do not ask optional choices
  TRINAXAI_NONINTERACTIVE=1   Do not ask optional choices
  TRINAXAI_UPDATE_BACKUP=0    Skip backup
  TRINAXAI_UPDATE_PULL=0      Skip Git pull
  TRINAXAI_UPDATE_MODELS=1    Pull configured models
  TRINAXAI_UPDATE_RESTART=1   Restart after update
  TRINAXAI_UPDATE_AUDIT=0     Skip readiness audit
EOF
  exit 0
}

INTERACTIVE="${TRINAXAI_INTERACTIVE:-1}"
NONINTERACTIVE="${TRINAXAI_NONINTERACTIVE:-0}"
if [ "$NONINTERACTIVE" = "1" ]; then
  INTERACTIVE=0
fi

CREATE_BACKUP="${TRINAXAI_UPDATE_BACKUP:-1}"
PULL_CODE="${TRINAXAI_UPDATE_PULL:-1}"
RUN_AUDIT="${TRINAXAI_UPDATE_AUDIT:-1}"

PULL_MODELS="${TRINAXAI_UPDATE_MODELS:-0}"
PULL_MODELS_SET=0
[ -n "${TRINAXAI_UPDATE_MODELS+x}" ] && PULL_MODELS_SET=1

RESTART_AFTER="${TRINAXAI_UPDATE_RESTART:-0}"
RESTART_SET=0
[ -n "${TRINAXAI_UPDATE_RESTART+x}" ] && RESTART_SET=1

AUTOSTART_ACTION=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --interactive) INTERACTIVE=1; NONINTERACTIVE=0;;
    --non-interactive|--yes|-y) INTERACTIVE=0; NONINTERACTIVE=1;;
    --no-backup) CREATE_BACKUP=0;;
    --no-pull) PULL_CODE=0;;
    --models|--pull-models) PULL_MODELS=1; PULL_MODELS_SET=1;;
    --no-models) PULL_MODELS=0; PULL_MODELS_SET=1;;
    --restart) RESTART_AFTER=1; RESTART_SET=1;;
    --no-restart) RESTART_AFTER=0; RESTART_SET=1;;
    --enable-autostart) AUTOSTART_ACTION="enable";;
    --disable-autostart) AUTOSTART_ACTION="disable";;
    --keep-autostart) AUTOSTART_ACTION="keep";;
    --no-audit) RUN_AUDIT=0;;
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

env_value() {
  local key="$1"
  [ -f ".env" ] || return 0
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); gsub(/\r$/, ""); print; exit }' .env
}

add_unique_model() {
  local model="$1"
  [ -n "$model" ] || return 0
  case " ${MODELS[*]} " in
    *" $model "*) ;;
    *) MODELS+=("$model");;
  esac
}

configured_models() {
  MODELS=()
  add_unique_model "$(env_value TRINAXAI_MODEL_CODE)"
  add_unique_model "$(env_value TRINAXAI_MODEL_DEEP)"
  add_unique_model "$(env_value TRINAXAI_MODEL_GENERAL)"
  add_unique_model "$(env_value TRINAXAI_MODEL_FAST)"
  add_unique_model "$(env_value TRINAXAI_EMBED)"
  add_unique_model "$(env_value VITE_TRINAXAI_VISION_MODEL)"
  if [ "${#MODELS[@]}" -eq 0 ]; then
    MODELS=(qwen2.5-coder:3b llama3.2:3b bge-m3 qwen2.5vl:3b)
  fi
}

ensure_ollama_running() {
  command -v ollama >/dev/null 2>&1 || return 1
  ollama list >/dev/null 2>&1 && return 0
  mkdir -p "$ROOT/logs"
  nohup ollama serve > "$ROOT/logs/ollama.log" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    sleep 1
    ollama list >/dev/null 2>&1 && return 0
  done
  return 1
}

run_service_manager() {
  local action="$1"
  if [ -f "$ROOT/service_manager.py" ]; then
    TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" "$action" --base-dir "$ROOT" || true
  else
    echo "[!] service_manager.py not found; skipped $action."
  fi
}

export PYTHONDONTWRITEBYTECODE=1

echo "== TrinaxAI guided update =="

if [ "$CREATE_BACKUP" = "1" ]; then
  if ask_yes_no "Create a backup before updating?" y; then
    CREATE_BACKUP=1
  else
    CREATE_BACKUP=0
  fi
fi

if [ "$PULL_CODE" = "1" ]; then
  if ask_yes_no "Pull latest code from Git?" y; then
    PULL_CODE=1
  else
    PULL_CODE=0
  fi
fi

if [ "$INTERACTIVE" = "1" ] && [ "$PULL_MODELS_SET" != "1" ]; then
  if ask_yes_no "Download/update configured Ollama models too?" n; then
    PULL_MODELS=1
  else
    PULL_MODELS=0
  fi
fi

if [ "$INTERACTIVE" = "1" ] && [ -z "$AUTOSTART_ACTION" ]; then
  if ask_yes_no "Change boot auto-start setting?" n; then
    if ask_yes_no "Enable TrinaxAI when your computer starts?" y; then
      AUTOSTART_ACTION="enable"
    else
      AUTOSTART_ACTION="disable"
    fi
  else
    AUTOSTART_ACTION="keep"
  fi
fi

if [ "$INTERACTIVE" = "1" ] && [ "$RESTART_SET" != "1" ]; then
  if ask_yes_no "Restart TrinaxAI after the update?" y; then
    RESTART_AFTER=1
  else
    RESTART_AFTER=0
  fi
fi

if [ "$RUN_AUDIT" = "1" ]; then
  if ask_yes_no "Run public readiness audit after updating?" y; then
    RUN_AUDIT=1
  else
    RUN_AUDIT=0
  fi
fi

if [ "$CREATE_BACKUP" = "1" ] && [ -f "./backup.sh" ]; then
  bash ./backup.sh create || echo "[!] Backup failed; continuing update."
elif [ "$CREATE_BACKUP" = "1" ]; then
  echo "[!] backup.sh not found; backup skipped."
fi

if [ "$PULL_CODE" = "1" ]; then
  if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
    git pull --ff-only
  else
    echo "[!] Git repository not detected. Download the latest release manually."
  fi
fi

echo "== Required dependency refresh =="
"${PYTHON_CMD[@]}" -m pip install --upgrade pip
"${PYTHON_CMD[@]}" -m pip install -r requirements.txt
"${PYTHON_CMD[@]}" -m pip install -e .

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

if [ "$PULL_MODELS" = "1" ]; then
  configured_models
  if ensure_ollama_running; then
    for model in "${MODELS[@]}"; do
      echo "Pulling $model..."
      ollama pull "$model" || echo "[!] Failed to pull $model"
    done
  else
    echo "[!] Ollama is not available; model update skipped."
  fi
fi

case "$AUTOSTART_ACTION" in
  enable) run_service_manager enable-autostart;;
  disable) run_service_manager disable-autostart;;
esac

if [ "$RUN_AUDIT" = "1" ] && [ -f "scripts/public_readiness.py" ]; then
  "${PYTHON_CMD[@]}" scripts/public_readiness.py
elif [ "$RUN_AUDIT" = "1" ]; then
  echo "[!] scripts/public_readiness.py not found; audit skipped."
fi

if [ "$RESTART_AFTER" = "1" ]; then
  run_service_manager stop-all
  run_service_manager start
else
  echo "Update complete. Restart later with ./startup_ai.sh or trinaxai restart."
fi
