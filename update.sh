#!/usr/bin/env bash
# TrinaxAI updater. Keeps local data, updates code/deps, rebuilds PWA.
set -euo pipefail

LANGUAGE="${TRINAXAI_LANG:-${LANG:-en}}"
LANGUAGE_EXPLICIT="${TRINAXAI_LANG:-}"
LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE" | tr '[:upper:]' '[:lower:]')"
case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
for language_arg in "$@"; do
  case "$language_arg" in
    --language=*|--lang=*) LANGUAGE_EXPLICIT="${language_arg#*=}"; LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE_EXPLICIT" | tr '[:upper:]' '[:lower:]')"; case "$LANGUAGE_LOWER" in es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac ;;
  esac
done
ARG_NONINTERACTIVE=0
for argument in "$@"; do
  case "$argument" in --non-interactive|--yes|-y|--dry-run|--scheduled) ARG_NONINTERACTIVE=1;; esac
done
if [ -z "$LANGUAGE_EXPLICIT" ] && [ "${TRINAXAI_NONINTERACTIVE:-0}" != "1" ] && [ "$ARG_NONINTERACTIVE" != "1" ] && [ "${TRINAXAI_DRY_RUN:-0}" != "1" ] && [ -r /dev/tty ]; then
  read -r -p "Select language / Selecciona idioma [en/es, default: $LANGUAGE]: " language_reply </dev/tty || language_reply=""
  case "$(printf '%s' "$language_reply" | tr '[:upper:]' '[:lower:]')" in es*) LANGUAGE=es ;; en*) LANGUAGE=en ;; esac
  LANGUAGE_EXPLICIT=prompt
fi

GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

if [ "$LANGUAGE" = "es" ]; then
  tr_text_es() {
    case "$1" in
      'TrinaxAI - Smart Update') echo 'Actualización inteligente de TrinaxAI' ;;
      'Source Code') echo 'Código fuente' ;;
      'Backup') echo 'Copia de seguridad' ;;
      'Python Dependencies') echo 'Dependencias de Python' ;;
      'Web App') echo 'Aplicación web' ;;
      'Ollama Models') echo 'Modelos de Ollama' ;;
      'Autostart and Audit') echo 'Inicio automático y auditoría' ;;
      'Restart') echo 'Reinicio' ;;
      'Would download the latest source package from GitHub') echo 'Se descargaría el paquete fuente más reciente desde GitHub' ;;
      'Would create a backup of runtime configuration and data') echo 'Se crearía una copia de la configuración y los datos de ejecución' ;;
      'Would refresh pip, requirements, and the editable CLI') echo 'Se actualizarían pip, requirements y la CLI editable' ;;
      'Would run npm ci and npm run build') echo 'Se ejecutarían npm ci y npm run build' ;;
      'Would check Ollama and pull configured models if requested') echo 'Se comprobaría Ollama y se descargarían los modelos configurados si se solicita' ;;
      'Would change autostart and run readiness checks') echo 'Se cambiaría el inicio automático y se ejecutarían comprobaciones de preparación' ;;
      'Would restart TrinaxAI if requested') echo 'Se reiniciaría TrinaxAI si se solicita' ;;
      'Links to enter') echo 'Enlaces de acceso' ;;
      'LAN / Red local') echo 'LAN' ;;
      'RAG health') echo 'Salud de RAG' ;;
      'DRY-RUN: nothing will be downloaded, installed, or changed.') echo 'SIMULACIÓN: no se descargará, instalará ni modificará nada.' ;;
      'Dry-run finished; no changes were made') echo 'Simulación terminada; no se hicieron cambios' ;;
      'Scheduled maintenance is check-only; no remote code will be executed.') echo 'El mantenimiento programado solo comprueba; no ejecutará código remoto.' ;;
      'Downloading the latest TrinaxAI source package from GitHub…') echo 'Descargando el paquete fuente más reciente de TrinaxAI desde GitHub...' ;;
      'Source package updated') echo 'Paquete fuente actualizado' ;;
      'Weekly automatic maintenance') echo 'Mantenimiento automático semanal' ;;
      'Your data and settings stay untouched') echo 'Tus datos y configuración permanecen intactos' ;;
      'Create a backup before updating?') echo '¿Crear una copia de seguridad antes de actualizar?' ;;
      'Download the latest TrinaxAI version?') echo '¿Descargar la última versión de TrinaxAI?' ;;
      'Remove Ollama application before continuing?') echo '¿Eliminar la aplicación Ollama antes de continuar?' ;;
      'Install Ollama again with the official installer after removal?') echo '¿Instalar Ollama de nuevo con el instalador oficial después de eliminarlo?' ;;
      'Repair/reinstall Ollama with the official installer?') echo '¿Reparar o reinstalar Ollama con el instalador oficial?' ;;
      'Download/update configured Ollama models too?') echo '¿Descargar o actualizar también los modelos configurados de Ollama?' ;;
      'Remove configured Ollama models before model update?') echo '¿Eliminar los modelos configurados de Ollama antes de actualizarlos?' ;;
      'Change boot auto-start setting?') echo '¿Cambiar la configuración de inicio automático?' ;;
      'Enable TrinaxAI when your computer starts?') echo '¿Activar TrinaxAI al iniciar el equipo?' ;;
      'Restart TrinaxAI after the update?') echo '¿Reiniciar TrinaxAI después de actualizar?' ;;
      'Run public readiness audit after updating?') echo '¿Ejecutar la auditoría pública de preparación después de actualizar?' ;;
      'Python environment refreshed') echo 'Entorno Python actualizado' ;;
      'PWA dependencies installed and production build created') echo 'Dependencias PWA instaladas y compilación de producción creada' ;;
      'Update complete. Restart later with ./startup_ai.sh or trinaxai restart.') echo 'Actualización terminada. Reinicia después con ./startup_ai.sh o trinaxai restart.' ;;
      'Settings, indexes, models, and personal data were preserved.') echo 'Se conservaron la configuración, los índices, los modelos y los datos personales.' ;;
      *) echo "$1" ;;
    esac
  }
else
  tr_text_en() { case "$1" in 'LAN / Red local') echo 'LAN' ;; *) echo "$1" ;; esac; }
fi
if [ "$LANGUAGE" = "es" ]; then tr_text() { tr_text_es "$@"; }; else tr_text() { tr_text_en "$@"; }; fi

print_step() { echo -e "\n${BLUE}${BOLD}=== $(tr_text "$1") ===${NC}"; }
print_ok()   { echo -e "  ${GREEN}[OK]${NC} $(tr_text "$1")"; }
print_warn() { echo -e "  ${YELLOW}[!]${NC} $(tr_text "$1")"; }
print_info() { echo -e "  ${CYAN}[i]${NC} $(tr_text "$1")"; }

usage() {
  if [ "$LANGUAGE" = "es" ]; then
    cat <<EOF
Actualizador de TrinaxAI

Uso:
  ./update.sh                    Actualización guiada (pregunta opciones)
  ./update.sh --non-interactive  Actualización automática para CI/scripts
  ./update.sh --no-backup        Omitir backup previo
  ./update.sh --no-pull          Omitir descarga del código
  ./update.sh --models           Descargar/actualizar modelos Ollama configurados
  ./update.sh --no-models        No descargar modelos Ollama
  ./update.sh --remove-models-first Eliminar modelos configurados antes de actualizar
  ./update.sh --repair-ollama    Reinstalar/reparar Ollama antes de actualizar modelos
  ./update.sh --remove-ollama    Eliminar Ollama antes de continuar
  ./update.sh --restart          Reiniciar TrinaxAI después de actualizar
  ./update.sh --no-restart       No reiniciar después de actualizar
  ./update.sh --dry-run         Simular la actualización sin modificar nada
  ./update.sh --enable-autostart Activar arranque automático
  ./update.sh --disable-autostart Desactivar arranque automático
  ./update.sh --no-audit         Omitir readiness audit
  ./update.sh --scheduled        Solo comprobar actualizaciones
  ./update.sh --help             Mostrar esta ayuda

Las tareas obligatorias siguen siendo automáticas: actualizar dependencias Python,
reinstalar la CLI editable, instalar npm y construir la PWA.

TRINAXAI_LANG=es selecciona este idioma; en mantiene la salida inglesa.
EOF
  else
    cat <<EOF
TrinaxAI Updater

Usage:
  ./update.sh                    Guided update (asks optional choices)
  ./update.sh --non-interactive  Automatic update for CI/scripts
  ./update.sh --no-backup        Skip pre-update backup
  ./update.sh --no-pull          Skip the source download
  ./update.sh --models           Pull/update configured Ollama models
  ./update.sh --no-models        Do not pull Ollama models
  ./update.sh --remove-models-first Remove configured models before updating them
  ./update.sh --repair-ollama    Reinstall/repair Ollama before updating models
  ./update.sh --remove-ollama    Remove Ollama before continuing
  ./update.sh --restart          Restart TrinaxAI after update
  ./update.sh --no-restart       Do not restart after update
  ./update.sh --dry-run         Simulate the update without changing anything
  ./update.sh --enable-autostart Enable boot autostart after update
  ./update.sh --disable-autostart Disable boot autostart after update
  ./update.sh --no-audit         Skip public readiness audit
  ./update.sh --scheduled        Check for updates only
  ./update.sh --help             Show this help

Required update work stays automatic: dependency refresh, editable CLI reinstall,
npm ci, and the production PWA build.

TRINAXAI_LANG=es selects Spanish output; en keeps English output.
EOF
  fi
  exit "${1:-0}"
}

INTERACTIVE="${TRINAXAI_INTERACTIVE:-0}"
NONINTERACTIVE="${TRINAXAI_NONINTERACTIVE:-0}"
if [ "$NONINTERACTIVE" = "1" ]; then
  INTERACTIVE=0
fi

CREATE_BACKUP="${TRINAXAI_UPDATE_BACKUP:-1}"
PULL_CODE="${TRINAXAI_UPDATE_PULL:-1}"
RUN_AUDIT="${TRINAXAI_UPDATE_AUDIT:-1}"
DRY_RUN="${TRINAXAI_DRY_RUN:-0}"
SCHEDULED=0

PULL_MODELS="${TRINAXAI_UPDATE_MODELS:-0}"
PULL_MODELS_SET=0
[ -n "${TRINAXAI_UPDATE_MODELS+x}" ] && PULL_MODELS_SET=1
REMOVE_MODELS_FIRST="${TRINAXAI_UPDATE_REMOVE_MODELS:-0}"
REPAIR_OLLAMA="${TRINAXAI_UPDATE_REPAIR_OLLAMA:-0}"
REMOVE_OLLAMA=0
INSTALL_OLLAMA_AFTER_REMOVE=0

RESTART_AFTER="${TRINAXAI_UPDATE_RESTART:-0}"
RESTART_SET=0
[ -n "${TRINAXAI_UPDATE_RESTART+x}" ] && RESTART_SET=1

AUTOSTART_ACTION=""
ROLLBACK_ACTIVE=0

rollback_failed_update() {
  local status=$?
  trap - ERR INT TERM
  if [ "$ROLLBACK_ACTIVE" = "1" ]; then
    print_warn "Update failed; restoring the previously working source tree."
    "${PYTHON_CMD[@]}" "$ROOT/scripts/source_update.py" rollback --root "$ROOT" || true
  fi
  exit "$status"
}

trap rollback_failed_update ERR INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage;;
    --interactive) INTERACTIVE=1; NONINTERACTIVE=0;;
    --non-interactive|--yes|-y) INTERACTIVE=0; NONINTERACTIVE=1;;
    --no-backup) CREATE_BACKUP=0;;
    --no-pull) PULL_CODE=0;;
    --models|--pull-models) PULL_MODELS=1; PULL_MODELS_SET=1;;
    --no-models) PULL_MODELS=0; PULL_MODELS_SET=1;;
    --remove-models-first) REMOVE_MODELS_FIRST=1;;
    --repair-ollama) REPAIR_OLLAMA=1;;
    --remove-ollama) REMOVE_OLLAMA=1;;
    --restart) RESTART_AFTER=1; RESTART_SET=1;;
    --no-restart) RESTART_AFTER=0; RESTART_SET=1;;
    --dry-run) DRY_RUN=1; INTERACTIVE=0; NONINTERACTIVE=1;;
    --enable-autostart) AUTOSTART_ACTION="enable";;
    --disable-autostart) AUTOSTART_ACTION="disable";;
    --keep-autostart) AUTOSTART_ACTION="keep";;
    --no-audit) RUN_AUDIT=0;;
    --scheduled)
      SCHEDULED=1; INTERACTIVE=0; NONINTERACTIVE=1
      PULL_CODE=0; PULL_MODELS=0; PULL_MODELS_SET=1
      RESTART_AFTER=0; RESTART_SET=1; RUN_AUDIT=0
      ;;
    --language|--lang)
      shift
      [ "$#" -gt 0 ] || { echo "--language requires a value" >&2; exit 2; }
      LANGUAGE_EXPLICIT="${1:-}"; LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE_EXPLICIT" | tr '[:upper:]' '[:lower:]')"
      case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
      ;;
    --language=*|--lang=*)
      LANGUAGE_EXPLICIT="${1#*=}"
      [ -n "$LANGUAGE_EXPLICIT" ] || { echo "--language requires a value" >&2; exit 2; }
      LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE_EXPLICIT" | tr '[:upper:]' '[:lower:]')"
      case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
      ;;
    *) echo "$(tr_text "Unknown option: $1")" >&2; usage 2;;
  esac
  shift
done

if [ -z "$LANGUAGE_EXPLICIT" ] && [ "$INTERACTIVE" = "1" ] && [ -r /dev/tty ]; then
  language_reply=""
  read -r -p "Select language / Selecciona idioma [en/es, default: $LANGUAGE]: " language_reply </dev/tty || language_reply=""
  case "$(printf '%s' "$language_reply" | tr '[:upper:]' '[:lower:]')" in es|es-es|es_*) LANGUAGE=es ;; en|en-us|en_*) LANGUAGE=en ;; esac
fi
if [ "$LANGUAGE" = "es" ]; then tr_text() { tr_text_es "$@"; }; else tr_text() { tr_text_en "$@"; }; fi

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
    echo "[!] $(tr_text "No interactive terminal; using default answer for: $prompt")" >&2
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

ROOT="${TRINAXAI_UPDATE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$ROOT"

if [ "$DRY_RUN" = "1" ]; then
  echo -e "${YELLOW}${BOLD}$(tr_text 'DRY-RUN: nothing will be downloaded, installed, or changed.')${NC}"
  print_step "Source Code"
  print_info "Would download the latest source package from GitHub"
  print_step "Backup"
  print_info "Would create a backup of runtime configuration and data"
  print_step "Python Dependencies"
  print_info "Would refresh pip, requirements, and the editable CLI"
  print_step "Web App"
  print_info "Would run npm ci and npm run build"
  print_step "Ollama Models"
  print_info "Would check Ollama and pull configured models if requested"
  print_step "Autostart and Audit"
  print_info "Would change autostart and run readiness checks"
  print_step "Restart"
  print_info "Would restart TrinaxAI if requested"
  echo ""
  echo -e "${BOLD}${CYAN}$(tr_text 'Links to enter')${NC}"
  echo "  Localhost:       https://localhost:3334"
  echo "  $(tr_text 'LAN / Red local'): https://[YOUR-LAN-IP]:3334"
  echo "  $(tr_text 'RAG health'):      https://localhost:3333/health"
  print_ok "Dry-run finished; no changes were made"
  exit 0
fi

is_windows() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

if is_windows && [ -f "$ROOT/update.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-NoProfile" "-ExecutionPolicy" "Bypass" "-File" "$(cygpath -w "$ROOT/update.ps1" 2>/dev/null || printf '%s' "$ROOT/update.ps1")")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$CREATE_BACKUP" = "0" ] && PS_ARGS+=("-NoBackup")
  [ "$PULL_CODE" = "0" ] && PS_ARGS+=("-NoPull")
  if [ "$PULL_MODELS_SET" = "1" ]; then
    [ "$PULL_MODELS" = "1" ] && PS_ARGS+=("-Models") || PS_ARGS+=("-NoModels")
  fi
  [ "$REMOVE_MODELS_FIRST" = "1" ] && PS_ARGS+=("-RemoveModels")
  [ "$REPAIR_OLLAMA" = "1" ] && PS_ARGS+=("-RepairOllama")
  [ "$REMOVE_OLLAMA" = "1" ] && PS_ARGS+=("-RemoveOllama")
  if [ "$RESTART_SET" = "1" ]; then
    [ "$RESTART_AFTER" = "1" ] && PS_ARGS+=("-Restart") || PS_ARGS+=("-NoRestart")
  fi
  case "$AUTOSTART_ACTION" in
    enable) PS_ARGS+=("-EnableAutostart");;
    disable) PS_ARGS+=("-DisableAutostart");;
  esac
  [ "$RUN_AUDIT" = "0" ] && PS_ARGS+=("-NoAudit")
  [ -z "$LANGUAGE_EXPLICIT" ] || PS_ARGS+=("-Language" "$LANGUAGE")
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
else
  echo "[!] Python not found. Set TRINAXAI_PYTHON or create .venv first." >&2
  exit 1
fi

if [ "$SCHEDULED" = "1" ]; then
  print_info "Scheduled maintenance is check-only; no remote code will be executed."
  exec "${PYTHON_CMD[@]}" scripts/auto_update.py run --base-dir "$ROOT"
fi

if [ -f "$ROOT/.trinaxai-update-backup" ]; then
  print_warn "An interrupted source update was found; restoring it before continuing."
  "${PYTHON_CMD[@]}" "$ROOT/scripts/source_update.py" rollback --root "$ROOT"
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
  case " ${MODELS[*]-} " in
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
  if [ "${#MODELS[@]}" -eq 0 ]; then
    MODELS=(qwen3.5:2b qwen3.5:4b qwen3-embedding:0.6b)
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

repair_ollama() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "[!] curl not found; cannot run official Ollama installer."
    return 1
  fi
}

remove_configured_models() {
  configured_models
  if command -v ollama >/dev/null 2>&1; then
    for model in "${MODELS[@]}"; do
      ollama rm "$model" 2>/dev/null || true
    done
  fi
}

remove_ollama_app() {
  pkill -TERM -f "ollama" 2>/dev/null || true
  sleep 1
  pkill -KILL -f "ollama" 2>/dev/null || true
  if command -v brew >/dev/null 2>&1; then
    brew uninstall ollama 2>/dev/null || true
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get remove -y ollama 2>/dev/null || true
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf remove -y ollama 2>/dev/null || true
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Rns --noconfirm ollama 2>/dev/null || true
  fi
  if [ "${HOME:-}" = "/" ] || [ -z "${HOME:-}" ]; then
    echo "[!] HOME is unsafe or unset; Ollama data was not removed."
  elif [ -L "$HOME/.ollama" ]; then
    echo "[!] Ollama data path is a symbolic link; it was not removed."
  else
    rm -rf -- "$HOME/.ollama" 2>/dev/null || true
  fi
}

run_service_manager() {
  local action="$1"
  if [ -f "$ROOT/service_manager.py" ]; then
    TRINAXAI_PRIVILEGED_WRAPPER=1 "${PYTHON_CMD[@]}" "$ROOT/service_manager.py" "$action" --base-dir "$ROOT" || true
  else
    echo "[!] service_manager.py not found; skipped $action."
  fi
}

sync_repository() {
  print_info "Downloading the latest TrinaxAI source package from GitHub…"
  "${PYTHON_CMD[@]}" "$ROOT/scripts/source_update.py" update --root "$ROOT"
  ROLLBACK_ACTIVE=1
  print_ok "Source package updated"
}

export PYTHONDONTWRITEBYTECODE=1

echo -e "\n${BLUE}${BOLD}=== $(tr_text 'TrinaxAI - Smart Update') ===${NC}"
if [ "$SCHEDULED" = "1" ]; then print_info "Weekly automatic maintenance"; else print_info "Your data and settings stay untouched"; fi

if [ "$CREATE_BACKUP" = "1" ]; then
  if ask_yes_no "Create a backup before updating?" y; then
    CREATE_BACKUP=1
  else
    CREATE_BACKUP=0
  fi
fi

if [ "$PULL_CODE" = "1" ]; then
  if ask_yes_no "Download the latest TrinaxAI version?" y; then
    PULL_CODE=1
  else
    PULL_CODE=0
  fi
fi

if [ "$INTERACTIVE" = "1" ]; then
  if ask_yes_no "Remove Ollama application before continuing?" n; then
    REMOVE_OLLAMA=1
    if ask_yes_no "Install Ollama again with the official installer after removal?" y; then
      INSTALL_OLLAMA_AFTER_REMOVE=1
    fi
  elif ask_yes_no "Repair/reinstall Ollama with the official installer?" n; then
    REPAIR_OLLAMA=1
  fi
fi

if [ "$INTERACTIVE" = "1" ] && [ "$PULL_MODELS_SET" != "1" ]; then
  if ask_yes_no "Download/update configured Ollama models too?" n; then
    PULL_MODELS=1
  else
    PULL_MODELS=0
  fi
fi

if [ "$INTERACTIVE" = "1" ]; then
  if ask_yes_no "Remove configured Ollama models before model update?" n; then
    REMOVE_MODELS_FIRST=1
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
  print_step "Backup"
  bash ./backup.sh create
elif [ "$CREATE_BACKUP" = "1" ]; then
  echo "[!] backup.sh not found; refusing an update without the requested backup." >&2
  exit 1
fi

if [ "$PULL_CODE" = "1" ]; then
  print_step "Source Code"
  sync_repository
fi

if [ "$REMOVE_OLLAMA" = "1" ]; then
  remove_ollama_app
  if [ "$INSTALL_OLLAMA_AFTER_REMOVE" = "1" ]; then
    repair_ollama || echo "[!] Ollama reinstall failed."
  else
    PULL_MODELS=0
  fi
elif [ "$REPAIR_OLLAMA" = "1" ]; then
  repair_ollama || echo "[!] Ollama repair failed."
fi

print_step "Python Dependencies"
"${PYTHON_CMD[@]}" -m pip install --upgrade pip
if [ -f requirements.lock ]; then
  "${PYTHON_CMD[@]}" -m pip install --require-hashes -r requirements.lock
else
  "${PYTHON_CMD[@]}" -m pip install -r requirements.txt
fi
"${PYTHON_CMD[@]}" -m pip install -e .
print_ok "Python environment refreshed"

if [ -f "$ROOT/scripts/generate_continue_config.py" ]; then
  "${PYTHON_CMD[@]}" "$ROOT/scripts/generate_continue_config.py" --root "$ROOT" --install-user-config
  print_ok "Continue configuration regenerated"
fi

if [ -d "chat-pwa" ] && [ "${#NPM_CMD[@]}" -gt 0 ]; then
  print_step "Web App"
  if ! (cd chat-pwa && "${NPM_CMD[@]}" ci && "${NPM_CMD[@]}" run build); then
    if is_windows; then
      cat >&2 <<'EOF'
[!] PWA build failed on Windows.
    If the error is "spawn EPERM" and the project is under C:\Windows\System32,
    run this script from an elevated Bash/PowerShell window or move the app to a
    normal user directory such as C:\Users\<you>\TrinaxAI.
EOF
    fi
    exit 1
  fi
  print_ok "PWA dependencies installed and production build created"
elif [ -d "chat-pwa" ]; then
  echo "[!] npm not found; skipped PWA rebuild."
fi

if [ "$PULL_MODELS" = "1" ]; then
  configured_models
  if [ "$REMOVE_MODELS_FIRST" = "1" ]; then
    remove_configured_models
  fi
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
  print_step "Restart"
  run_service_manager stop-all
  run_service_manager start
else
  echo "Update complete. Restart later with ./startup_ai.sh or trinaxai restart."
fi

echo -e "\n${GREEN}${BOLD}✓ TrinaxAI is up to date${NC}"
print_info "Settings, indexes, models, and personal data were preserved."
"${PYTHON_CMD[@]}" "$ROOT/scripts/source_update.py" finish --root "$ROOT"
ROLLBACK_ACTIVE=0
trap - ERR INT TERM
