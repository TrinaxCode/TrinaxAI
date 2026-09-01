#!/usr/bin/env bash
# TrinaxAI — One-Command Installer (Linux/macOS/Windows Bash)
# Linux/macOS release-pinned install (replace 1.2.0 with a validated stable release):
#   version="1.2.0"
#   base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
#   installer="$(mktemp)"; manifest="$(mktemp)"
#   curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
#   curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
#   expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
#   if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "A SHA-256 tool (sha256sum or shasum) is required." >&2; exit 2; fi
#   if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Installer SHA-256 verification failed." >&2; exit 1; fi
#   bash -n "$installer" && bash "$installer"
# The SHA-256 check is mandatory; detached GPG verification is optional only
# with a signing-key fingerprint obtained independently (same-release keys are
# not an authenticity anchor; this repository has no pinned trust anchor yet).

set -euo pipefail

SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

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
if [ "$LANGUAGE" = "es" ]; then
  tr_text_es() {
    case "$1" in
      title) echo 'Instalador de TrinaxAI en un comando' ;;
      'TrinaxAI - Local AI Assistant') echo 'TrinaxAI - Asistente de IA local' ;;
      'TrinaxAI is ready!') echo 'TrinaxAI está listo' ;;
      'Installation prepared; TrinaxAI is not running.') echo 'Instalación preparada; TrinaxAI no está en ejecución.' ;;
      usage) echo 'Uso' ;;
      guided) echo 'Instalación guiada (pregunta opciones)' ;;
      automatic) echo 'Instalación automática para CI/scripts' ;;
      skip_models) echo 'Omitir descargas; requiere los modelos configurados ya instalados' ;;
      help) echo 'Mostrar esta ayuda' ;;
      '--install-dir requires a path') echo 'Se requiere una ruta para --install-dir' ;;
      'Unknown option:'*) echo "Opción desconocida:${1#Unknown option:}" ;;
      'Privacy') echo 'Privacidad' ;;
      'Local-first; web search and downloads use the network') echo 'Local-first; la búsqueda web y las descargas usan Internet' ;;
      'Detected RAM') echo 'RAM detectada' ;;
      'Recommended profile') echo 'Perfil recomendado' ;;
      '  1) 8gb     About 8GB RAM') echo '  1) 8gb     Aproximadamente 8 GB de RAM' ;;
      '  2) 16gb    About 16GB RAM') echo '  2) 16gb    Aproximadamente 16 GB de RAM' ;;
      '  3) 32gb    About 32GB RAM or capable GPU') echo '  3) 32gb    Aproximadamente 32 GB o GPU capaz' ;;
      '  4) 64gb    64GB+ RAM or powerful GPU') echo '  4) 64gb    64 GB+ de RAM o GPU potente' ;;
      'Model roles TrinaxAI needs:') echo 'Roles de modelos que necesita TrinaxAI:' ;;
      '  General chat: conversation and everyday questions') echo '  Chat general: conversación y preguntas cotidianas' ;;
      '  Code/deep:    code, reasoning, refactors, project analysis') echo '  Código/profundo: código, razonamiento, refactors y análisis de proyectos' ;;
      '  Embeddings:   RAG indexing and semantic search') echo '  Embeddings: indexación RAG y búsqueda semántica' ;;
      '  Vision:       image and screenshot analysis') echo '  Visión: análisis de imágenes y capturas de pantalla' ;;
      'Deprecated LAN system option ignored; host administration stays localhost-only.') echo 'La opción obsoleta de sistema por LAN se ignora; la administración del host queda solo en localhost.' ;;
      'Links to enter') echo 'Enlaces de acceso' ;;
      'Localhost') echo 'Localhost' ;;
      'LAN / Red local') echo 'LAN' ;;
      'RAG health') echo 'Salud de RAG' ;;
      'Ollama API') echo 'API de Ollama' ;;
      'Quick start') echo 'Inicio rápido' ;;
      'CLI') echo 'CLI' ;;
      'New terminal') echo 'Terminal nueva' ;;
      'Open one if your current shell cannot find the new CLI yet') echo 'Abre una si tu shell actual todavía no encuentra la nueva CLI' ;;
      'Shutdown') echo 'Apagado' ;;
      'System test') echo 'Prueba del sistema' ;;
      'Updates') echo 'Actualizaciones' ;;
      'Automatic check every week') echo 'Comprobación automática semanal' ;;
      'Docs') echo 'Documentación' ;;
      'Same WiFi network required. Check firewall: ports 3333, 3334') echo 'Se requiere la misma red WiFi. Comprueba el firewall: puertos 3333 y 3334' ;;
      'LAN system control remains localhost-only') echo 'El control del sistema por LAN queda restringido a localhost' ;;
      'Star the repo') echo 'Dale una estrella al repositorio' ;;
      '100% open source - AGPL-3.0-or-later') echo '100% código abierto - AGPL-3.0-or-later' ;;
      'DRY-RUN: nothing will be downloaded, installed, or changed.') echo 'SIMULACIÓN: no se descargará, instalará ni modificará nada.' ;;
      '0/6 Repository') echo '0/6 Repositorio' ;;
      '1/6 System Dependencies') echo '1/6 Dependencias del sistema' ;;
      '1.5/6 TrinaxAI Profile') echo '1.5/6 Perfil de TrinaxAI' ;;
      '2/6 Ollama (Local AI Engine)') echo '2/6 Ollama (motor de IA local)' ;;
      '3/6 Python Virtual Environment') echo '3/6 Entorno virtual de Python' ;;
      '4/6 PWA Frontend') echo '4/6 Frontend PWA' ;;
      '5/6 AI Models') echo '5/6 Modelos de IA' ;;
      '6/6 Auto-Start on Boot') echo '6/6 Inicio automático' ;;
      'Would use repository directory:'*) echo "Se usaría el directorio del repositorio:${1#Would use repository directory:}" ;;
      'Source package download simulated') echo 'Descarga del paquete fuente simulada' ;;
      'Would check/install Python 3.10+, Node.js 22+, npm, curl, unzip, and OpenSSL') echo 'Se comprobarían/instalarían Python 3.10+, Node.js 22+, npm, curl, unzip y OpenSSL' ;;
      'Python, Node.js, and system dependency checks simulated') echo 'Comprobaciones de Python, Node.js y dependencias simuladas' ;;
      'Would detect RAM, select a hardware profile, and write .env') echo 'Se detectaría la RAM, se elegiría un perfil de hardware y se escribiría .env' ;;
      'Profile and configuration generation simulated') echo 'Generación de perfil y configuración simulada' ;;
      'Would check Ollama, start it if needed, and verify http://localhost:11434/api/tags') echo 'Se comprobaría Ollama, se iniciaría si hace falta y se verificaría http://localhost:11434/api/tags' ;;
      'Would use the official Ollama installer if ollama is unavailable') echo 'Se usaría el instalador oficial de Ollama si Ollama no está disponible' ;;
      'Ollama availability and fallback checks simulated') echo 'Comprobaciones de Ollama y fallback simuladas' ;;
      'Would create/update .venv and install Python dependencies') echo 'Se crearía/actualizaría .venv y se instalarían las dependencias Python' ;;
      'Python environment changes simulated') echo 'Cambios del entorno Python simulados' ;;
      'Would run npm ci and npm run build') echo 'Se ejecutarían npm ci y npm run build' ;;
      'PWA build simulated') echo 'Compilación de la PWA simulada' ;;
      'Would check Ollama and pull configured models') echo 'Se comprobaría Ollama y se descargarían los modelos configurados' ;;
      'Model checks and downloads simulated') echo 'Comprobaciones y descargas de modelos simuladas' ;;
      'Would optionally start TrinaxAI and configure auto-start/weekly updates') echo 'Se iniciaría TrinaxAI opcionalmente y se configurarían el inicio automático y las actualizaciones semanales' ;;
      'Service and auto-start changes simulated') echo 'Cambios de servicio e inicio automático simulados' ;;
      'Dry-run finished; no changes were made') echo 'Simulación terminada; no se hicieron cambios' ;;
      'CLI PATH saved in '*) echo "PATH de la CLI guardado en ${1#CLI PATH saved in }" ;;
      'Administrator access is required for:'*) echo "Se requieren permisos de administrador para:${1#Administrator access is required for:}" ;;
      'Install the system dependencies manually, then run this installer again.') echo 'Instala las dependencias del sistema manualmente y vuelve a ejecutar este instalador.' ;;
      'Starting Ollama locally...') echo 'Iniciando Ollama localmente...' ;;
      'HTTPS certificate found') echo 'Certificado HTTPS encontrado' ;;
      'LAN IP changed to '*'; renewing the HTTPS certificate...') echo "La IP LAN cambió a ${1#LAN IP changed to }; renovando el certificado HTTPS..." ;;
      'OpenSSL was not found. HTTPS certificate generation skipped.') echo 'No se encontró OpenSSL. Se omitió la generación del certificado HTTPS.' ;;
      'The PWA may run as HTTP or show a browser security warning.') echo 'La PWA puede ejecutarse por HTTP o mostrar una advertencia de seguridad del navegador.' ;;
      'Creating local HTTPS certificate for TrinaxAI...') echo 'Creando certificado HTTPS local para TrinaxAI...' ;;
      'mkcert could not generate HTTPS certificate; trying OpenSSL.') echo 'mkcert no pudo generar el certificado HTTPS; se probará OpenSSL.' ;;
      'Could not generate HTTPS certificate.') echo 'No se pudo generar el certificado HTTPS.' ;;
      'HTTPS certificate generated') echo 'Certificado HTTPS generado' ;;
      'HTTPS certificate trusted in macOS login keychain') echo 'Certificado HTTPS confiado en el llavero de inicio de sesión de macOS' ;;
      'Could not auto-trust the certificate.'*) echo "No se pudo confiar automáticamente en el certificado.${1#Could not auto-trust the certificate.}" ;;
      'HTTPS certificate trusted in system CA store') echo 'Certificado HTTPS confiado en el almacén de CA del sistema' ;;
      'No supported CA trust updater found.'*) echo "No se encontró un actualizador de confianza CA compatible.${1#No supported CA trust updater found.}" ;;
      'Installing packages (Python, Node.js, npm, curl, unzip)...') echo 'Instalando paquetes (Python, Node.js, npm, curl, unzip)...' ;;
      'npm was not installed.'*) echo "npm no se instaló.${1#npm was not installed.}" ;;
      Install\ Node.js\ 22+\ with\ npm\ from\ *) echo "Instala Node.js 22+ con npm desde ${1#Install Node.js 22+ with npm from }" ;;
      'Unknown Linux package manager.'*) echo "Gestor de paquetes de Linux desconocido.${1#Unknown Linux package manager.}" ;;
      'Linux dependencies ready') echo 'Dependencias de Linux listas' ;;
      'Installing Homebrew...') echo 'Instalando Homebrew...' ;;
      'macOS dependencies ready') echo 'Dependencias de macOS listas' ;;
      'Windows detected. Please ensure you have:') echo 'Windows detectado. Asegúrate de tener:' ;;
      'Python 3.10 or newer was not found.') echo 'No se encontró Python 3.10 o posterior.' ;;
      'Node.js 22 or newer is required.'*) echo "Se requiere Node.js 22 o posterior.${1#Node.js 22 or newer is required.}" ;;
      'npm was not found next to Node.js.'*) echo "No se encontró npm junto a Node.js.${1#npm was not found next to Node.js.}" ;;
      'Runtime versions ready:'*) echo "Versiones del entorno listas:${1#Runtime versions ready:}" ;;
      'Unknown TRINAXAI_PROFILE='*) echo "TRINAXAI_PROFILE desconocido; se usará el perfil automático" ;;
      'Automatic setup selected: profile='*) echo "Configuración automática seleccionada: perfil=${1#Automatic setup selected: profile=}" ;;
      'Could not generate admin token.'*) echo "No se pudo generar el token de administrador.${1#Could not generate admin token.}" ;;
      'Admin token generated and saved to .env') echo 'Token de administrador generado y guardado en .env' ;;
      '.env written with profile='*) echo ".env escrito con el perfil ${1#.env written with profile=}" ;;
      'Ollama already installed') echo 'Ollama ya está instalado' ;;
      'Installing Ollama...') echo 'Instalando Ollama...' ;;
      'Download Ollama from:'*) echo "Descarga Ollama desde:${1#Download Ollama from:}" ;;
      'Install Ollama, then re-run this script for full setup.') echo 'Instala Ollama y vuelve a ejecutar este script para completar la configuración.' ;;
      'Continuing with Python and frontend setup...') echo 'Continuando con la configuración de Python y frontend...' ;;
      'Ollama installed') echo 'Ollama instalado' ;;
      'Could not create Python virtual environment.') echo 'No se pudo crear el entorno virtual de Python.' ;;
      'Install Python 3.10+ with venv support, then rerun ./install.sh') echo 'Instala Python 3.10+ con soporte venv y vuelve a ejecutar ./install.sh' ;;
      'Virtual environment exists but activation script was not found.') echo 'Existe el entorno virtual, pero no se encontró su script de activación.' ;;
      'Locked Python packages installed') echo 'Paquetes Python bloqueados instalados' ;;
      'Python packages installed') echo 'Paquetes Python instalados' ;;
      'requirements.txt not found - skipping') echo 'No se encontró requirements.txt; se omite' ;;
      'TrinaxAI CLI installed in editable mode') echo 'CLI de TrinaxAI instalada en modo editable' ;;
      'CLI command linked:'*) echo "Comando CLI enlazado:${1#CLI command linked:}" ;;
      'CLI entry point was not found at '*) echo "No se encontró el punto de entrada de la CLI en ${1#CLI entry point was not found at }" ;;
      'PWA build failed - you can retry with:'*) echo "Falló la compilación de la PWA; puedes reintentarlo con:${1#PWA build failed - you can retry with:}" ;;
      'PWA dependencies installed') echo 'Dependencias de la PWA instaladas' ;;
      Node.js\ not\ found.\ Install\ from\ *) echo "No se encontró Node.js. Instálalo desde ${1#Node.js not found. Install from }" ;;
      'The PWA needs Node.js 22+ to build and serve') echo 'La PWA necesita Node.js 22+ para compilarse y servirse' ;;
      'chat-pwa/ directory not found') echo 'No se encontró el directorio chat-pwa/' ;;
      Only\ *GB\ free.*) echo "Solo queda ${1#Only }; las descargas de modelos pueden fallar; libera espacio antes de descargar modelos grandes." ;;
      Vision\ model\ *\ will\ download\ on\ first\ image\ analysis.) echo "El modelo de visión ${1#Vision model }; se descargará al analizar la primera imagen." ;;
      'Ollama is not available yet; skipping model downloads.'*) echo "Ollama aún no está disponible; se omiten las descargas de modelos. TrinaxAI se instalará de todos modos." ;;
      'After installing/starting Ollama, run:'*) echo "Después de instalar/iniciar Ollama, ejecuta:${1#After installing/starting Ollama, run:}" ;;
      'Skipping model download.'*) echo "Se omite la descarga de modelos. Puedes descargarlos después con:${1#Skipping model download.}" ;;
      'Starting TrinaxAI services...') echo 'Iniciando servicios de TrinaxAI...' ;;
      'Supervisor returned a non-zero status; checking the RAG API directly.') echo 'El supervisor devolvió un estado distinto de cero; se comprobará la API RAG directamente.' ;;
      'TrinaxAI and the RAG API are ready') echo 'TrinaxAI y la API RAG están listas' ;;
      'TrinaxAI did not answer on the health endpoint yet.'*) echo "TrinaxAI aún no responde en el endpoint de salud.${1#TrinaxAI did not answer on the health endpoint yet.}" ;;
      'Start skipped.'*) echo "Inicio omitido.${1#Start skipped.}" ;;
      'Enabling safe weekly updates from GitHub...') echo 'Activando actualizaciones semanales seguras desde GitHub...' ;;
      'Automatic updates enabled (weekly)') echo 'Actualizaciones automáticas activadas (semanales)' ;;
      'Could not enable the weekly task.'*) echo "No se pudo activar la tarea semanal.${1#Could not enable the weekly task.}" ;;
      'Auto-start enabled') echo 'Inicio automático activado' ;;
      'Could not enable auto-start automatically.'*) echo "No se pudo activar el inicio automático.${1#Could not enable auto-start automatically.}" ;;
      'Auto-start skipped because TrinaxAI was not started. Enable it after starting TrinaxAI.') echo 'El inicio automático se omitió porque TrinaxAI no se inició. Actívalo después de iniciar TrinaxAI.' ;;
      'Auto-start skipped.'*) echo "Inicio automático omitido.${1#Auto-start skipped.}" ;;
      *) echo "$1" ;;
    esac
  }
else
  tr_text_en() { case "$1" in title) echo 'TrinaxAI One-Command Installer' ;; usage) echo 'Usage:' ;; guided) echo 'Guided install (asks optional choices)' ;; automatic) echo 'Automatic install for CI/scripts' ;; skip_models) echo 'Skip downloads; requires configured models already installed' ;; help) echo 'Show this help' ;; 'LAN / Red local') echo 'LAN' ;; *) echo "$1" ;; esac; }
fi
if [ "$LANGUAGE" = "es" ]; then
  tr_text() { tr_text_es "$@"; }
else
  tr_text() { tr_text_en "$@"; }
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

usage() {
  if [ "$LANGUAGE" = "es" ]; then
    cat <<EOF
$(tr_text title)

$(tr_text usage):
  ./install.sh                 $(tr_text guided)
  ./install.sh --interactive   $(tr_text guided) (por defecto)
  ./install.sh --non-interactive  $(tr_text automatic)
  ./install.sh --no-models     $(tr_text skip_models)
  ./install.sh --no-vision     Flag de compatibilidad; visión se descarga al usarla
  ./install.sh --no-autostart  No activar el arranque automático
  ./install.sh --no-auto-update No activar la actualización semanal automática
  ./install.sh --no-start      No iniciar TrinaxAI después de instalar
  ./install.sh --dry-run      Simular todos los pasos sin modificar el sistema
  ./install.sh --lan-system    Compatibilidad obsoleta; se ignora y el host sigue siendo solo localhost
  ./install.sh --profile 8gb|16gb|32gb|64gb
  ./install.sh --install-dir PATH  Elegir el directorio de aplicación
  ./install.sh --help          $(tr_text help)

Qué hace:
  1. Instala dependencias del sistema (Python, Node.js, npm, curl, unzip)
  2. Detecta CPU, RAM, GPU y VRAM; recomienda un perfil de hardware
  3. Escribe .env con la IP LAN detectada y la flota de modelos
  4. Instala Ollama si falta
  5. Crea el entorno virtual de Python e instala dependencias
  6. Construye el frontend PWA
  7. Pregunta si debe descargar modelos Ollama recomendados
  8. Pregunta si debe activar el arranque automático e iniciar TrinaxAI
  9. Activa una comprobación semanal segura de GitHub

Variables adicionales: TRINAXAI_PROFILE, TRINAXAI_INTERACTIVE, TRINAXAI_NONINTERACTIVE,
TRINAXAI_INSTALL_MODELS, TRINAXAI_INSTALL_VISION, TRINAXAI_ENABLE_AUTOSTART,
TRINAXAI_ENABLE_AUTO_UPDATE, TRINAXAI_START_NOW, TRINAXAI_ALLOW_LAN_SYSTEM (obsoleta e ignorada),
TRINAXAI_ADMIN_TOKEN, TRINAXAI_HOME y TRINAXAI_LANG.
EOF
  else
    cat <<EOF
$(tr_text title)

$(tr_text usage):
  ./install.sh                 $(tr_text guided)
  ./install.sh --interactive   $(tr_text guided) (default)
  ./install.sh --non-interactive  $(tr_text automatic)
  ./install.sh --no-models     $(tr_text skip_models)
  ./install.sh --no-vision     Compatibility flag; vision downloads on first use
  ./install.sh --no-autostart  Do not enable boot autostart
  ./install.sh --no-auto-update Do not enable the weekly automatic update
  ./install.sh --no-start      Do not start TrinaxAI after install
  ./install.sh --dry-run      Simulate every step without changing the system
  ./install.sh --lan-system    Deprecated compatibility flag; ignored, host administration stays localhost-only
  ./install.sh --profile 8gb|16gb|32gb|64gb
  ./install.sh --install-dir PATH  Choose the application directory
  ./install.sh --help          $(tr_text help)

What it does:
  1. Installs system dependencies (Python, Node.js, npm, curl, unzip)
  2. Detects CPU, RAM, GPU and VRAM; recommends a hardware profile
  3. Writes .env with the detected LAN IP and model fleet
  4. Installs Ollama if missing
  5. Creates the Python virtual environment and installs dependencies
  6. Builds the PWA frontend
  7. Asks whether to pull recommended Ollama models
  8. Asks whether to enable boot autostart and start TrinaxAI
  9. Enables a safe weekly GitHub update check

Additional variables: TRINAXAI_PROFILE, TRINAXAI_INTERACTIVE, TRINAXAI_NONINTERACTIVE,
TRINAXAI_INSTALL_MODELS, TRINAXAI_INSTALL_VISION, TRINAXAI_ENABLE_AUTOSTART,
TRINAXAI_ENABLE_AUTO_UPDATE, TRINAXAI_START_NOW, TRINAXAI_ALLOW_LAN_SYSTEM (deprecated and ignored),
TRINAXAI_ADMIN_TOKEN, TRINAXAI_HOME and TRINAXAI_LANG.
EOF
  fi
  exit "${1:-0}"
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
DRY_RUN="${TRINAXAI_DRY_RUN:-0}"
PROFILE_OVERRIDE="${TRINAXAI_PROFILE:-}"
LEGACY_LAN_SYSTEM_REQUEST=0
if [ "${TRINAXAI_ALLOW_LAN_SYSTEM:-0}" = "1" ]; then LEGACY_LAN_SYSTEM_REQUEST=1; fi
ENABLE_LAN_SYSTEM=0
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
    --dry-run) DRY_RUN=1; INTERACTIVE=0; NONINTERACTIVE=1; INSTALL_MODELS=1;;
    --lan-system) LEGACY_LAN_SYSTEM_REQUEST=1;;
    --profile)
      shift
      [ "$#" -gt 0 ] || { echo "--profile requires a value" >&2; exit 2; }
      PROFILE_OVERRIDE="${1:-}"
      ;;
    --profile=*)
      PROFILE_OVERRIDE="${1#*=}"
      [ -n "$PROFILE_OVERRIDE" ] || { echo "--profile requires a value" >&2; exit 2; }
      ;;
    --install-dir)
      shift
      INSTALL_DIR="${1:-}"
      [ -n "$INSTALL_DIR" ] || { echo "$(tr_text '--install-dir requires a path')" >&2; exit 2; }
      ;;
    --install-dir=*)
      INSTALL_DIR="${1#*=}"
      [ -n "$INSTALL_DIR" ] || { echo "$(tr_text '--install-dir requires a path')" >&2; exit 2; }
      ;;
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
    *)
      echo "$(tr_text "Unknown option: $1")" >&2
      usage 2
      ;;
  esac
  shift
done

if [ -z "$LANGUAGE_EXPLICIT" ] && [ "$INTERACTIVE" = "1" ] && [ -r /dev/tty ]; then
  language_reply=""
  read -r -p "Select language / Selecciona idioma [en/es, default: $LANGUAGE]: " language_reply </dev/tty || language_reply=""
  case "$(printf '%s' "$language_reply" | tr '[:upper:]' '[:lower:]')" in
  es|es-es|es_*) LANGUAGE=es ;;
    en|en-us|en_*) LANGUAGE=en ;;
  esac
fi
if [ "$LANGUAGE" = "es" ]; then
  tr_text() { tr_text_es "$@"; }
else
  tr_text() { tr_text_en "$@"; }
fi

print_header() { echo -e "\n${BLUE}${BOLD}=== $(tr_text "$1") ===${NC}\n"; }
print_ok()    { echo -e "  ${GREEN}[OK]${NC} $(tr_text "$1")"; }
print_warn()  { echo -e "  ${YELLOW}[!]${NC} $(tr_text "$1")"; }
print_err()   { echo -e "  ${RED}[X]${NC} $(tr_text "$1")"; }
print_info()  { echo -e "  ${CYAN}[i]${NC} $(tr_text "$1")"; }
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
  local prompt="$(tr_text "$1")" reply=""
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

hardware_recommendations() {
  "$PYTHON_BIN" - "$1" <<'PY'
import sys

from trinaxai_core import detect_hardware, model_recommendations, select_profile

hardware = detect_hardware()
detected = select_profile(hardware)
requested = sys.argv[1].strip()
profile = requested if requested in {"8gb", "16gb", "32gb", "64gb"} else detected
recommendations = model_recommendations(hardware, profile=profile)
large = profile in {"32gb", "64gb"}
embed = "qwen3-embedding:4b" if large else "qwen3-embedding:0.6b"
embed_dims = "2560" if large else "1024"
embed_batch = "16" if profile == "64gb" else "8" if profile != "8gb" else "1"
embed_keep_alive = "30m" if large else "0s" if profile == "8gb" else "15m"
print("\t".join(
    [
        detected,
        str(round(float(hardware.get("ram", {}).get("total_bytes") or 0) / 1_000_000_000)),
        profile,
        recommendations["general"],
        recommendations["code"],
        recommendations["deep"],
        recommendations["fast"],
        "quality" if large else "balanced",
        embed,
        embed_dims,
        embed_batch,
        embed_keep_alive,
    ]
))
PY
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

env_file_value() {
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
  add_unique_model "$(env_file_value TRINAXAI_MODEL_CODE)"
  add_unique_model "$(env_file_value TRINAXAI_MODEL_DEEP)"
  add_unique_model "$(env_file_value TRINAXAI_MODEL_GENERAL)"
  add_unique_model "$(env_file_value TRINAXAI_MODEL_FAST)"
  add_unique_model "$(env_file_value TRINAXAI_EMBED)"
  if [ "${#MODELS[@]}" -eq 0 ]; then
    MODELS=(qwen3.5:2b qwen3.5:4b qwen3-embedding:0.6b qwen3-embedding:4b)
  fi
}

ollama_model_installed() {
  local model="$1"
  ollama list 2>/dev/null | awk -v model="$model" 'NR > 1 && $1 == model { found=1 } END { exit(found ? 0 : 1) }'
}

verify_models() {
  local model
  for model in "${MODELS[@]}"; do
    if ! ollama_model_installed "$model"; then
      print_err "Required Ollama model is not ready: $model"
      return 1
    fi
  done
}

wait_for_local_url() {
  local url="$1"
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if curl -kfsS --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

smoke_inference() {
  local response
  response="$(curl -kfsS --connect-timeout 3 --max-time 300 \
    -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Reply with the single word OK."}],"stream":false,"mode":"model","think":false}' \
    "$RAG_BASE_URL/v1/chat/completions")" || return 1
  if ! printf '%s' "$response" | "$PYTHON_BIN" -c \
    'import json, sys; data = json.load(sys.stdin); content = data["choices"][0]["message"]["content"]; raise SystemExit(0 if isinstance(content, str) and content.strip() else 1)'; then
    return 1
  fi
}

assert_runtime_ready() {
  local rag_port pwa_port scheme rag_url="" pwa_url=""
  rag_port="${TRINAXAI_PORT:-$(env_file_value TRINAXAI_PORT)}"
  rag_port="${rag_port:-3333}"
  pwa_port="${TRINAXAI_PWA_PORT:-$(env_file_value TRINAXAI_PWA_PORT)}"
  pwa_port="${pwa_port:-3334}"
  for scheme in https http; do
    if wait_for_local_url "$scheme://127.0.0.1:$rag_port/health"; then
      rag_url="$scheme://127.0.0.1:$rag_port"
      break
    fi
  done
  [ -n "$rag_url" ] || { print_err "TrinaxAI backend is not ready on port $rag_port."; return 1; }
  for scheme in https http; do
    if wait_for_local_url "$scheme://127.0.0.1:$pwa_port/"; then
      pwa_url="$scheme://127.0.0.1:$pwa_port"
      break
    fi
  done
  [ -n "$pwa_url" ] || { print_err "TrinaxAI PWA is not ready on port $pwa_port."; return 1; }
  RAG_BASE_URL="$rag_url"
  if ! smoke_inference; then
    print_err "TrinaxAI smoke inference failed."
    return 1
  fi
  print_ok "Backend, PWA, and smoke inference are ready"
}

ensure_https_certificate() {
  mkdir -p "$SCRIPT_DIR/chat-pwa/certs"
  cert_key="$SCRIPT_DIR/chat-pwa/certs/localhost-key.pem"
  cert_file="$SCRIPT_DIR/chat-pwa/certs/localhost.pem"
  cert_crt="$SCRIPT_DIR/chat-pwa/certs/trinaxai-local.crt"
  local_dns="$(hostname 2>/dev/null || echo trinaxai).local"
  if [ -f "$cert_key" ] && [ -f "$cert_file" ]; then
    if { [ -z "${LAN_IP:-}" ] || ! command -v openssl >/dev/null 2>&1 || \
      openssl x509 -in "$cert_file" -noout -ext subjectAltName 2>/dev/null | grep -Fq "IP Address:$LAN_IP"; } && \
      { ! command -v openssl >/dev/null 2>&1 || \
      openssl x509 -in "$cert_file" -noout -ext subjectAltName 2>/dev/null | grep -Fq "DNS:$local_dns"; }; then
      print_ok "HTTPS certificate found"
      return 0
    fi
    print_info "LAN IP changed to $LAN_IP; renewing the HTTPS certificate..."
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    print_warn "OpenSSL was not found. HTTPS certificate generation skipped."
    print_warn "The PWA may run as HTTP or show a browser security warning."
    return 0
  fi
  print_info "Creating local HTTPS certificate for TrinaxAI..."
  san_entries="DNS:localhost,DNS:$(hostname 2>/dev/null || echo trinaxai),DNS:$local_dns,IP:127.0.0.1,IP:::1"
  if [ -n "${LAN_IP:-}" ]; then
    san_entries="$san_entries,IP:$LAN_IP"
  fi
  mkcert_ok=0
  if command -v mkcert >/dev/null 2>&1; then
    mkcert_names=(localhost "$(hostname 2>/dev/null || echo trinaxai)" "$local_dns" 127.0.0.1 ::1)
    if [ -n "${LAN_IP:-}" ]; then
      mkcert_names+=("$LAN_IP")
    fi
    mkcert -cert-file "$cert_file" -key-file "$cert_key" \
      "${mkcert_names[@]}" >/dev/null 2>&1 && mkcert_ok=1 || {
        print_warn "mkcert could not generate HTTPS certificate; trying OpenSSL."
      }
  fi
  if [ "$mkcert_ok" -ne 1 ]; then
    openssl req -x509 -newkey rsa:2048 -sha256 -days 1825 -nodes \
      -keyout "$cert_key" \
      -out "$cert_file" \
      -subj "/CN=TrinaxAI Local HTTPS" \
      -addext "subjectAltName=$san_entries" >/dev/null 2>&1 || {
        print_warn "Could not generate HTTPS certificate."
        return 0
      }
  fi
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
  if command -v python3 >/dev/null 2>&1 &&
    python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null &&
    command -v node >/dev/null 2>&1 &&
    node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' 2>/dev/null &&
    command -v npm >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 &&
    command -v unzip >/dev/null 2>&1 && command -v openssl >/dev/null 2>&1; then
    print_ok "System dependencies already available"
    return 0
  fi
  print_info "Installing packages (Python, Node.js, npm, curl, unzip)..."
  if command -v apt-get >/dev/null 2>&1; then
    as_root apt-get update -qq
    # npm ships with NodeSource/Node.js, but the distro npm package may conflict.
    # Try nodejs + npm together; if that fails, install nodejs alone.
    as_root apt-get install -y python3 python3-pip python3-venv curl unzip ufw openssl
    if ! command -v node >/dev/null 2>&1; then
      as_root apt-get install -y nodejs npm 2>/dev/null || as_root apt-get install -y nodejs || true
    fi
    if ! command -v npm >/dev/null 2>&1; then
      print_warn "npm was not installed. Node.js may be missing or installed from NodeSource."
      print_info "Install Node.js 22+ with npm from https://nodejs.org or use your package manager."
    fi
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf install -y python3 python3-pip nodejs npm curl unzip openssl
  elif command -v pacman >/dev/null 2>&1; then
    as_root pacman -Sy --needed --noconfirm python python-pip nodejs npm curl unzip openssl
  elif command -v zypper >/dev/null 2>&1; then
    as_root zypper --non-interactive install python3 python3-pip nodejs npm curl unzip openssl
  elif command -v apk >/dev/null 2>&1; then
    as_root apk add python3 py3-pip py3-virtualenv nodejs npm curl unzip openssl
  else
    print_warn "Unknown Linux package manager. Install Python 3.10+, pip, venv, Node.js 22+, npm, curl, unzip manually."
  fi
}

OS="unknown"
case "$(uname -s)" in
  Linux*)  OS="linux";;
  Darwin*) OS="macos";;
  MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac

validate_install_dir() {
  case "$INSTALL_DIR" in
    ""|/|.|..|../*|*/../*|*/..|*$'\n'*|*$'\r'*)
      print_err "Refusing an unsafe installation directory: $INSTALL_DIR"
      exit 2
      ;;
  esac
  if [ -L "$INSTALL_DIR" ]; then
    print_err "Installation directory must not be a symbolic link: $INSTALL_DIR"
    exit 2
  fi
  if [ -e "$INSTALL_DIR" ] && [ ! -d "$INSTALL_DIR" ]; then
    print_err "Installation directory is not a directory: $INSTALL_DIR"
    exit 2
  fi
}

validate_source_archive() {
  local archive="$1" listing="$2" normalized_listing types entry root relative top line
  [ -s "$archive" ] || { print_err "Downloaded source package is empty."; return 1; }
  if ! LC_ALL=C tar -tzf "$archive" > "$listing" 2>/dev/null; then
    print_err "Downloaded source package is not a valid gzip-compressed tar archive."
    return 1
  fi
  normalized_listing="${listing}.normalized"
  sed 's:/$::' "$listing" > "$normalized_listing"
  if [ "$(sort "$normalized_listing" | uniq -d | head -n 1)" ]; then
    print_err "Downloaded source package contains duplicate paths."
    return 1
  fi

  root=""
  while IFS= read -r entry || [ -n "$entry" ]; do
    [ -n "$entry" ] || continue
    case "$entry" in
      *$'\r'*|*$'\t'*|/*|\\*|[A-Za-z]:*|../*|*/../*|*/..|..|*//*|./*|*/./*|*/.)
        print_err "Downloaded source package contains an unsafe path: $entry"
        return 1
        ;;
    esac
    top="${entry%%/*}"
    if [ -z "$root" ]; then
      root="$top"
    elif [ "$top" != "$root" ]; then
      print_err "Downloaded source package must contain one source directory."
      return 1
    fi
    if [ "$entry" != "$root" ]; then
      relative="${entry#"$root"/}"
      case "$relative" in
        .env|.env/*|.venv|.venv/*|backups|backups/*|local_sources|local_sources/*|logs|logs/*|storage|storage/*|chat-pwa/certs|chat-pwa/certs/*)
          print_err "Downloaded source package contains runtime data: $entry"
          return 1
          ;;
      esac
    fi
  done < "$normalized_listing"

  case "$root" in TrinaxAI-*) ;; *) print_err "Downloaded source package has an unexpected root directory."; return 1;; esac
  if ! grep -Fqx "$root/pyproject.toml" "$normalized_listing"; then
    print_err "Downloaded source package is missing pyproject.toml."
    return 1
  fi
  types="${listing}.types"
  if ! LC_ALL=C tar -tvzf "$archive" > "$types" 2>/dev/null; then
    print_err "Downloaded source package metadata could not be inspected."
    return 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    case "${line:0:1}" in
      d|-) ;;
      *) print_err "Downloaded source package contains an unsafe link or file type."; return 1;;
    esac
  done < "$types"
  SOURCE_ARCHIVE_ROOT="$root"
}

extract_source_archive() {
  local archive="$1" destination="$2" tar_options=()
  validate_source_archive "$archive" "${archive}.listing"
  mkdir -p "$destination"
  if tar --no-same-owner -tzf "$archive" >/dev/null 2>&1; then
    tar_options+=(--no-same-owner)
  fi
  if tar --no-same-permissions -tzf "$archive" >/dev/null 2>&1; then
    tar_options+=(--no-same-permissions)
  fi
  LC_ALL=C tar "${tar_options[@]}" -xzf "$archive" -C "$destination"
  [ -d "$destination/$SOURCE_ARCHIVE_ROOT" ] || {
    print_err "Downloaded source package has no usable source directory."
    return 1
  }
}

run_dry_run() {
  echo ""
  echo -e "${YELLOW}${BOLD}$(tr_text 'DRY-RUN: nothing will be downloaded, installed, or changed.')${NC}"
  echo ""
  print_header "0/6 Repository"
  print_info "Would use repository directory: ${INSTALL_DIR:-<auto-detected>}"
  print_ok "Source package download simulated"
  print_header "1/6 System Dependencies"
  print_info "Would check/install Python 3.10+, Node.js 22+, npm, curl, unzip, and OpenSSL"
  print_ok "Python, Node.js, and system dependency checks simulated"
  print_header "1.5/6 TrinaxAI Profile"
  print_info "Would detect RAM, select a hardware profile, and write .env"
  print_ok "Profile and configuration generation simulated"
  print_header "2/6 Ollama (Local AI Engine)"
  print_info "Would check Ollama, start it if needed, and verify http://localhost:11434/api/tags"
  print_info "Would use the official Ollama installer if ollama is unavailable"
  print_ok "Ollama availability and fallback checks simulated"
  print_header "3/6 Python Virtual Environment"
  print_info "Would create/update .venv and install Python dependencies"
  print_ok "Python environment changes simulated"
  print_header "4/6 PWA Frontend"
  print_info "Would run npm ci and npm run build"
  print_ok "PWA build simulated"
  print_header "5/6 AI Models"
  print_info "Would check Ollama and pull configured models"
  print_ok "Model checks and downloads simulated"
  print_header "6/6 Auto-Start on Boot"
  print_info "Would optionally start TrinaxAI and configure auto-start/weekly updates"
  print_ok "Service and auto-start changes simulated"
  echo ""
  echo -e "${BOLD}${CYAN}$(tr_text 'Links to enter')${NC}"
  echo "  Localhost:       https://localhost:3334"
  echo "  $(tr_text 'LAN / Red local'): https://[YOUR-LAN-IP]:3334"
  echo "  $(tr_text 'RAG health'):      https://localhost:3333/health"
  echo ""
  print_ok "Dry-run finished; no changes were made"
  return 0
}

if [ "$DRY_RUN" = "1" ]; then
  run_dry_run
  exit 0
fi

if [ -z "$INSTALL_DIR" ]; then
  if [ -f "$HOME/trinaxai/rag_api.py" ]; then
    INSTALL_DIR="$HOME/trinaxai"
  elif [ "$OS" = "macos" ]; then
    INSTALL_DIR="$HOME/Library/Application Support/TrinaxAI"
  else
    INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/trinaxai"
  fi
fi
validate_install_dir

if [ "$OS" = "windows" ] && [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/install.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
  PS_ARGS=("-ExecutionPolicy" "Bypass" "-File" "$(cygpath -w "$SCRIPT_DIR/install.ps1" 2>/dev/null || printf '%s' "$SCRIPT_DIR/install.ps1")")
  [ "$INTERACTIVE" = "1" ] && PS_ARGS+=("-Interactive")
  [ "$NONINTERACTIVE" = "1" ] && PS_ARGS+=("-NonInteractive")
  [ "$INSTALL_MODELS" = "1" ] || PS_ARGS+=("-NoModels")
  [ "$INSTALL_VISION" = "1" ] || PS_ARGS+=("-NoVision")
  [ "$ENABLE_AUTOSTART" = "1" ] || PS_ARGS+=("-NoAutostart")
  [ "$ENABLE_AUTO_UPDATE" = "1" ] || PS_ARGS+=("-NoAutoUpdate")
  [ "$START_NOW" = "1" ] || PS_ARGS+=("-NoStart")
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  [ -z "$LANGUAGE_EXPLICIT" ] || PS_ARGS+=("-Language" "$LANGUAGE")
  [ -z "$INSTALL_DIR" ] || PS_ARGS+=("-InstallDir" "$INSTALL_DIR")
  exec powershell.exe "${PS_ARGS[@]}"
fi

echo ""
echo -e "${BLUE}${BOLD}$(tr_text 'TrinaxAI - Local AI Assistant')${NC}"
echo -e "${BLUE}${BOLD}github.com/TrinaxCode/TrinaxAI${NC}"
echo -e "  ${CYAN}OS:${NC} ${GREEN}${OS}${NC}"
echo -e "  ${CYAN}$(tr_text 'Privacy'):${NC} $(tr_text 'Local-first; web search and downloads use the network')"
echo ""

# Download the source package when running from a piped script.
REPO_DIR="$INSTALL_DIR"
MANAGED_INSTALL=0
if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/rag_api.py" ] || [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
  print_header "0/6 Downloading TrinaxAI"
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
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/trinaxai.XXXXXX")"
    trap 'rm -rf -- "$temp_dir"' EXIT
    release_version="${TRINAXAI_RELEASE_VERSION:-1.2.0}"
    if [ -n "$release_version" ] && [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      print_err "TRINAXAI_RELEASE_VERSION must be a semantic version."
      exit 2
    fi
    source_archive_name="TrinaxAI-${release_version}.tar.gz"
    default_source_archive_url="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${release_version}/${source_archive_name}"
    source_url_override="${TRINAXAI_SOURCE_URL:-}"
    source_archive_url="${source_url_override:-$default_source_archive_url}"
    case "$source_archive_url" in
      https://*) ;;
      *) print_err "Source package URL must use HTTPS."; exit 2 ;;
    esac
    if [ -n "$source_url_override" ]; then
      source_checksum="$(printf '%s' "${TRINAXAI_SOURCE_SHA256:-}" | tr -d '[:space:]')"
      if [ -z "$source_checksum" ]; then
        print_err "TRINAXAI_SOURCE_URL requires TRINAXAI_SOURCE_SHA256."
        exit 2
      fi
    elif [ -n "${TRINAXAI_SOURCE_SHA256:-}" ]; then
      source_checksum="$(printf '%s' "$TRINAXAI_SOURCE_SHA256" | tr -d '[:space:]')"
    else
      source_checksum="$(curl -fsSL --retry 3 --connect-timeout 15 --max-time 60 \
        "https://github.com/TrinaxCode/TrinaxAI/releases/download/v${release_version}/SHA256SUMS" \
        | awk -v asset="$source_archive_name" '$2 == asset || $2 == "*" asset { print $1; exit }')"
    fi
    if [[ ! "$source_checksum" =~ ^[0-9a-fA-F]{64}$ ]]; then
      print_err "Could not obtain a valid SHA-256 for the source package."
      exit 2
    fi
    curl -fsSL --retry 3 --connect-timeout 15 --max-time 300 \
      -o "$temp_dir/trinaxai.tar.gz" "$source_archive_url"
    if command -v sha256sum >/dev/null 2>&1; then
      source_archive_digest="$(sha256sum "$temp_dir/trinaxai.tar.gz" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
      source_archive_digest="$(shasum -a 256 "$temp_dir/trinaxai.tar.gz" | awk '{print $1}')"
    else
      print_err "sha256sum or shasum is required to verify the source package."
      exit 2
    fi
    source_archive_digest="$(printf '%s' "$source_archive_digest" | tr '[:upper:]' '[:lower:]')"
    source_checksum="$(printf '%s' "$source_checksum" | tr '[:upper:]' '[:lower:]')"
    if [ "$source_archive_digest" != "$source_checksum" ]; then
      print_err "The source package failed SHA-256 verification."
      exit 2
    fi
    extract_source_archive "$temp_dir/trinaxai.tar.gz" "$temp_dir/extracted"
    mv "$temp_dir/extracted/$SOURCE_ARCHIVE_ROOT" "$REPO_DIR"
    rm -rf -- "$temp_dir"
    trap - EXIT
    MANAGED_INSTALL=1
    cd "$REPO_DIR"
    print_ok "Repository ready at $REPO_DIR"
  fi
else
  REPO_DIR="$SCRIPT_DIR"
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
  [ -z "$PROFILE_OVERRIDE" ] || PS_ARGS+=("-Profile" "$PROFILE_OVERRIDE")
  [ -z "$LANGUAGE_EXPLICIT" ] || PS_ARGS+=("-Language" "$LANGUAGE")
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
  brew install python@3.11 node curl openssl 2>/dev/null || true
  print_ok "macOS dependencies ready"
elif [ "$OS" = "windows" ]; then
  print_warn "Windows detected. Please ensure you have:"
  print_info "  • Python 3.10+ from https://python.org"
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
if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' 2>/dev/null; then
  print_err "Node.js 22 or newer is required. Install an active Node.js LTS release and run the installer again."
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  print_err "npm was not found next to Node.js. Install the complete Node.js distribution and retry."
  exit 1
fi
print_ok "Runtime versions ready: $($PYTHON_BIN --version 2>&1), Node $(node --version)"

# ── Profile and .env ──
print_header "1.5/6 TrinaxAI Profile"
if ! hardware_data="$(hardware_recommendations "")"; then
  print_err "Could not detect hardware or calculate the recommended profile."
  exit 1
fi
IFS=$'\t' read -r AUTO_PROFILE RAM_GB PROFILE MODEL_GENERAL MODEL_CODE MODEL_DEEP MODEL_FAST EMBED_PRESET EMBED_MODEL EMBED_DIMS EMBED_BATCH EMBED_KEEP_ALIVE <<< "$hardware_data"
echo -e "  ${CYAN}$(tr_text 'Detected RAM'):${NC} ${RAM_GB:-unknown} GB"
echo -e "  ${CYAN}$(tr_text 'Recommended profile'):${NC} ${GREEN}${AUTO_PROFILE}${NC}"
echo ""
if [ -n "$PROFILE_OVERRIDE" ]; then
  case "$PROFILE_OVERRIDE" in
    8gb|16gb|32gb|64gb) PROFILE="$PROFILE_OVERRIDE";;
    *) print_warn "Unknown TRINAXAI_PROFILE=$PROFILE_OVERRIDE; using $AUTO_PROFILE"; PROFILE="$AUTO_PROFILE";;
  esac
elif [ "$INTERACTIVE" = "1" ]; then
  reply=$(ask "Setup mode: Normal recommended or Advanced manual? [N/a]")
  if [[ "$reply" =~ ^[Aa] ]]; then
    echo "$(tr_text '  1) 8gb     About 8GB RAM')"
    echo "$(tr_text '  2) 16gb    About 16GB RAM')"
    echo "$(tr_text '  3) 32gb    About 32GB RAM or capable GPU')"
    echo "$(tr_text '  4) 64gb    64GB+ RAM or powerful GPU')"
    reply=$(ask "Choose profile [default: $AUTO_PROFILE]")
    case "$reply" in
      1|8gb) PROFILE="8gb";;
      2|16gb) PROFILE="16gb";;
      3|32gb) PROFILE="32gb";;
      4|64gb) PROFILE="64gb";;
      "") PROFILE="$AUTO_PROFILE";;
      *) PROFILE="$AUTO_PROFILE";;
    esac
  else
    PROFILE="$AUTO_PROFILE"
  fi
else
  PROFILE="$AUTO_PROFILE"
fi
print_ok "Automatic setup selected: profile=$PROFILE"

if ! hardware_data="$(hardware_recommendations "$PROFILE")"; then
  print_err "Could not calculate model recommendations for profile=$PROFILE."
  exit 1
fi
IFS=$'\t' read -r DETECTED_PROFILE RAM_GB SELECTED_PROFILE MODEL_GENERAL MODEL_CODE MODEL_DEEP MODEL_FAST EMBED_PRESET EMBED_MODEL EMBED_DIMS EMBED_BATCH EMBED_KEEP_ALIVE <<< "$hardware_data"
PROFILE="$SELECTED_PROFILE"
VISION_MODEL="$MODEL_GENERAL"

echo ""
echo -e "${CYAN}$(tr_text 'Model roles TrinaxAI needs:')${NC}"
echo "$(tr_text '  General chat: conversation and everyday questions')"
echo "$(tr_text '  Code/deep:    code, reasoning, refactors, project analysis')"
echo "$(tr_text '  Embeddings:   RAG indexing and semantic search')"
echo "$(tr_text '  Vision:       image and screenshot analysis')"
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

if [ "$LEGACY_LAN_SYSTEM_REQUEST" = "1" ]; then
  print_warn "Deprecated LAN system option ignored; host administration stays localhost-only."
fi
ENABLE_LAN_SYSTEM=0

LAN_IP="$(lan_ip)"
LAN_HOSTNAME="$(hostname 2>/dev/null || echo trinaxai)"
if [ -L .env ]; then
  print_err "Refusing to write .env through a symbolic link."
  exit 1
fi
if [ -f .env ]; then
  print_ok ".env already exists; preserving the existing configuration"
else
  umask 077
  env_tmp="$(mktemp "$SCRIPT_DIR/.env.tmp.XXXXXX")"
  cat > "$env_tmp" <<EOF
# TrinaxAI — Generated configuration ($(date +%Y-%m-%d))
# See .env.example for all available options.

# Profile (auto-detected: $AUTO_PROFILE, RAM: ${RAM_GB:-unknown} GB)
TRINAXAI_HOME="$SCRIPT_DIR"
TRINAXAI_LANG=$LANGUAGE
TRINAXAI_PROFILE=$PROFILE
TRINAXAI_PERFORMANCE_MODE=fast

# Network
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1:11434
TRINAXAI_FRONTEND_URL=https://localhost:3334
TRINAXAI_FRONTEND_MODE=serve
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
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334,https://localhost:3335,http://localhost:3335,https://127.0.0.1:3335,http://127.0.0.1:3335,https://$LAN_HOSTNAME.local:3334,http://$LAN_HOSTNAME.local:3334,https://$LAN_HOSTNAME.local:3335,http://$LAN_HOSTNAME.local:3335${LAN_IP:+,https://$LAN_IP:3334,http://$LAN_IP:3334,https://$LAN_IP:3335,http://$LAN_IP:3335}
TRINAXAI_ALLOW_LAN_SYSTEM=$ENABLE_LAN_SYSTEM
TRINAXAI_ADMIN_TOKEN=$ADMIN_TOKEN

# Indexing
TRINAXAI_INDEX_DIR="$SCRIPT_DIR/local_sources"
EOF
  if [ "$PROFILE" = "64gb" ]; then
    cat >> "$env_tmp" <<'EOF'
TRINAXAI_NUM_CTX=16384
TRINAXAI_EMBED_WORKERS=6
EOF
  elif [ "$PROFILE" = "32gb" ]; then
    cat >> "$env_tmp" <<'EOF'
TRINAXAI_NUM_CTX=8192
TRINAXAI_EMBED_WORKERS=4
EOF
  fi
  chmod 600 "$env_tmp"
  mv -f -- "$env_tmp" .env
  env_tmp=""
  print_ok ".env written with profile=$PROFILE"
fi

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
    print_err "Ollama is not installed. Download it from: https://ollama.com/download/windows"
    exit 1
  fi
  command -v ollama >/dev/null 2>&1 || {
    print_err "Ollama installation completed without a usable ollama command."
    exit 1
  }
  print_ok "Ollama installed"
fi
if ! ensure_ollama_running; then
  print_err "Ollama is not ready on http://localhost:11434."
  exit 1
fi
print_ok "Ollama API ready"

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
  python -m pip install --require-hashes -r requirements.lock
  print_ok "Locked Python packages installed"
elif [ -f "requirements.txt" ]; then
  python -m pip install -r requirements.txt
  print_ok "Python packages installed"
else
  print_warn "requirements.txt not found - skipping"
fi

python -m pip install -e .
print_ok "TrinaxAI CLI installed in editable mode"

if [ -f "$SCRIPT_DIR/scripts/generate_continue_config.py" ]; then
  python "$SCRIPT_DIR/scripts/generate_continue_config.py" --root "$SCRIPT_DIR" --install-user-config
  print_ok "Continue configuration generated for profile=$PROFILE"
fi

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

if [ -d "chat-pwa" ] && [ -f "chat-pwa/package.json" ] && [ -f "chat-pwa/package-lock.json" ]; then
  cd chat-pwa
  if command -v node &>/dev/null && command -v npm &>/dev/null; then
    npm ci --silent 2>/dev/null || npm ci
    if ! npm run build >/dev/null 2>&1 || [ ! -f dist/index.html ]; then
      print_err "PWA build failed - retry with: cd chat-pwa && npm run build"
      exit 1
    fi
    print_ok "PWA build ready"
  else
    print_err "Node.js 22+ and npm are required to build the PWA. Install them from https://nodejs.org"
    exit 1
  fi
  cd ..
else
  print_err "chat-pwa/package.json and package-lock.json are required for the PWA."
  exit 1
fi

# ── 5. Default Models ──
print_header "5/6 AI Models"

DISK_GB="$(free_disk_gb)"
if [ "${DISK_GB:-0}" -gt 0 ] && [ "$DISK_GB" -lt 12 ]; then
  print_warn "Only ${DISK_GB}GB free. Model downloads may fail; free disk space before pulling large models."
fi

configured_models

echo ""
echo -e "${YELLOW}TrinaxAI works best with these models:${NC}"
echo "  General chat:   $MODEL_GENERAL"
echo "  Code/router:    $MODEL_CODE"
echo "  Deep analysis:  $MODEL_DEEP"
echo "  Embeddings:     $EMBED_MODEL"
echo "  Vision (lazy):  $VISION_MODEL"
echo ""

if [ "$INSTALL_MODELS" = "1" ]; then
  if ask_yes_no "Download the configured Ollama models now? Choose N only if they are already installed." y; then
    INSTALL_MODELS=1
  else
    INSTALL_MODELS=0
  fi
fi

if [ "$INSTALL_MODELS" = "1" ]; then
  if ensure_ollama_running; then
    for model in "${MODELS[@]}"; do
      echo "  Pulling $model..."
      if ! ollama pull "$model" || ! ollama_model_installed "$model"; then
        print_err "$model failed"
        exit 1
      fi
      print_ok "$model"
    done

    print_info "Vision model $VISION_MODEL will download on first image analysis."
  else
    print_err "Ollama is not available; required models cannot be prepared."
    exit 1
  fi
else
  print_info "Skipping model downloads; checking the configured models already installed."
fi
if ! ensure_ollama_running || ! verify_models; then
  print_err "Required Ollama models are not ready. Re-run without --no-models or pull the configured models."
  exit 1
fi

# ── 6. Auto-Start Service ──
print_header "6/6 Auto-Start on Boot"

if [ "$START_NOW" = "1" ]; then
  if ask_yes_no "Start TrinaxAI now after install?" y; then
    print_info "Starting TrinaxAI services..."
    if ! python service_manager.py start --base-dir "$SCRIPT_DIR"; then
      print_err "TrinaxAI services failed to start."
      exit 1
    fi
    if ! assert_runtime_ready; then
      exit 1
    fi
  else
    START_NOW=0
    print_info "Start skipped. Run ./startup_ai.sh or trinaxai start when ready."
  fi
fi

if [ "$START_NOW" = "1" ] && [ "$ENABLE_AUTOSTART" = "1" ]; then
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
  print_info "Enabling safe weekly updates from GitHub..."
  python scripts/auto_update.py enable --base-dir "$SCRIPT_DIR" && \
    print_ok "Automatic updates enabled (weekly)" || \
    print_warn "Could not enable the weekly task. Run: python scripts/auto_update.py enable"
fi

if [ "$START_NOW" = "1" ] && [ "$ENABLE_AUTOSTART" = "1" ]; then
  python service_manager.py enable-autostart --base-dir "$SCRIPT_DIR" && \
    print_ok "Auto-start enabled" || \
    print_warn "Could not enable auto-start automatically. Use: python service_manager.py enable-autostart --base-dir \"$SCRIPT_DIR\""
elif [ "$START_NOW" != "1" ]; then
  print_info "Auto-start skipped because TrinaxAI was not started. Enable it after starting TrinaxAI."
else
  print_info "Auto-start skipped. Enable it later in PWA Settings."
fi

# ── Done ──
echo ""
if [ "$START_NOW" = "1" ]; then
  echo -e "${GREEN}${BOLD}$(tr_text 'TrinaxAI is ready!')${NC}"
  echo ""
  echo -e "${BOLD}${CYAN}$(tr_text 'Links to enter')${NC}"
  echo -e "  ${BLUE}$(tr_text 'Localhost'):${NC}     https://localhost:3334"
  if [ -n "${LAN_IP:-}" ]; then
    echo -e "  ${BLUE}$(tr_text 'LAN / Red local'):${NC} https://${LAN_IP}:3334"
  else
    echo -e "  ${BLUE}$(tr_text 'LAN / Red local'):${NC} https://[YOUR-LAN-IP]:3334"
  fi
  echo -e "  ${BLUE}$(tr_text 'RAG health'):${NC}    https://localhost:3333/health"
  echo -e "  ${BLUE}$(tr_text 'Ollama API'):${NC}    http://localhost:11434"
else
  echo -e "${YELLOW}${BOLD}$(tr_text 'Installation prepared; TrinaxAI is not running.')${NC}"
fi
echo ""
echo -e "  ${BLUE}$(tr_text 'Quick start'):${NC}   ./startup_ai.sh"
echo -e "  ${BLUE}$(tr_text 'CLI'):${NC}           trinaxai"
echo -e "  ${BLUE}$(tr_text 'New terminal'):${NC}  $(tr_text 'Open one if your current shell cannot find the new CLI yet')"
echo -e "  ${BLUE}$(tr_text 'Shutdown'):${NC}     ./shutdown_ai.sh"
echo -e "  ${BLUE}$(tr_text 'System test'):${NC}   python test_system.py --verbose"
echo -e "  ${BLUE}$(tr_text 'Updates'):${NC}       $(tr_text 'Automatic check every week')"
echo -e "  ${BLUE}$(tr_text 'Docs'):${NC}         https://github.com/TrinaxCode/TrinaxAI"
echo ""
if [ "$START_NOW" = "1" ]; then
  echo -e "  ($(tr_text 'Same WiFi network required. Check firewall: ports 3333, 3334'))"
  echo ""
fi
echo -e "  ${YELLOW}$(tr_text 'LAN system control remains localhost-only')${NC}"
echo ""
echo -e "  ${YELLOW}$(tr_text 'Star the repo'):${NC} github.com/TrinaxCode/TrinaxAI"
echo -e "  ${GREEN}$(tr_text '100% open source - AGPL-3.0-or-later')${NC}"
echo ""
