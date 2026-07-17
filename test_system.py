#!/usr/bin/env python3
"""
TrinaxAI — System Health Test
Ejecuta pruebas automáticas para verificar que todo el sistema funciona.
Uso: python test_system.py [--verbose] [--summary]
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().with_name(".env"))
except ImportError:
    pass

from config import create_ssl_context

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    group: str = "General"
    extra: list[str] = field(default_factory=list)


def _fetch(url: str, timeout: int = 8) -> tuple[int, str]:
    ctx = create_ssl_context(verify=False)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (OSError, ValueError, urllib.error.URLError):
        return -1, ""


def _fetch_with_http_fallback(url: str, timeout: int = 8) -> tuple[int, str]:
    code, body = _fetch(url, timeout=timeout)
    if code == -1 and url.startswith("https://"):
        return _fetch("http://" + url.removeprefix("https://"), timeout=timeout)
    return code, body


def check_python() -> list[CheckResult]:
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return [
        CheckResult(
            f"Python {py_ver}",
            sys.version_info >= (3, 10),
            "Requiere Python 3.10+",
            "Runtime",
        )
    ]


def check_ollama(ollama_base: str, *, verbose: bool = False) -> list[CheckResult]:
    code, body = _fetch(f"{ollama_base}/api/tags", timeout=8)
    if code != 200:
        return [
            CheckResult(
                "Ollama está corriendo",
                False,
                "Inicia TrinaxAI: ./startup_ai.sh o python service_manager.py start-ai",
                "Ollama",
            )
        ]
    try:
        models = json.loads(body).get("models", [])
    except json.JSONDecodeError:
        models = []
    extra = [f"📦 {m.get('name', '?')} ({m.get('size', '?')})" for m in models[:10]] if verbose else []
    return [
        CheckResult("Ollama está corriendo", True, group="Ollama"),
        CheckResult(
            f"Modelos disponibles: {len(models)}",
            len(models) > 0,
            "Ejecuta: ollama pull qwen2.5-coder:3b",
            "Ollama",
            extra,
        ),
    ]


def check_rag(rag_base: str, *, verbose: bool = False) -> list[CheckResult]:
    code, body = _fetch_with_http_fallback(f"{rag_base}/health", timeout=5)
    if code != 200:
        return [CheckResult("API responde", False, f"HTTP {code}", "RAG API")]
    try:
        data: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        return [CheckResult("API responde", False, "Respuesta JSON inválida", "RAG API")]
    extra = []
    if verbose:
        extra = [
            f"📁 Proyectos: {data.get('projects', [])}",
            f"🧠 num_ctx: {data.get('num_ctx', '?')}",
            f"📊 Reranker: {data.get('rerank', False)}",
        ]
    models_list = data.get("models", [])
    return [
        CheckResult("API responde", True, group="RAG API", extra=extra),
        CheckResult("Índice cargado", bool(data.get("indexed", False)), "Ejecuta: python index.py", "RAG API"),
        CheckResult(f"Perfil: {data.get('profile', '?')}", True, group="RAG API"),
        CheckResult(f"Modelos configurados: {len(models_list)}", len(models_list) > 0, group="RAG API"),
    ]


def check_frontend(frontend_url: str) -> list[CheckResult]:
    code, _ = _fetch_with_http_fallback(f"{frontend_url}/", timeout=5)
    return [CheckResult("PWA responde", code == 200, "Inicia: cd chat-pwa && npm run dev", "PWA")]


def check_feature_dependencies() -> list[CheckResult]:
    checks = [
        ("PowerPoint (.pptx)", "pptx", "Ejecuta: pip install python-pptx"),
        ("Excel (.xlsx)", "openpyxl", "Ejecuta: pip install openpyxl"),
        ("RTF", "striprtf", "Ejecuta: pip install striprtf"),
        ("Watcher", "watchdog", "Ejecuta: pip install watchdog"),
    ]
    results = []
    for name, module, hint in checks:
        try:
            __import__(module)
            available = True
        except ImportError:
            available = False
        results.append(CheckResult(name, available, hint, "Herramientas"))
    results.append(CheckResult(
        "Conversión Office heredada",
        bool(shutil.which("libreoffice") or shutil.which("soffice")),
        "Instala LibreOffice para leer .ppt, .xls, .doc y OpenDocument",
        "Herramientas",
    ))
    return results


def check_resources() -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        usage = shutil.disk_usage("/")
        avail_gb = usage.free / (1024**3)
        pct = int((1 - usage.free / usage.total) * 100)
        results.append(
            CheckResult(
                f"Espacio disponible: {avail_gb:.1f} GB ({pct}% usado)",
                pct < 95,
                "Libera espacio en disco",
                "Recursos",
            )
        )
    except (OSError, PermissionError):
        pass

    try:
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            mem_avail = 0
            for line in meminfo_path.read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1])
            if mem_avail > 0:
                results.append(CheckResult(f"RAM disponible: {mem_avail / (1024**2):.1f} GB", True, group="Recursos"))
        else:
            try:
                import psutil

                vmem = psutil.virtual_memory()
                results.append(CheckResult(f"RAM disponible: {vmem.available / (1024**3):.1f} GB", True, group="Recursos"))
            except ImportError:
                pass
    except (OSError, FileNotFoundError):
        pass
    return results


def run_checks(*, verbose: bool = False) -> list[CheckResult]:
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    rag_port = os.getenv("TRINAXAI_PORT", "3333")
    rag_base = os.getenv("TRINAXAI_HEALTH_URL", f"https://localhost:{rag_port}").rstrip("/")
    frontend_url = os.getenv("TRINAXAI_FRONTEND_URL", "https://localhost:3334").rstrip("/")

    checks: list[CheckResult] = []
    checks.extend(check_python())
    checks.extend(check_ollama(ollama_base, verbose=verbose))
    checks.extend(check_rag(rag_base, verbose=verbose))
    checks.extend(check_frontend(frontend_url))
    checks.extend(check_feature_dependencies())
    checks.extend(check_resources())
    return checks


def print_results(results: list[CheckResult], *, summary_only: bool = False) -> None:
    if not summary_only:
        print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║   TrinaxAI System Health Check       ║{RESET}")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════╝{RESET}\n")
        current_group = ""
        for result in results:
            if result.group != current_group:
                current_group = result.group
                print(f"\n{BOLD}{current_group}{RESET}")
            status = f"{GREEN}✅ PASS{RESET}" if result.ok else f"{RED}❌ FAIL{RESET}"
            print(f"  {status}  {result.name}")
            if result.detail and not result.ok:
                print(f"         {RED}{result.detail}{RESET}")
            for item in result.extra:
                print(f"         {item}")

    failed = [r for r in results if not r.ok]
    print(f"\n{BOLD}{'═' * 40}{RESET}")
    if not failed:
        print(f"{GREEN}{BOLD}✅ ¡Todo funciona correctamente!{RESET}")
        print(f"{GREEN}TrinaxAI está listo para usar.{RESET}")
    else:
        print(f"{YELLOW}{BOLD}⚠️  Se encontraron {len(failed)} problemas.{RESET}")
        for result in failed:
            print(f"{YELLOW}- {result.group}: {result.name}{RESET}")
        print(f"{YELLOW}Documentación: abre la PWA → 📚 Docs{RESET}")
    print(f"{BOLD}{'═' * 40}{RESET}\n")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print("Uso: python test_system.py [--verbose] [--summary]")
        print("")
        print("Verifica Python, Ollama, RAG API, PWA, disco y RAM sin modificar el sistema.")
        return 0
    verbose = "--verbose" in argv or "-v" in argv
    summary_only = "--summary" in argv
    results = run_checks(verbose=verbose)
    print_results(results, summary_only=summary_only)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
