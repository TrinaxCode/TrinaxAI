#!/usr/bin/env bash
# ============================================================
#  TrinaxAI — Setup de sistema (ejecutar UNA vez con sudo)
#
#    sudo ./setup_trinaxai.sh
#
#  Hace 3 cosas:
#   1. Optimiza Ollama (KEEP_ALIVE, 2 modelos cargados, paralelismo)
#      -> arregla la lentitud (antes recargaba 3GB en cada consulta).
#   2. Instala un wrapper de lifecycle mínimo y propiedad de root.
#   3. Habilita y reinicia los servicios.
# ============================================================
# Guard: bash is required for brace expansion and arrays.
if [ -z "${BASH_VERSION:-}" ]; then
    echo "ERROR: This script requires bash. Run: bash $0" >&2
    exit 1
fi

# OS detection: this script is Linux-only (systemd, sudoers, etc.)
if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: setup_trinaxai.sh is Linux-only (systemd)."
    echo "For macOS, use install.sh then start services manually."
    echo "For Windows, use install.sh in Git Bash then start manually."
    exit 1
fi

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Ejecuta con sudo:  sudo ./setup_trinaxai.sh"
    exit 1
fi

USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
PROFILE="$(grep -E '^TRINAXAI_PROFILE=' "$PROJ/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
PROFILE="${PROFILE:-16gb}"

echo -e "${BLUE}[1/4]${NC} Optimizando Ollama (override systemd)..."
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
# Mantener el modelo en RAM 30 min (respuestas rápidas, sin recargar 3GB).
Environment="OLLAMA_KEEP_ALIVE=30m"
# RAG usa 2 modelos a la vez (bge-m3 + qwen3): ambos cargados, sin thrashing.
Environment="OLLAMA_MAX_LOADED_MODELS=2"
# Paralelismo para indexado rápido (python index.py) y varias peticiones.
Environment="OLLAMA_NUM_PARALLEL=4"
# Ollama nunca se publica directamente en la LAN. La PWA usa el gateway
# autenticado de TrinaxAI, que aplica límites y una allowlist de operaciones.
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_ORIGINS=http://localhost:3334,http://127.0.0.1:3334"
EOF
echo -e "      ${GREEN}✓${NC} override.conf actualizado"

echo -e "${BLUE}[2/4]${NC} Wrapper seguro para encender/apagar desde la PWA..."
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
  *)
    echo "usage: trinaxai-lifecycle {start-ai|stop-ai}" >&2
    exit 2
    ;;
esac
EOF
chown root:root "$LIFECYCLE_WRAPPER"
chmod 0755 "$LIFECYCLE_WRAPPER"
cat > /etc/sudoers.d/trinaxai <<EOF
# Wrapper fijo, propiedad de root, con argumentos exactos. El repositorio y
# sus scripts nunca se ejecutan como root.
$USER_NAME ALL=(root) NOPASSWD: $LIFECYCLE_WRAPPER start-ai, $LIFECYCLE_WRAPPER stop-ai
EOF
chmod 0440 /etc/sudoers.d/trinaxai
# Validar sintaxis sudoers; si falla, eliminar para no romper sudo.
if visudo -cf /etc/sudoers.d/trinaxai >/dev/null 2>&1; then
    echo -e "      ${GREEN}✓${NC} sudoers válido"
else
    rm -f /etc/sudoers.d/trinaxai
    echo "      ❌ sudoers inválido — revertido. Abortando."
    exit 1
fi

echo -e "${BLUE}[3/4]${NC} Habilitando servicios..."
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
After=network.target ai-rag.service
Wants=ai-rag.service

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
echo -e "      ${BLUE}·${NC} Verificando modelos (descarga los que falten)..."
if [ "$PROFILE" = "8gb" ]; then
    MODELS=(bge-m3 qwen3.5:0.8b qwen3.5:4b qwen2.5-coder:1.5b qwen3-vl:2b-instruct)
elif [ "$PROFILE" = "ultra" ]; then
    MODELS=(bge-m3 qwen3.5:4b qwen3.5:35b-a3b qwen2.5-coder:14b qwen3-vl:32b-instruct)
elif [ "$PROFILE" = "max" ]; then
    MODELS=(bge-m3 qwen3.5:4b qwen3.5:27b qwen2.5-coder:7b qwen3-vl:30b-a3b-instruct)
else
    # 16gb (default)
    MODELS=(bge-m3 granite4:3b qwen3.5:9b qwen2.5-coder:3b qwen3-vl:8b-instruct)
fi
for m in "${MODELS[@]}"; do
    if ! sudo -u "$USER_NAME" ollama list 2>/dev/null | grep -qF "$m"; then
        echo -e "        ↓ $m"; sudo -u "$USER_NAME" ollama pull "$m" >/dev/null 2>&1 || true
    fi
done
# Eliminar modelos obsoletos (reemplazados por versiones más recientes en 2026).
# Si usas estos modelos en otros proyectos, presiona Ctrl+C en los próximos 5 segundos.
_LEGACY_MODELS=(nomic-embed-text llava:7b moondream qwen3-vl:2b qwen3-vl:4b qwen3-vl:8b qwen3-vl:32b llama3.2:3b qwen2.5-coder:1.5b qwen2.5-coder:14b)
_PRESENT=()
for m in "${_LEGACY_MODELS[@]}"; do
    sudo -u "$USER_NAME" ollama list 2>/dev/null | grep -qF "$m" && _PRESENT+=("$m") || true
done
if [ ${#_PRESENT[@]} -gt 0 ]; then
    echo -e "      ${YELLOW}⚠${NC}  Los siguientes modelos serán eliminados (reemplazados): ${_PRESENT[*]}"
    echo -e "      ${YELLOW}⚠${NC}  Si los usas en otros proyectos, presiona Ctrl+C ahora (5 seg)."
    sleep 5
    for m in "${_PRESENT[@]}"; do
        echo -e "        🗑  Eliminando $m..."
        sudo -u "$USER_NAME" ollama rm "$m" >/dev/null 2>&1 || true
    done
fi
echo -e "      ${GREEN}✓${NC} modelos listos"

systemctl enable ai-rag.service >/dev/null 2>&1 || true
systemctl restart ai-rag.service
systemctl enable trinaxai-frontend.service >/dev/null 2>&1 || true
systemctl restart trinaxai-frontend.service
echo -e "      ${GREEN}✓${NC} ollama + ai-rag + frontend reiniciados"

echo -e "${BLUE}[4/4]${NC} Verificando..."
sleep 2
ok=true
for s in ollama ai-rag trinaxai-frontend; do
    if systemctl is-active --quiet "$s.service"; then
        echo -e "      ${GREEN}✓${NC} $s activo"
    else
        echo "      ⚠️  $s NO activo"; ok=false
    fi
done

echo ""
if $ok; then
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  TrinaxAI listo. Setup completado.        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
    echo "  Ahora puedes encender/apagar desde la PWA y las"
    echo "  respuestas de Ollama serán rápidas (modelo en RAM)."
    echo ""
    echo "  Falta indexar tus archivos (cuando quieras):"
    echo "    cd $PROJ && .venv/bin/python index.py"
fi
