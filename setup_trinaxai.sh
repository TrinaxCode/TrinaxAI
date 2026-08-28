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
PROFILE="$(grep -E '^TRINAXAI_PROFILE=' "$PROJ/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
PROFILE="${PROFILE:-16gb}"
LEGACY_8GB_PROFILE="$(printf '\154\157\167')"
if [ "$PROFILE" = "$LEGACY_8GB_PROFILE" ]; then PROFILE="8gb"; fi

echo -e "${BLUE}[1/4]${NC} $(t 'Tuning Ollama (systemd override)...' 'Optimizando Ollama (override de systemd)...')"
mkdir -p /etc/systemd/system/ollama.service.d
MAX_LOADED_MODELS=2
NUM_PARALLEL=4
if [ "$PROFILE" = "8gb" ]; then
    MAX_LOADED_MODELS=1
    NUM_PARALLEL=1
fi
cat > /etc/systemd/system/ollama.service.d/override.conf <<EOF
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
echo -e "      ${GREEN}[OK]${NC} $(t 'override.conf updated' 'override.conf actualizado')"

echo -e "${BLUE}[2/4]${NC} $(t 'Installing the secure PWA lifecycle wrapper...' 'Instalando el wrapper seguro de lifecycle para la PWA...')"
LIFECYCLE_DIR=/usr/local/libexec/trinaxai
LIFECYCLE_WRAPPER=$LIFECYCLE_DIR/trinaxai-lifecycle
install -d -o root -g root -m 0755 "$LIFECYCLE_DIR"
cat > "$LIFECYCLE_WRAPPER" <<'EOF'
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
chown root:root "$LIFECYCLE_WRAPPER"
chmod 0755 "$LIFECYCLE_WRAPPER"
cat > /etc/sudoers.d/trinaxai <<EOF
# Wrapper fijo, propiedad de root, con argumentos exactos. El repositorio y
# sus scripts nunca se ejecutan como root.
$USER_NAME ALL=(root) NOPASSWD: $LIFECYCLE_WRAPPER start-ai, $LIFECYCLE_WRAPPER stop-ai, $LIFECYCLE_WRAPPER start-all, $LIFECYCLE_WRAPPER stop-all, $LIFECYCLE_WRAPPER reload-network
EOF
chmod 0440 /etc/sudoers.d/trinaxai
# Validar sintaxis sudoers; si falla, eliminar para no romper sudo.
if visudo -cf /etc/sudoers.d/trinaxai >/dev/null 2>&1; then
    echo -e "      ${GREEN}[OK]${NC} $(t 'sudoers is valid' 'sudoers válido')"
else
    rm -f /etc/sudoers.d/trinaxai
    echo "      [ERROR] $(t 'Invalid sudoers; reverted. Aborting.' 'sudoers inválido; revertido. Abortando.')"
    exit 1
fi

echo -e "${BLUE}[3/4]${NC} $(t 'Enabling services...' 'Habilitando servicios...')"
cat > /etc/systemd/system/ai-rag.service <<EOF
[Unit]
Description=TrinaxAI RAG API
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJ
EnvironmentFile=-$PROJ/.env
ExecStart=$(which bash) -lc 'cd "$PROJ" && source .venv/bin/activate && if [ "\${TRINAXAI_RAG_HTTPS:-1}" != "0" ] && [ "\${TRINAXAI_RAG_HTTPS:-1}" != "false" ] && [ -f "$PROJ/chat-pwa/certs/localhost-key.pem" ] && [ -f "$PROJ/chat-pwa/certs/localhost.pem" ]; then exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333} --ssl-keyfile "$PROJ/chat-pwa/certs/localhost-key.pem" --ssl-certfile "$PROJ/chat-pwa/certs/localhost.pem"; else exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333}; fi'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/trinaxai-frontend.service <<EOF
[Unit]
Description=TrinaxAI Frontend PWA
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJ/chat-pwa
EnvironmentFile=-$PROJ/.env
Environment="NODE_ENV=production"
ExecStart=$(which npm) run preview
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ollama.service >/dev/null 2>&1 || true
systemctl restart ollama.service
# Esperar a Ollama
for i in {1..20}; do
    curl -s http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
done
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
for m in "${MODELS[@]}"; do
    if ! sudo -u "$USER_NAME" ollama list 2>/dev/null | grep -qF "$m"; then
        echo -e "        -> $m"; sudo -u "$USER_NAME" ollama pull "$m" >/dev/null 2>&1 || true
    fi
done
echo -e "      ${GREEN}[OK]${NC} $(t 'models ready' 'modelos listos')"

systemctl enable ai-rag.service >/dev/null 2>&1 || true
systemctl restart ai-rag.service
systemctl enable trinaxai-frontend.service >/dev/null 2>&1 || true
systemctl restart trinaxai-frontend.service
echo -e "      ${GREEN}[OK]${NC} $(t 'ollama + ai-rag + frontend restarted' 'ollama + ai-rag + frontend reiniciados')"

echo -e "${BLUE}[4/4]${NC} $(t 'Verifying...' 'Verificando...')"
sleep 2
ok=true
for s in ollama ai-rag trinaxai-frontend; do
    if systemctl is-active --quiet "$s.service"; then
        echo -e "      ${GREEN}[OK]${NC} $s $(t 'active' 'activo')"
    else
        echo "      [!] $s $(t 'NOT active' 'NO activo')"; ok=false
    fi
done

echo ""
if $ok; then
    echo -e "${GREEN}+------------------------------------------+${NC}"
    echo -e "${GREEN}|  $(t 'TrinaxAI ready. Setup complete.' 'TrinaxAI listo. Setup completado.')       |${NC}"
    echo -e "${GREEN}+------------------------------------------+${NC}"
    echo "  $(t 'You can now start and stop services from the PWA.' 'Ahora puedes encender y apagar servicios desde la PWA.')"
    echo "  $(t 'Ollama responses will be faster with the model in RAM.' 'Las respuestas de Ollama serán más rápidas con el modelo en RAM.')"
    echo ""
    echo "  $(t 'Index your files when ready:' 'Falta indexar tus archivos cuando quieras:')"
    echo "    cd $PROJ && .venv/bin/python index.py"
fi
