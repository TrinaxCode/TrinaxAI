#!/usr/bin/env python3
"""
TrinaxAI — System Health Test
Ejecuta pruebas automáticas para verificar que todo el sistema funciona.
Uso: python test_system.py [--verbose]
"""

import json
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().with_name(".env"))
except Exception:
    pass


try:
    from config import create_ssl_context
except Exception:

    def create_ssl_context(verify: "bool | None" = None) -> "ssl.SSLContext | None":
        if verify is None:
            verify = os.getenv("TRINAXAI_TLS_VERIFY", "0") == "1"
        if verify:
            return None
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _fetch(url: str, timeout: int = 8) -> tuple[int, str]:
    """Fetch a URL with urllib (no external curl dependency).
    Returns (status_code, body). Accepts self-signed certs for localhost."""
    # TrinaxAI uses self-signed certs for local HTTPS; verify=False is intentional.
    ctx = create_ssl_context(verify=False)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception:
        return -1, ""


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def check(msg: str, ok: bool, detail: str = "") -> bool:
    status = f"{GREEN}✅ PASS{RESET}" if ok else f"{RED}❌ FAIL{RESET}"
    print(f"  {status}  {msg}")
    if detail and not ok:
        print(f"         {RED}{detail}{RESET}")
    return ok


def record(current: bool, msg: str, ok: bool, detail: str = "") -> bool:
    return check(msg, ok, detail) and current


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Uso: python test_system.py [--verbose]")
        print("")
        print(
            "Verifica Python, Ollama, RAG API, PWA, disco y RAM sin modificar el sistema."
        )
        sys.exit(0)

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    all_ok = True
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    rag_port = os.getenv("TRINAXAI_PORT", "3333")
    rag_base = os.getenv("TRINAXAI_HEALTH_URL", f"https://localhost:{rag_port}").rstrip(
        "/"
    )
    frontend_url = os.getenv("TRINAXAI_FRONTEND_URL", "https://localhost:3334").rstrip(
        "/"
    )

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   TrinaxAI System Health Check       ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════╝{RESET}\n")

    # ── 1. Python version ──
    py_ver = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    all_ok = record(
        all_ok, f"Python {py_ver}", sys.version_info >= (3, 10), "Requiere Python 3.10+"
    )

    # ── 2. Ollama running ──
    print(f"\n{BOLD}🧠 Ollama ({ollama_base}){RESET}")
    try:
        code, body = _fetch(f"{ollama_base}/api/tags", timeout=8)
        if code == 200:
            data = json.loads(body)
            models = data.get("models", [])
            all_ok = record(all_ok, "Ollama está corriendo", True)
            all_ok = record(
                all_ok,
                f"Modelos disponibles: {len(models)}",
                len(models) > 0,
                "Ejecuta: ollama pull qwen2.5-coder:3b",
            )
            if verbose and models:
                for m in models[:10]:
                    print(f"         📦 {m.get('name', '?')} ({m.get('size', '?')})")
        else:
            all_ok = record(
                all_ok,
                "Ollama está corriendo",
                False,
                "Inicia TrinaxAI: ./startup_ai.sh o python service_manager.py start-ai",
            )
    except Exception:
        all_ok = record(
            all_ok,
            "Ollama está corriendo",
            False,
            "¿Está Ollama instalado? https://ollama.com",
        )

    # ── 3. RAG API health ──
    print(f"\n{BOLD}🔌 RAG API ({rag_base}){RESET}")
    try:
        code, body = _fetch(f"{rag_base}/health", timeout=5)
        if code == 200:
            data = json.loads(body)
            all_ok = record(all_ok, "API responde", True)
            indexed = bool(data.get("indexed", False))
            all_ok = record(
                all_ok,
                f"Índice cargado: {indexed}",
                indexed,
                "Ejecuta: python index.py",
            )
            all_ok = record(all_ok, f"Perfil: {data.get('profile', '?')}", True)
            models_list = data.get("models", [])
            all_ok = record(
                all_ok,
                f"Modelos configurados: {len(models_list)}",
                len(models_list) > 0,
            )
            if verbose:
                print(f"         📁 Proyectos: {data.get('projects', [])}")
                print(f"         🧠 num_ctx: {data.get('num_ctx', '?')}")
                print(f"         📊 Reranker: {data.get('rerank', False)}")
        else:
            all_ok = record(all_ok, "API responde", False, f"HTTP {code}")
    except Exception as e:
        all_ok = record(all_ok, "API responde", False, str(e))

    # ── 4. PWA running ──
    print(f"\n{BOLD}📱 PWA Frontend ({frontend_url}){RESET}")
    try:
        code, _ = _fetch(f"{frontend_url}/", timeout=5)
        all_ok = record(
            all_ok, "PWA responde", code == 200, "Inicia: cd chat-pwa && npm run dev"
        )
    except Exception as e:
        all_ok = record(all_ok, "PWA responde", False, str(e))

    # ── 5. Disk space ──
    print(f"\n{BOLD}💾 Recursos{RESET}")
    try:
        usage = shutil.disk_usage("/")
        avail_gb = usage.free / (1024**3)
        pct = int((1 - usage.free / usage.total) * 100)
        all_ok = record(
            all_ok,
            f"Espacio disponible: {avail_gb:.1f} GB ({pct}% usado)",
            pct < 95,
            "Libera espacio en disco",
        )
    except Exception:
        pass

    # ── 6. RAM ──
    try:
        # Linux: read /proc/meminfo (no external tools needed)
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            mem = meminfo_path.read_text()
            mem_total = mem_avail = 0
            for line in mem.split("\n"):
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1])
            if mem_avail > 0:
                avail_gb = mem_avail / (1024**2)
                all_ok = record(all_ok, f"RAM disponible: {avail_gb:.1f} GB", True)
        else:
            # Fallback: try psutil if installed
            try:
                import psutil

                vmem = psutil.virtual_memory()
                avail_gb = vmem.available / (1024**3)
                all_ok = record(all_ok, f"RAM disponible: {avail_gb:.1f} GB", True)
            except ImportError:
                pass
    except Exception:
        pass

    # ── Summary ──
    print(f"\n{BOLD}{'═' * 40}{RESET}")
    if all_ok:
        print(f"{GREEN}{BOLD}✅ ¡Todo funciona correctamente!{RESET}")
        print(f"{GREEN}TrinaxAI está listo para usar.{RESET}")
    else:
        print(f"{YELLOW}{BOLD}⚠️  Se encontraron problemas.{RESET}")
        print(f"{YELLOW}Revisa los ❌ FAIL arriba para más detalles.{RESET}")
        print(f"{YELLOW}Documentación: abre la PWA → 📚 Docs{RESET}")
    print(f"{BOLD}{'═' * 40}{RESET}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
