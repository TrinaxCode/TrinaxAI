#!/usr/bin/env bash
# ============================================================
#  TrinaxAI - System setup (run ONCE with sudo)
#
#    sudo ./setup_trinaxai.sh
#
#  Performs 3 tasks:
#   1. Tunes Ollama residency and parallelism for the selected profile.
#   2. Installs a minimal root-owned lifecycle wrapper.
#   3. Enables and restarts the services.
# ============================================================
# Guard: bash is required for brace expansion and arrays.
if [ -z "${BASH_VERSION:-}" ]; then
    echo "ERROR: This script requires bash / Este script requiere bash. Run / ejecuta: bash $0" >&2
    exit 1
fi

set -euo pipefail

LANGUAGE="${TRINAXAI_LANG:-${LANG:-en}}"
if [[ "$LANGUAGE" =~ ^es([_-]|$) ]]; then LANGUAGE=es; else LANGUAGE=en; fi
t() { if [ "$LANGUAGE" = "es" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

fail() {
    echo "[ERROR] $*" >&2
    exit 1
}

on_error() {
    local status=$?
    echo "[ERROR] $(t "Setup failed near line ${BASH_LINENO[0]} while running: ${BASH_COMMAND}" "La configuración falló cerca de la línea ${BASH_LINENO[0]} al ejecutar: ${BASH_COMMAND}")" >&2
    echo "$(t 'Check the command above, fix the reported problem, and run setup again.' 'Comprueba el comando anterior, corrige el problema indicado y vuelve a ejecutar setup.')" >&2
    exit "$status"
}
trap on_error ERR

require_command() {
    local command_name="$1"
    if ! command -v "$command_name" >/dev/null 2>&1; then
        fail "$(t "Required command '$command_name' was not found. Install it and rerun setup." "No se encontró el comando requerido '$command_name'. Instálalo y vuelve a ejecutar setup.")"
    fi
}

run_systemctl() {
    local action="$1"
    shift
    local unit="${*:-systemd}"
    local output
    if ! output="$(systemctl "$action" "$@" 2>&1)"; then
        [ -z "$output" ] || printf '%s\n' "$output" >&2
        fail "$(t "systemctl $action $unit failed. Check: systemctl status $unit and journalctl -u $unit -n 50." "Falló systemctl $action $unit. Comprueba: systemctl status $unit y journalctl -u $unit -n 50.")"
    fi
}

assert_root_path() {
    local path="$1"
    local expected_mode="$2"
    local kind="${3:-file}"
    local metadata
    if [ -L "$path" ]; then
        fail "$(t "Refusing symlink where a root-owned $kind is required: $path" "Se rechaza un enlace simbólico donde se requiere un $kind propiedad de root: $path")"
    fi
    if [ "$kind" = "directory" ]; then
        [ -d "$path" ] || fail "$(t "Required directory was not created: $path" "No se creó el directorio requerido: $path")"
    else
        [ -f "$path" ] || fail "$(t "Required file was not created: $path" "No se creó el archivo requerido: $path")"
    fi
    if ! metadata="$(stat -c '%u:%g %a' "$path" 2>/dev/null)"; then
        fail "$(t "Could not inspect permissions for $path. Check the filesystem and rerun setup." "No se pudieron inspeccionar los permisos de $path. Comprueba el sistema de archivos y vuelve a ejecutar setup.")"
    fi
    if [ "$metadata" != "0:0 $expected_mode" ]; then
        fail "$(t "$path must be owned by root:root with mode $expected_mode (found $metadata)." "$path debe pertenecer a root:root con modo $expected_mode (se encontró $metadata).")"
    fi
}

wait_for_local_url() {
    local url="$1"
    for _ in {1..20}; do
        if curl -kfsS --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# OS detection: this script is Linux-only (systemd, sudoers, etc.)
if [ "$(uname -s)" != "Linux" ]; then
    echo "$(t 'ERROR: setup_trinaxai.sh is Linux-only (systemd).' 'ERROR: setup_trinaxai.sh solo funciona en Linux (systemd).')"
    echo "$(t 'For macOS, use install.sh then start services manually.' 'En macOS, usa install.sh y luego inicia los servicios manualmente.')"
    echo "$(t 'For Windows, use install.ps1 then start services manually.' 'En Windows, usa install.ps1 y luego inicia los servicios manualmente.')"
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "$(t 'Run with sudo: sudo ./setup_trinaxai.sh' 'Ejecuta con sudo: sudo ./setup_trinaxai.sh')"
    exit 1
fi

USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
for required_command in awk cat chown chmod curl install npm ollama stat sudo systemctl visudo; do
    require_command "$required_command"
done
if ! id "$USER_NAME" >/dev/null 2>&1; then
    fail "$(t "The service account '$USER_NAME' does not exist. Run setup with sudo from the intended user account." "La cuenta de servicio '$USER_NAME' no existe. Ejecuta setup con sudo desde la cuenta de usuario correcta.")"
fi
if [[ "$USER_NAME" =~ [^a-zA-Z0-9._-] ]]; then
    fail "$(t "The service account '$USER_NAME' contains unsupported characters; refusing to write sudoers." "La cuenta de servicio '$USER_NAME' contiene caracteres no permitidos; no se escribirá sudoers.")"
fi
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    fail "$(t 'Python is required for the functional smoke test. Install Python 3 and rerun setup.' 'Python es necesario para la prueba funcional. Instala Python 3 y vuelve a ejecutar setup.')"
fi
BASH_BIN="$(command -v bash)"
NPM_BIN="$(command -v npm)"
PROFILE=""
if [ -f "$PROJ/.env" ]; then
    if ! PROFILE="$(awk -F= '/^TRINAXAI_PROFILE=/{value=$0; sub(/^[^=]*=/, "", value)} END {print value}' "$PROJ/.env")"; then
        fail "$(t "Could not read $PROJ/.env to determine the profile. Check its permissions and rerun setup." "No se pudo leer $PROJ/.env para determinar el perfil. Comprueba sus permisos y vuelve a ejecutar setup.")"
    fi
fi
PROFILE="${PROFILE:-16gb}"
LEGACY_8GB_PROFILE="$(printf '\154\157\167')"
if [ "$PROFILE" = "$LEGACY_8GB_PROFILE" ]; then PROFILE="8gb"; fi

echo -e "${BLUE}[1/4]${NC} $(t 'Tuning Ollama (systemd override)...' 'Optimizando Ollama (override de systemd)...')"
OLLAMA_OVERRIDE_DIR=/etc/systemd/system/ollama.service.d
OLLAMA_OVERRIDE_FILE=$OLLAMA_OVERRIDE_DIR/override.conf
if ! install -d -o root -g root -m 0755 "$OLLAMA_OVERRIDE_DIR"; then
    fail "$(t "Could not create $OLLAMA_OVERRIDE_DIR. Check root filesystem permissions and disk space." "No se pudo crear $OLLAMA_OVERRIDE_DIR. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
assert_root_path "$OLLAMA_OVERRIDE_DIR" 755 directory
MAX_LOADED_MODELS=2
NUM_PARALLEL=4
if [ "$PROFILE" = "8gb" ]; then
    MAX_LOADED_MODELS=1
    NUM_PARALLEL=1
fi
if ! cat > "$OLLAMA_OVERRIDE_FILE" <<EOF
[Service]
# Mantener el modelo en RAM 30 min (respuestas rápidas, sin recargar 3GB).
Environment="OLLAMA_KEEP_ALIVE=30m"
# 8 GB carga uno; perfiles mayores admiten embedder + generador.
Environment="OLLAMA_MAX_LOADED_MODELS=$MAX_LOADED_MODELS"
# Paralelismo para indexado rápido (python index.py) y varias peticiones.
Environment="OLLAMA_NUM_PARALLEL=$NUM_PARALLEL"
# Ollama nunca se publica directamente en la LAN. La PWA usa el gateway
# autenticado de TrinaxAI, que aplica límites y una allowlist de operaciones.
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_ORIGINS=http://localhost:3334,http://127.0.0.1:3334"
EOF
then
    fail "$(t "Could not write $OLLAMA_OVERRIDE_FILE. Check root filesystem permissions and disk space." "No se pudo escribir $OLLAMA_OVERRIDE_FILE. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
if ! chown root:root "$OLLAMA_OVERRIDE_FILE" || ! chmod 0644 "$OLLAMA_OVERRIDE_FILE"; then
    fail "$(t "Could not secure $OLLAMA_OVERRIDE_FILE as root:root mode 0644." "No se pudo asegurar $OLLAMA_OVERRIDE_FILE como root:root con modo 0644.")"
fi
assert_root_path "$OLLAMA_OVERRIDE_FILE" 644
echo -e "      ${GREEN}[OK]${NC} $(t 'override.conf updated' 'override.conf actualizado')"

echo -e "${BLUE}[2/4]${NC} $(t 'Installing the secure PWA lifecycle wrapper...' 'Instalando el wrapper seguro de lifecycle para la PWA...')"
LIFECYCLE_DIR=/usr/local/libexec/trinaxai
LIFECYCLE_WRAPPER=$LIFECYCLE_DIR/trinaxai-lifecycle
if ! install -d -o root -g root -m 0755 "$LIFECYCLE_DIR"; then
    fail "$(t "Could not create $LIFECYCLE_DIR. Check root filesystem permissions and disk space." "No se pudo crear $LIFECYCLE_DIR. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
assert_root_path "$LIFECYCLE_DIR" 755 directory
if ! cat > "$LIFECYCLE_WRAPPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  start-ai)
    systemctl enable ollama.service ai-rag.service >/dev/null
    systemctl start ollama.service ai-rag.service trinaxai-frontend.service
    ;;
  stop-ai)
    systemctl disable --now ai-rag.service ollama.service >/dev/null
    ;;
  start-all)
    systemctl enable ollama.service ai-rag.service trinaxai-frontend.service >/dev/null
    systemctl start ollama.service ai-rag.service trinaxai-frontend.service
    ;;
  stop-all)
    systemctl disable --now ai-rag.service ollama.service trinaxai-frontend.service >/dev/null
    ;;
  reload-network)
    systemctl restart ai-rag.service trinaxai-frontend.service
    ;;
  *)
    echo "usage / uso: trinaxai-lifecycle {start-ai|stop-ai|start-all|stop-all|reload-network}" >&2
    exit 2
    ;;
esac
EOF
then
    fail "$(t "Could not write $LIFECYCLE_WRAPPER. Check root filesystem permissions and disk space." "No se pudo escribir $LIFECYCLE_WRAPPER. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
if ! chown root:root "$LIFECYCLE_WRAPPER" || ! chmod 0755 "$LIFECYCLE_WRAPPER"; then
    fail "$(t "Could not secure $LIFECYCLE_WRAPPER as root:root mode 0755." "No se pudo asegurar $LIFECYCLE_WRAPPER como root:root con modo 0755.")"
fi
assert_root_path "$LIFECYCLE_WRAPPER" 755
SUDOERS_FILE=/etc/sudoers.d/trinaxai
if ! cat > "$SUDOERS_FILE" <<EOF
# Wrapper fijo, propiedad de root, con argumentos exactos. El repositorio y
# sus scripts nunca se ejecutan como root.
$USER_NAME ALL=(root) NOPASSWD: $LIFECYCLE_WRAPPER start-ai, $LIFECYCLE_WRAPPER stop-ai, $LIFECYCLE_WRAPPER start-all, $LIFECYCLE_WRAPPER stop-all, $LIFECYCLE_WRAPPER reload-network
EOF
then
    fail "$(t "Could not write $SUDOERS_FILE. Check root filesystem permissions and disk space." "No se pudo escribir $SUDOERS_FILE. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
if ! chown root:root "$SUDOERS_FILE" || ! chmod 0440 "$SUDOERS_FILE"; then
    fail "$(t "Could not secure $SUDOERS_FILE as root:root mode 0440." "No se pudo asegurar $SUDOERS_FILE como root:root con modo 0440.")"
fi
# Validar sintaxis sudoers; si falla, eliminar para no romper sudo.
if visudo -cf "$SUDOERS_FILE" >/dev/null 2>&1; then
    echo -e "      ${GREEN}[OK]${NC} $(t 'sudoers is valid' 'sudoers válido')"
else
    if ! rm -f "$SUDOERS_FILE"; then
        fail "$(t "Invalid sudoers and the file could not be removed: $SUDOERS_FILE." "sudoers inválido y no se pudo eliminar el archivo: $SUDOERS_FILE.")"
    fi
    echo "      [ERROR] $(t 'Invalid sudoers; reverted. Aborting.' 'sudoers inválido; revertido. Abortando.')"
    exit 1
fi
assert_root_path "$SUDOERS_FILE" 440

echo -e "${BLUE}[3/4]${NC} $(t 'Enabling services...' 'Habilitando servicios...')"
RAG_SERVICE_FILE=/etc/systemd/system/ai-rag.service
FRONTEND_SERVICE_FILE=/etc/systemd/system/trinaxai-frontend.service
if ! cat > "$RAG_SERVICE_FILE" <<EOF
[Unit]
Description=TrinaxAI RAG API
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJ
EnvironmentFile=-$PROJ/.env
ExecStart=$BASH_BIN -lc 'cd "$PROJ" && source .venv/bin/activate && if [ "\${TRINAXAI_RAG_HTTPS:-1}" != "0" ] && [ "\${TRINAXAI_RAG_HTTPS:-1}" != "false" ] && [ -f "$PROJ/chat-pwa/certs/localhost-key.pem" ] && [ -f "$PROJ/chat-pwa/certs/localhost.pem" ]; then exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333} --ssl-keyfile "$PROJ/chat-pwa/certs/localhost-key.pem" --ssl-certfile "$PROJ/chat-pwa/certs/localhost.pem"; else exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333}; fi'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
then
    fail "$(t "Could not write $RAG_SERVICE_FILE. Check root filesystem permissions and disk space." "No se pudo escribir $RAG_SERVICE_FILE. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
if ! chown root:root "$RAG_SERVICE_FILE" || ! chmod 0644 "$RAG_SERVICE_FILE"; then
    fail "$(t "Could not secure $RAG_SERVICE_FILE as root:root mode 0644." "No se pudo asegurar $RAG_SERVICE_FILE como root:root con modo 0644.")"
fi
assert_root_path "$RAG_SERVICE_FILE" 644

if ! cat > "$FRONTEND_SERVICE_FILE" <<EOF
[Unit]
Description=TrinaxAI Frontend PWA
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJ/chat-pwa
EnvironmentFile=-$PROJ/.env
Environment="NODE_ENV=production"
ExecStart=$NPM_BIN run preview
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
then
    fail "$(t "Could not write $FRONTEND_SERVICE_FILE. Check root filesystem permissions and disk space." "No se pudo escribir $FRONTEND_SERVICE_FILE. Comprueba los permisos del sistema de archivos y el espacio en disco.")"
fi
if ! chown root:root "$FRONTEND_SERVICE_FILE" || ! chmod 0644 "$FRONTEND_SERVICE_FILE"; then
    fail "$(t "Could not secure $FRONTEND_SERVICE_FILE as root:root mode 0644." "No se pudo asegurar $FRONTEND_SERVICE_FILE como root:root con modo 0644.")"
fi
assert_root_path "$FRONTEND_SERVICE_FILE" 644

run_systemctl daemon-reload
run_systemctl enable ollama.service
run_systemctl restart ollama.service
# Esperar a Ollama
if ! wait_for_local_url http://127.0.0.1:11434/api/tags; then
    fail "$(t 'Ollama did not become ready on http://127.0.0.1:11434. Check: systemctl status ollama.service and journalctl -u ollama.service -n 50.' 'Ollama no estuvo listo en http://127.0.0.1:11434. Comprueba: systemctl status ollama.service y journalctl -u ollama.service -n 50.')"
fi
# Asegurar la flota de modelos (auto-router + embeddings + visión).
echo -e "      ${BLUE}[>]${NC} $(t 'Checking models (downloading missing ones)...' 'Verificando modelos (descargando los que falten)...')"
if [ "$PROFILE" = "8gb" ]; then
    MODELS=(qwen3-embedding:0.6b qwen3.5:2b)
elif [ "$PROFILE" = "64gb" ]; then
    MODELS=(qwen3-embedding:4b qwen3.5:4b qwen3.5:35b qwen3-coder:30b)
elif [ "$PROFILE" = "32gb" ]; then
    MODELS=(qwen3-embedding:4b qwen3.5:4b qwen3.5:9b)
else
    # 16gb (default)
    MODELS=(qwen3-embedding:0.6b qwen3.5:2b qwen3.5:4b)
fi
ollama_models() {
    sudo -u "$USER_NAME" ollama list 2>&1
}

model_is_installed() {
    local model="$1"
    local model_list="$2"
    awk -v model="$model" '$1 == model { found=1 } END { exit(found ? 0 : 1) }' <<< "$model_list"
}

ensure_model() {
    local model="$1"
    local model_list
    if ! model_list="$(ollama_models)"; then
        [ -z "$model_list" ] || printf '%s\n' "$model_list" >&2
        fail "$(t "Could not list Ollama models for '$model'. Check: sudo -u $USER_NAME ollama list." "No se pudieron listar los modelos de Ollama para '$model'. Comprueba: sudo -u $USER_NAME ollama list.")"
    fi
    if model_is_installed "$model" "$model_list"; then
        return 0
    fi
    echo -e "        -> $model"
    if ! sudo -u "$USER_NAME" ollama pull "$model"; then
        fail "$(t "Failed to pull required model '$model'. Check internet, disk space, and Ollama permissions; then retry: sudo -u $USER_NAME ollama pull $model." "Falló la descarga del modelo requerido '$model'. Comprueba Internet, espacio en disco y permisos de Ollama; luego reintenta: sudo -u $USER_NAME ollama pull $model.")"
    fi
    if ! model_list="$(ollama_models)"; then
        [ -z "$model_list" ] || printf '%s\n' "$model_list" >&2
        fail "$(t "The pull finished but Ollama could not list '$model'. Check: sudo -u $USER_NAME ollama list." "La descarga terminó pero Ollama no pudo listar '$model'. Comprueba: sudo -u $USER_NAME ollama list.")"
    fi
    if ! model_is_installed "$model" "$model_list"; then
        fail "$(t "Ollama pull reported success but required model '$model' is still missing. Retry: sudo -u $USER_NAME ollama pull $model." "Ollama indicó éxito pero el modelo requerido '$model' aún falta. Reintenta: sudo -u $USER_NAME ollama pull $model.")"
    fi
}

for m in "${MODELS[@]}"; do
    ensure_model "$m"
done
echo -e "      ${GREEN}[OK]${NC} $(t 'models ready' 'modelos listos')"

run_systemctl enable ai-rag.service
run_systemctl restart ai-rag.service
run_systemctl enable trinaxai-frontend.service
run_systemctl restart trinaxai-frontend.service
echo -e "      ${GREEN}[OK]${NC} $(t 'ollama + ai-rag + frontend restarted' 'ollama + ai-rag + frontend reiniciados')"

echo -e "${BLUE}[4/4]${NC} $(t 'Verifying...' 'Verificando...')"
sleep 2
ok=true
failed_services=()
for s in ollama ai-rag trinaxai-frontend; do
    if systemctl is-active --quiet "$s.service"; then
        echo -e "      ${GREEN}[OK]${NC} $s $(t 'active' 'activo')"
    else
        echo "      [!] $s $(t 'NOT active' 'NO activo')"
        ok=false
        failed_services+=("$s.service")
    fi
done

echo ""
if [ "$ok" != true ]; then
    fail "$(t "Required services are not active: ${failed_services[*]}. Check systemctl status and journalctl -u for the failed unit(s)." "Los servicios requeridos no están activos: ${failed_services[*]}. Comprueba systemctl status y journalctl -u para las unidades fallidas.")"
fi

env_value() {
    local key="$1"
    [ -f "$PROJ/.env" ] || return 0
    awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); gsub(/\r$/, ""); print; exit }' "$PROJ/.env"
}

valid_port() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$1" -ge 1 ] 2>/dev/null && [ "$1" -le 65535 ] 2>/dev/null
}

smoke_inference() {
    local response
    if ! response="$(curl -kfsS --connect-timeout 3 --max-time 300 \
        -H 'Content-Type: application/json' \
        -d '{"messages":[{"role":"user","content":"Reply with the single word OK."}],"stream":false,"mode":"model","think":false}' \
        "$RAG_BASE_URL/v1/chat/completions" 2>&1)"; then
        [ -z "$response" ] || printf '%s\n' "$response" >&2
        return 1
    fi
    if ! printf '%s' "$response" | "$PYTHON_BIN" -c \
        'import json, sys; data = json.load(sys.stdin); content = data["choices"][0]["message"]["content"]; raise SystemExit(0 if isinstance(content, str) and content.strip() else 1)'; then
        return 1
    fi
}

assert_runtime_ready() {
    local rag_port pwa_port scheme rag_url="" pwa_url=""
    rag_port="${TRINAXAI_PORT:-$(env_value TRINAXAI_PORT)}"
    rag_port="${rag_port:-3333}"
    pwa_port="${TRINAXAI_PWA_PORT:-$(env_value TRINAXAI_PWA_PORT)}"
    pwa_port="${pwa_port:-3334}"
    if ! valid_port "$rag_port"; then
        echo "[ERROR] $(t "TRINAXAI_PORT is invalid: $rag_port. Set a TCP port from 1 to 65535 in .env." "TRINAXAI_PORT no es válido: $rag_port. Define en .env un puerto TCP entre 1 y 65535.")" >&2
        return 1
    fi
    if ! valid_port "$pwa_port"; then
        echo "[ERROR] $(t "TRINAXAI_PWA_PORT is invalid: $pwa_port. Set a TCP port from 1 to 65535 in .env." "TRINAXAI_PWA_PORT no es válido: $pwa_port. Define en .env un puerto TCP entre 1 y 65535.")" >&2
        return 1
    fi
    for scheme in https http; do
        if wait_for_local_url "$scheme://127.0.0.1:$rag_port/ready"; then
            rag_url="$scheme://127.0.0.1:$rag_port"
            break
        fi
    done
    if [ -z "$rag_url" ]; then
        echo "[ERROR] $(t "TrinaxAI backend readiness failed on port $rag_port. Check: systemctl status ai-rag.service and journalctl -u ai-rag.service -n 50." "Falló la prueba de disponibilidad del backend TrinaxAI en el puerto $rag_port. Comprueba: systemctl status ai-rag.service y journalctl -u ai-rag.service -n 50.")" >&2
        return 1
    fi
    for scheme in https http; do
        if wait_for_local_url "$scheme://127.0.0.1:$pwa_port/"; then
            pwa_url="$scheme://127.0.0.1:$pwa_port"
            break
        fi
    done
    if [ -z "$pwa_url" ]; then
        echo "[ERROR] $(t "TrinaxAI PWA readiness failed on port $pwa_port. Check: systemctl status trinaxai-frontend.service and journalctl -u trinaxai-frontend.service -n 50." "Falló la prueba de disponibilidad de la PWA TrinaxAI en el puerto $pwa_port. Comprueba: systemctl status trinaxai-frontend.service y journalctl -u trinaxai-frontend.service -n 50.")" >&2
        return 1
    fi
    RAG_BASE_URL="$rag_url"
    if ! smoke_inference; then
        echo "[ERROR] $(t "Functional smoke test failed against $RAG_BASE_URL/v1/chat/completions. Check the model logs and retry after fixing the backend." "Falló la prueba funcional contra $RAG_BASE_URL/v1/chat/completions. Comprueba los logs del modelo y reintenta tras corregir el backend.")" >&2
        return 1
    fi
    echo "      ${GREEN}[OK]${NC} $(t 'Backend, PWA, and smoke inference are ready' 'Backend, PWA y prueba funcional están listos')"
}

if ! assert_runtime_ready; then
    fail "$(t 'Setup stopped: the local runtime did not pass its functional readiness checks.' 'Setup detenido: el runtime local no superó las pruebas funcionales de disponibilidad.')"
fi

if [ "$ok" = true ]; then
    echo -e "${GREEN}+------------------------------------------+${NC}"
    echo -e "${GREEN}|  $(t 'TrinaxAI ready. Setup complete.' 'TrinaxAI listo. Setup completado.')       |${NC}"
    echo -e "${GREEN}+------------------------------------------+${NC}"
    echo "  $(t 'You can now start and stop services from the PWA.' 'Ahora puedes encender y apagar servicios desde la PWA.')"
    echo "  $(t 'Ollama responses will be faster with the model in RAM.' 'Las respuestas de Ollama serán más rápidas con el modelo en RAM.')"
    echo ""
    echo "  $(t 'Index your files when ready:' 'Falta indexar tus archivos cuando quieras:')"
    echo "    cd $PROJ && .venv/bin/python index.py"
fi
