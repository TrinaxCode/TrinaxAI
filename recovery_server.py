#!/usr/bin/env python3
"""Loopback-only recovery page for the stopped TrinaxAI installation."""

from __future__ import annotations

import argparse
import html
import http.server
import ipaddress
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit


def _is_loopback(value: str | None) -> bool:
    try:
        return bool(value) and ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value == "localhost"


def _tls_files(base_dir: Path) -> tuple[Path, Path] | None:
    certs = base_dir / "chat-pwa" / "certs"
    key = certs / "localhost-key.pem"
    cert = certs / "localhost.pem"
    if key.is_file() and cert.is_file():
        return key, cert
    return None


def _page(token: str, *, error: str = "", effective_url: str = "http://localhost:3334/") -> bytes:
    message = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TrinaxAI est&aacute; apagado</title><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#050b12;color:#eef7ff;font:16px system-ui,sans-serif;padding:24px}}
main{{width:min(460px,100%);padding:38px;border:1px solid #1d4665;border-radius:24px;background:#0b1722;box-shadow:0 20px 70px #0008;text-align:center}}
.mark{{font-size:42px;color:#42c6a5}}h1{{margin:12px 0 8px;font-size:27px}}p{{color:#a9c0d1;line-height:1.55}}button{{margin-top:18px;border:0;border-radius:12px;padding:13px 24px;background:#0879c9;color:white;font-weight:700;font-size:15px;cursor:pointer}}button:disabled{{opacity:.6;cursor:wait}}.error{{color:#ff9b9b}}
</style></head><body><main><div class="mark">&#9670;</div><h1>TrinaxAI est&aacute; apagado</h1>
<p id="status">TrinaxAI se encuentra apagado en este momento. &iquest;Deseas activar todo el sistema?</p>
<p>Solo disponible en este equipo: <code>{html.escape(effective_url)}</code><br>Only available on this computer.</p>{message}
<button id="start" type="button">Activar TrinaxAI</button></main><script>
const token={json.dumps(token)};const button=document.getElementById('start');const status=document.getElementById('status');
button.onclick=async()=>{{button.disabled=true;status.textContent='Iniciando TrinaxAI...';try{{const r=await fetch('/api/recovery/start',{{method:'POST',headers:{{'X-Recovery-Token':token,'Content-Type':'application/json'}},body:'{{}}',cache:'no-store'}});if(!r.ok)throw new Error('start_failed');
let attempts=0;const check=async()=>{{try{{const h=await fetch('/api/network',{{cache:'no-store'}});if(h.ok){{location.reload();return}}}}catch{{}}if(++attempts<80)setTimeout(check,750);else{{status.textContent='No se pudo iniciar TrinaxAI. Intenta de nuevo.';button.disabled=false}}}};setTimeout(check,500)}}catch{{status.textContent='No se pudo solicitar el arranque. Intenta de nuevo.';button.disabled=false}}}};
</script></body></html>""".encode("utf-8")


class RecoveryHandler(http.server.BaseHTTPRequestHandler):
    server_version = "TrinaxAI-Recovery/1.0"

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorized(self) -> bool:
        peer = self.client_address[0]
        origin = self.headers.get("Origin", "")
        if not _is_loopback(peer):
            return False
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not _is_loopback(parsed.hostname):
                return False
            if parsed.port not in {None, self.server.server_port}:
                return False
        return secrets.compare_digest(self.headers.get("X-Recovery-Token", ""), self.server.recovery_token)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/recovery/health":
            self._send(200, b'{"ok":true,"state":"stopped"}', "application/json")
        elif self.path == "/" or self.path.startswith("/"):
            scheme = "https" if self.server.tls_enabled else "http"
            self._send(
                200,
                _page(
                    self.server.recovery_token,
                    effective_url=f"{scheme}://localhost:{self.server.server_port}/",
                ),
            )
        else:
            self._send(404, b'{"ok":false}', "application/json")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/recovery/start":
            self._send(404, b'{"ok":false}', "application/json")
            return
        if not self._authorized():
            self._send(403, b'{"ok":false,"error":"forbidden"}', "application/json")
            return
        self._send(202, b'{"ok":true,"state":"starting"}', "application/json")
        threading.Thread(target=self.server.start_normal, daemon=True).start()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(405, b'{"ok":false,"error":"method_not_allowed"}', "application/json")

    def log_message(self, *_args) -> None:
        return


class RecoveryServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # Reuse is safe here because the normal gateway is stopped and the recovery
    # listener is bound to loopback only; it avoids a harmless TIME_WAIT gap.
    allow_reuse_address = True

    def __init__(self, address, handler, base_dir: Path):
        super().__init__(address, handler)
        self.base_dir = base_dir
        self.recovery_token = secrets.token_urlsafe(32)
        self.tls_enabled = False
        self.shutdown_all = self.shutdown
        self.stop_complete = threading.Event()
        self._start_lock = threading.Lock()
        self._start_requested = False

    def start_normal(self) -> None:
        with self._start_lock:
            if self._start_requested:
                return
            self._start_requested = True
        self.shutdown_all()
        self.stop_complete.wait(5)
        command = [
            sys.executable,
            str(self.base_dir / "service_manager.py"),
            "start-all",
            "--base-dir",
            str(self.base_dir),
        ]
        kwargs = {
            "cwd": str(self.base_dir),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": {**os.environ, "TRINAXAI_START_SUPERVISOR": "1"},
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(command, **kwargs)


class IPv6RecoveryServer(RecoveryServer):
    address_family = socket.AF_INET6


def run(base_dir: str) -> int:
    root = Path(base_dir).resolve()
    port = int(os.getenv("TRINAXAI_PWA_PORT", "3334"))
    servers = [RecoveryServer(("127.0.0.1", port), RecoveryHandler, root)]
    try:
        servers.append(IPv6RecoveryServer(("::1", port), RecoveryHandler, root))
    except OSError:
        pass
    tls = _tls_files(root)
    if tls:
        first, second = tls
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(second), str(first))
            for server in servers:
                server.socket = context.wrap_socket(server.socket, server_side=True)
                server.tls_enabled = True
        except (OSError, ssl.SSLError):
            for server in servers:
                server.tls_enabled = False

    def shutdown_all() -> None:
        for server in servers:
            server.shutdown()

    token = secrets.token_urlsafe(32)
    for server in servers:
        server.recovery_token = token
        server.shutdown_all = shutdown_all
    (root / "storage").mkdir(parents=True, exist_ok=True)
    (root / "storage" / "recovery.pid").write_text(str(os.getpid()), encoding="ascii")
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    try:
        while any(thread.is_alive() for thread in threads):
            for thread in threads:
                thread.join(1)
    finally:
        shutdown_all()
        for thread in threads:
            thread.join(timeout=2)
        try:
            (root / "storage" / "recovery.pid").unlink()
        except FileNotFoundError:
            pass
        for server in servers:
            server.stop_complete.set()
            server.server_close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parent))
    raise SystemExit(run(parser.parse_args().base_dir))
