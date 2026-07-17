#!/usr/bin/env bash
set -euo pipefail
umask 077

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run this migration with sudo: sudo scripts/harden_systemd_units.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
OWNER="$(stat -c '%U' "$ROOT" 2>/dev/null || stat -f '%Su' "$ROOT")"
BASH_BIN="$(command -v bash)"
NPM_BIN="$(command -v npm)"
STAMP="$(date +%Y%m%d-%H%M%S)"
LIFECYCLE_DIR=/usr/local/libexec/trinaxai
LIFECYCLE_WRAPPER=$LIFECYCLE_DIR/trinaxai-lifecycle

for unit in ai-rag.service trinaxai-frontend.service; do
  if [ -f "/etc/systemd/system/$unit" ]; then
    cp -a "/etc/systemd/system/$unit" "/etc/systemd/system/$unit.bak-$STAMP"
  fi
done

rag_tmp="$(mktemp)"
frontend_tmp="$(mktemp)"
cleanup() { rm -f "$rag_tmp" "$frontend_tmp"; }
trap cleanup EXIT

cat >"$rag_tmp" <<EOF
[Unit]
Description=TrinaxAI RAG API
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$OWNER
WorkingDirectory=$ROOT
EnvironmentFile=-$ROOT/.env
ExecStart=$BASH_BIN -lc 'cd "$ROOT" && source .venv/bin/activate && if [ "\${TRINAXAI_RAG_HTTPS:-1}" != "0" ] && [ "\${TRINAXAI_RAG_HTTPS:-1}" != "false" ] && [ -f "$ROOT/chat-pwa/certs/localhost-key.pem" ] && [ -f "$ROOT/chat-pwa/certs/localhost.pem" ]; then exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333} --ssl-keyfile "$ROOT/chat-pwa/certs/localhost-key.pem" --ssl-certfile "$ROOT/chat-pwa/certs/localhost.pem"; else exec python -m uvicorn app.main:app --host 127.0.0.1 --port \${TRINAXAI_PORT:-3333}; fi'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >"$frontend_tmp" <<EOF
[Unit]
Description=TrinaxAI Frontend PWA
After=network.target ai-rag.service
Wants=ai-rag.service

[Service]
Type=simple
User=$OWNER
WorkingDirectory=$ROOT/chat-pwa
EnvironmentFile=-$ROOT/.env
Environment=NODE_ENV=production
ExecStart=$NPM_BIN run preview
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

install -o root -g root -m 0644 "$rag_tmp" /etc/systemd/system/ai-rag.service
install -o root -g root -m 0644 "$frontend_tmp" /etc/systemd/system/trinaxai-frontend.service

# The browser-facing PWA runs as the regular user, while Ollama is a system
# service. Give it only two fixed, root-owned lifecycle actions; never grant
# sudo to repository files or arbitrary systemctl arguments.
install -d -o root -g root -m 0755 "$LIFECYCLE_DIR"
wrapper_tmp="$(mktemp)"
cat >"$wrapper_tmp" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  start-ai)
    systemctl enable ollama.service ai-rag.service >/dev/null
    systemctl start ollama.service ai-rag.service
    ;;
  stop-ai)
    systemctl stop ai-rag.service ollama.service
    systemctl disable ai-rag.service ollama.service >/dev/null
    ;;
  *)
    echo "usage: trinaxai-lifecycle {start-ai|stop-ai}" >&2
    exit 2
    ;;
esac
EOF
install -o root -g root -m 0755 "$wrapper_tmp" "$LIFECYCLE_WRAPPER"
rm -f "$wrapper_tmp"
cat >/etc/sudoers.d/trinaxai <<EOF
# Exact root-owned lifecycle wrapper only; repository files are never sudoable.
$OWNER ALL=(root) NOPASSWD: $LIFECYCLE_WRAPPER start-ai, $LIFECYCLE_WRAPPER stop-ai
EOF
chmod 0440 /etc/sudoers.d/trinaxai
if ! visudo -cf /etc/sudoers.d/trinaxai >/dev/null; then
  rm -f /etc/sudoers.d/trinaxai
  echo "Invalid TrinaxAI sudoers policy; no lifecycle permission was installed." >&2
  exit 1
fi
systemctl daemon-reload
systemctl enable ai-rag.service trinaxai-frontend.service >/dev/null
systemctl restart ai-rag.service trinaxai-frontend.service

sleep 2
systemctl is-active --quiet ai-rag.service
systemctl is-active --quiet trinaxai-frontend.service
echo "TrinaxAI systemd units hardened. Backups use suffix .bak-$STAMP"
