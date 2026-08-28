#!/usr/bin/env bash
# TrinaxAI uninstaller. Stops services and removes selected local runtime files.
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
  case "$argument" in --non-interactive|--yes|-y|--dry-run) ARG_NONINTERACTIVE=1;; esac
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
      'TrinaxAI - Clean Uninstaller') echo 'Desinstalador limpio de TrinaxAI' ;;
      'Services and autostart') echo 'Servicios e inicio automático' ;;
      'Automatic updates') echo 'Actualizaciones automáticas' ;;
      'Runtime files') echo 'Archivos de ejecución' ;;
      'Ollama') echo 'Ollama' ;;
      'Would stop services and disable systemd/LaunchAgents/Windows startup') echo 'Se detendrían los servicios y se desactivaría el inicio de systemd/LaunchAgents/Windows' ;;
      'Would disable the weekly update task') echo 'Se desactivaría la tarea semanal de actualización' ;;
      'Would remove .venv, frontend build, and logs (configuration .env is preserved)') echo 'Se eliminarían .venv, la compilación frontend y los logs (la configuración .env se conserva)' ;;
      'Would preserve source code, indexes, models, and personal data by default') echo 'El código fuente, los índices, los modelos y los datos personales se conservarían por defecto' ;;
      'Would remove configured models/app only when explicitly requested') echo 'Solo se eliminarían los modelos o la aplicación configurados si se solicita explícitamente' ;;
      'Links to enter') echo 'Enlaces de acceso' ;;
      'LAN / Red local') echo 'LAN' ;;
      'RAG health') echo 'Salud de RAG' ;;
      'DRY-RUN: nothing will be stopped, removed, or changed.') echo 'SIMULACIÓN: no se detendrá, borrará ni modificará nada.' ;;
      'Dry-run finished; no changes were made') echo 'Simulación terminada; no se hicieron cambios' ;;
      'Location:') echo 'Ubicación:' ;;
      'Protected by default:') echo 'Protegido por defecto:' ;;
      'Cancelled.') echo 'Cancelado.' ;;
      'Non-interactive uninstall requires --yes.') echo 'La desinstalación no interactiva requiere --yes.' ;;
      'Stop running TrinaxAI services now?') echo '¿Detener ahora los servicios activos de TrinaxAI?' ;;
      'Disable TrinaxAI auto-start on boot?') echo '¿Desactivar el inicio automático de TrinaxAI?' ;;
      'Remove Python virtual environment (.venv)?') echo '¿Eliminar el entorno virtual de Python (.venv)?' ;;
      'Remove frontend dependencies/build (chat-pwa/node_modules and dist)?') echo '¿Eliminar las dependencias y compilación frontend (chat-pwa/node_modules y dist)?' ;;
      'Remove logs/?') echo '¿Eliminar logs/?' ;;
      'Remove generated .env configuration and admin token?') echo '¿Eliminar la configuración .env generada y el token de administrador?' ;;
      'Remove RAG index, memory, and local_sources data?') echo '¿Eliminar los datos del índice RAG, la memoria y local_sources?' ;;
      'Remove generated local HTTPS cert files?') echo '¿Eliminar los certificados HTTPS locales generados?' ;;
      'Remove known Ollama models used by TrinaxAI?') echo '¿Eliminar los modelos conocidos de Ollama usados por TrinaxAI?' ;;
      'Remove Ollama application too?') echo '¿Eliminar también la aplicación Ollama?' ;;
      'Stopping Services') echo 'Deteniendo servicios' ;;
      'Automatic Updates') echo 'Actualizaciones automáticas' ;;
      'Boot Auto-Start') echo 'Inicio automático' ;;
      'Weekly update task removed') echo 'Tarea semanal de actualización eliminada' ;;
      'Managed TrinaxAI application files removed') echo 'Archivos gestionados de TrinaxAI eliminados' ;;
      'Application source was kept because this is not a managed installation.') echo 'Se conservó el código de la aplicación porque no es una instalación gestionada.' ;;
      'TrinaxAI uninstall finished.') echo 'Desinstalación de TrinaxAI terminada.' ;;
      *) echo "$1" ;;
    esac
  }
else
  tr_text_en() { case "$1" in 'LAN / Red local') echo 'LAN' ;; *) echo "$1" ;; esac; }
fi
if [ "$LANGUAGE" = "es" ]; then tr_text() { tr_text_es "$@"; }; else tr_text() { tr_text_en "$@"; }; fi

print_step() { echo -e "\n${BLUE}${BOLD}=== $(tr_text "$1") ===${NC}"; }
print_ok() { echo -e "  ${GREEN}[OK]${NC} $(tr_text "$1")"; }
print_warn() { echo -e "  ${YELLOW}[!]${NC} $(tr_text "$1")"; }

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
  if [ "$LANGUAGE" = "es" ]; then
    cat <<EOF
Desinstalador de TrinaxAI

Uso:
  ./uninstall.sh                 Desinstalación guiada (pregunta cada borrado)
  ./uninstall.sh --yes           Desinstalación no interactiva con valores seguros
  ./uninstall.sh --remove-data   También elimina storage RAG y local_sources
  ./uninstall.sh --remove-app    También elimina el código de la instalación gestionada
  ./uninstall.sh --remove-models También elimina modelos Ollama conocidos
  ./uninstall.sh --remove-ollama También elimina la aplicación Ollama
  ./uninstall.sh --purge         Elimina datos, certificados, modelos y Ollama
  ./uninstall.sh --keep-env      Conserva el .env generado (por defecto)
  ./uninstall.sh --remove-env    Elimina el .env generado
  ./uninstall.sh --remove-certs  Elimina certificados HTTPS locales generados
  ./uninstall.sh --dry-run      Simular la desinstalación sin borrar nada
  ./uninstall.sh --help          Mostrar esta ayuda

Siempre conserva el repositorio, código fuente, scripts, documentación, tests y
archivos del proyecto. TRINAXAI_LANG=es selecciona la salida española.
EOF
  else
    cat <<EOF
TrinaxAI Uninstaller

Usage:
  ./uninstall.sh                 Guided uninstall (asks every optional removal)
  ./uninstall.sh --yes           Non-interactive uninstall with safe defaults
  ./uninstall.sh --remove-data   Also remove RAG storage and local_sources
  ./uninstall.sh --remove-app    Also remove the managed application source
  ./uninstall.sh --remove-models Also remove known Ollama models
  ./uninstall.sh --remove-ollama Also remove the Ollama application
  ./uninstall.sh --purge         Remove all generated data, certs, models, and Ollama
  ./uninstall.sh --keep-env      Keep generated .env (default)
  ./uninstall.sh --remove-env    Remove generated .env
  ./uninstall.sh --remove-certs  Remove generated local HTTPS cert files
  ./uninstall.sh --dry-run      Simulate uninstall without deleting anything
  ./uninstall.sh --help          Show this help

The source package, shell scripts, docs, tests and project files are
always kept. TRINAXAI_LANG=es selects Spanish output.
EOF
  fi
  exit "${1:-0}"
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
REMOVE_ENV=0
REMOVE_DATA=0
REMOVE_APP=0
REMOVE_CERTS=0
REMOVE_MODELS=0
REMOVE_MODELS_SET=0
REMOVE_OLLAMA=0
PURGE=0
DRY_RUN="${TRINAXAI_DRY_RUN:-0}"

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
    --remove-app) REMOVE_APP=1;;
    --keep-data) REMOVE_DATA=0;;
    --remove-certs) REMOVE_CERTS=1;;
    --keep-certs) REMOVE_CERTS=0;;
    --remove-models) REMOVE_MODELS=1; REMOVE_MODELS_SET=1;;
    --keep-models) REMOVE_MODELS=0; REMOVE_MODELS_SET=1;;
    --remove-ollama) REMOVE_OLLAMA=1; REMOVE_MODELS=1; REMOVE_MODELS_SET=1;;
    --purge) PURGE=1; REMOVE_DATA=1; REMOVE_CERTS=1; REMOVE_MODELS=1; REMOVE_OLLAMA=1; REMOVE_MODELS_SET=1;;
    --dry-run) DRY_RUN=1; INTERACTIVE=0; NONINTERACTIVE=1; CONFIRM_UNINSTALL=1;;
    --language|--lang)
      shift
      [ "$#" -gt 0 ] || { echo "--language requires a value" >&2; exit 2; }
      LANGUAGE_EXPLICIT="${1:-}"
      LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE_EXPLICIT" | tr '[:upper:]' '[:lower:]')"
      case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
      ;;
    --language=*|--lang=*)
      LANGUAGE_EXPLICIT="${1#*=}"
      [ -n "$LANGUAGE_EXPLICIT" ] || { echo "--language requires a value" >&2; exit 2; }
      LANGUAGE_LOWER="$(printf '%s' "$LANGUAGE_EXPLICIT" | tr '[:upper:]' '[:lower:]')"
      case "$LANGUAGE_LOWER" in es*|*_es*) LANGUAGE=es ;; *) LANGUAGE=en ;; esac
      ;;
    *) echo "Unknown option: $1" >&2; usage 2;;
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

if [ "$DRY_RUN" = "1" ]; then
  echo -e "${YELLOW}${BOLD}$(tr_text 'DRY-RUN: nothing will be stopped, removed, or changed.')${NC}"
  print_step "Services and autostart"
  echo "  $(tr_text 'Would stop services and disable systemd/LaunchAgents/Windows startup')"
  print_step "Automatic updates"
  echo "  $(tr_text 'Would disable the weekly update task')"
  print_step "Runtime files"
  echo "  $(tr_text 'Would remove .venv, frontend build, and logs (configuration .env is preserved)')"
  echo "  $(tr_text 'Would preserve source code, indexes, models, and personal data by default')"
  print_step "Ollama"
  echo "  $(tr_text 'Would remove configured models/app only when explicitly requested')"
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

if is_windows && [ -f "$ROOT/uninstall.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-NoProfile" "-ExecutionPolicy" "Bypass" "-File" "$(cygpath -w "$ROOT/uninstall.ps1" 2>/dev/null || printf '%s' "$ROOT/uninstall.ps1")")
  [ "$CONFIRM_UNINSTALL" = "1" ] && PS_ARGS+=("-Yes")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$STOP_SERVICES" = "0" ] && PS_ARGS+=("-KeepServices")
  [ "$DISABLE_AUTOSTART" = "0" ] && PS_ARGS+=("-KeepAutostart")
  [ "$REMOVE_VENV" = "0" ] && PS_ARGS+=("-KeepVenv")
  [ "$REMOVE_FRONTEND" = "0" ] && PS_ARGS+=("-KeepFrontend")
  [ "$REMOVE_LOGS" = "0" ] && PS_ARGS+=("-KeepLogs")
  [ "$REMOVE_ENV" = "0" ] && PS_ARGS+=("-KeepEnv")
  [ "$REMOVE_ENV" = "1" ] && PS_ARGS+=("-RemoveEnv")
  [ "$REMOVE_DATA" = "1" ] && PS_ARGS+=("-RemoveData")
  [ "$REMOVE_CERTS" = "1" ] && PS_ARGS+=("-RemoveCerts")
  [ "$REMOVE_MODELS" = "1" ] && PS_ARGS+=("-RemoveModels")
  [ "$REMOVE_OLLAMA" = "1" ] && PS_ARGS+=("-RemoveOllama")
  [ "$PURGE" = "1" ] && PS_ARGS+=("-Purge")
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
fi

abs_path() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
  elif command -v realpath >/dev/null 2>&1; then
    # BSD realpath (macOS) has no -m; targets are checked before this call.
    realpath "$1"
  else
    (cd "$(dirname "$1")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "$1")")
  fi
}

safe_remove() {
  local target abs win_path
  for target in "$@"; do
    if [ -L "$target" ]; then
      echo "Refusing to remove a symbolic-link target: $target" >&2
      exit 1
    fi
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

echo -e "\n${BLUE}${BOLD}=== $(tr_text 'TrinaxAI - Clean Uninstaller') ===${NC}"
echo -e "  ${CYAN}$(tr_text 'Location:')${NC} $ROOT"
echo -e "  ${GREEN}$(tr_text 'Protected by default:')${NC} source code, indexes, and Ollama models"
echo ""

if [ "$INTERACTIVE" = "1" ]; then
  confirm="$(ask "Type UNINSTALL to continue:")"
  if [ "$confirm" != "UNINSTALL" ]; then
    echo "$(tr_text 'Cancelled.')"
    exit 0
  fi
elif [ "$CONFIRM_UNINSTALL" != "1" ]; then
  echo "[!] $(tr_text 'Non-interactive uninstall requires --yes.')" >&2
  exit 1
fi

if [ "$INTERACTIVE" = "1" ]; then
  ask_yes_no "Stop running TrinaxAI services now?" y || STOP_SERVICES=0
  ask_yes_no "Disable TrinaxAI auto-start on boot?" y || DISABLE_AUTOSTART=0
  ask_yes_no "Remove Python virtual environment (.venv)?" y || REMOVE_VENV=0
  ask_yes_no "Remove frontend dependencies/build (chat-pwa/node_modules and dist)?" y || REMOVE_FRONTEND=0
  ask_yes_no "Remove logs/?" y || REMOVE_LOGS=0
  ask_yes_no "Remove generated .env configuration and admin token?" n && REMOVE_ENV=1
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
  launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.update.plist" 2>/dev/null || \
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
    launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.trinaxcode.trinaxai.plist" 2>/dev/null || \
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

if [ "$REMOVE_APP" = "1" ]; then
  if [ -f "$ROOT/.trinaxai-managed" ] && [ -f "$ROOT/scripts/source_update.py" ]; then
    "${PYTHON_CMD[@]}" "$ROOT/scripts/source_update.py" remove --root "$ROOT"
    print_ok "Managed TrinaxAI application files removed"
  else
    print_warn "Application source was kept because this is not a managed installation."
  fi
fi

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
  if [ "${HOME:-}" = "/" ] || [ -z "${HOME:-}" ]; then
    print_warn "HOME is unsafe or unset; Ollama data was not removed."
  elif [ -L "$HOME/.ollama" ]; then
    print_warn "Ollama data path is a symbolic link; it was not removed."
  elif [ -d "$HOME/.ollama" ]; then
    rm -rf -- "$HOME/.ollama"
  fi
fi

echo "$(tr_text 'TrinaxAI uninstall finished.')"
