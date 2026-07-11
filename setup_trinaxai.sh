#!/usr/bin/env bash
# ============================================================
#  TrinaxAI — Setup de sistema (ejecutar UNA vez con sudo)
#
#    sudo ./setup_trinaxai.sh
#
#  Hace 3 cosas:
#   1. Optimiza Ollama (KEEP_ALIVE, 2 modelos cargados, paralelismo)
#      -> arregla la lentitud (antes recargaba 3GB en cada consulta).
#   2. Permite encender/apagar TrinaxAI desde la PWA sin contraseña
#      (sudoers para startup_ai.sh y shutdown_ai.sh).
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
# Accesible desde el teléfono en la LAN.
# ⚠️  SECURITY: Esto expone Ollama a toda tu red local SIN autenticación.
#     Cualquier dispositivo en tu LAN puede usar tus modelos de IA.
#     Recomendación: usa un firewall para restringir el puerto 11434,
#     o configura una VPN (Tailscale/WireGuard) para acceso remoto seguro.
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_ORIGINS=*"
EOF
echo -e "      ${GREEN}✓${NC} override.conf actualizado"

echo -e "${BLUE}[2/4]${NC} Permisos sudo para encender/apagar desde la PWA..."
echo -e "      ${RED}⚠${NC}  Los scripts startup_ai.sh y shutdown_ai.sh son ejecutables"
echo -e "      ${RED}⚠${NC}  como root sin contraseña. Si un atacante compromete tu"
echo -e "      ${RED}⚠${NC}  cuenta de usuario, podría modificarlos para ejecutar"
echo -e "      ${RED}⚠${NC}  comandos arbitrarios como root."
echo -e "      ${RED}⚠${NC}  Para producción, mueve estos scripts a /usr/local/lib/trinaxai/"
echo -e "      ${RED}⚠${NC}  y actualiza la regla sudoers."
cat > /etc/sudoers.d/trinaxai <<EOF
# Permite a la PWA ejecutar el arranque/apagado de TrinaxAI sin contraseña.
$USER_NAME ALL=(root) NOPASSWD: $PROJ/startup_ai.sh, $PROJ/shutdown_ai.sh
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
ExecStart=$(which bash) -lc 'cd "$PROJ" && source .venv/bin/activate && exec python rag_api.py'
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
    MODELS=(bge-m3 qwen3:4b-instruct-2507-q4_K_M llama3.2:1b qwen2.5-coder:1.5b qwen2.5-coder:3b qwen3-vl:2b qwen3-vl:4b)
elif [ "$PROFILE" = "max" ] || [ "$PROFILE" = "ultra" ]; then
    MODELS=(bge-m3 qwen3:30b-a3b-instruct-2507-q4_K_M qwen3:4b-instruct-2507-q4_K_M qwen2.5-coder:7b qwen3-coder:30b qwen3-vl:8b qwen3-vl:32b)
else
    # 16gb (default)
    MODELS=(bge-m3 qwen3:4b-instruct-2507-q4_K_M qwen2.5-coder:3b qwen2.5-coder:7b qwen3-vl:4b qwen3-vl:8b)
fi
for m in "${MODELS[@]}"; do
    if ! sudo -u "$USER_NAME" ollama list 2>/dev/null | grep -qF "$m"; then
        echo -e "        ↓ $m"; sudo -u "$USER_NAME" ollama pull "$m" >/dev/null 2>&1 || true
    fi
done
# Eliminar modelos obsoletos (reemplazados por versiones más recientes en 2026).
# Si usas estos modelos en otros proyectos, presiona Ctrl+C en los próximos 5 segundos.
_LEGACY_MODELS=(nomic-embed-text llava:7b moondream qwen2.5vl:3b qwen2.5vl:7b llama3.2:3b qwen2.5-coder:1.5b qwen2.5-coder:14b)
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
