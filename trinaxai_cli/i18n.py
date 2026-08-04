"""English/Spanish localization for human-facing CLI output."""

from __future__ import annotations

import os
import re
from typing import Any

Lang = str

MESSAGES: dict[str, tuple[str, str]] = {
    "warning_rich": (
        "warning: 'rich' is not installed; falling back to plain text output. Install with: pip install rich",
        "aviso: 'rich' no está instalado; se usará texto plano. Instala con: pip install rich",
    ),
    "failure_generic": (
        "{action} could not be completed. Try again; other commands remain available.",
        "No se pudo completar {action}. Inténtalo de nuevo; los demás comandos siguen disponibles.",
    ),
    "command_exception": (
        "TrinaxAI could not complete '{name}'. Other commands remain available; try again or use --verbose.",
        "TrinaxAI no pudo completar '{name}'. Los demás comandos siguen disponibles; inténtalo de nuevo o usa --verbose.",
    ),
    "interrupted": ("interrupted.", "interrumpido."),
    "cancelled": ("Cancelled.", "Cancelado."),
    "starting": ("Starting TrinaxAI services...", "Iniciando los servicios de TrinaxAI..."),
    "updating": ("Updating TrinaxAI...", "Actualizando TrinaxAI..."),
    "no_connection": (
        "Is TrinaxAI running? Start it with: trinaxai start",
        "¿Está TrinaxAI encendido? Inícialo con: trinaxai start",
    ),
    "start_hint": ("Start TrinaxAI with: trinaxai start", "Inicia TrinaxAI con: trinaxai start"),
    "no_collections": ("No collections.", "No hay colecciones."),
    "no_memories": ("No memories.", "No hay memorias."),
    "no_files": ("No files in collection '{collection}'.", "No hay archivos en la colección '{collection}'."),
    "no_chunks": ("No chunks.", "No hay chunks."),
    "name_required": ("Name required.", "El nombre es obligatorio."),
    "text_required": ("Text required.", "El texto es obligatorio."),
    "collection_id_required": ("Collection id required.", "El ID de la colección es obligatorio."),
    "memory_id_required": ("Memory id required.", "El ID de la memoria es obligatorio."),
    "collection_not_found": ("Collection '{collection}' does not exist.", "La colección '{collection}' no existe."),
    "delete_default": ("Cannot delete the 'default' collection.", "No se puede eliminar la colección 'default'."),
    "invalid_workspace": (
        "workspace does not exist or is not a directory: {path}",
        "el workspace no existe o no es una carpeta: {path}",
    ),
    "ask_usage": (
        'Usage: trinaxai ask "your question" or echo "your question" | trinaxai ask',
        'Uso: trinaxai ask "tu pregunta" o echo "tu pregunta" | trinaxai ask',
    ),
    "stdin_limit": ("stdin prompt exceeds the 1 MiB limit.", "la pregunta de stdin supera el límite de 1 MiB."),
    "index_usage": ("Usage: trinaxai index /path/to/project", "Uso: trinaxai index /ruta/al/proyecto"),
    "indexing": (
        "Indexing {path} into collection '{collection}' (append={append})...",
        "Indexando {path} en la colección '{collection}' (append={append})...",
    ),
    "index_complete": (
        "Indexing completed and the live RAG index was reloaded.",
        "La indexación terminó y el índice RAG activo fue recargado.",
    ),
    "watcher_stopped": ("Watcher is not running.", "El watcher no está activo."),
    "pairing_none": ("No paired devices.", "No hay dispositivos vinculados."),
    "pairing_warning": (
        "The code is single-use. Verify the device name after it connects.",
        "El código solo se puede usar una vez. Verifica el nombre del dispositivo cuando se conecte.",
    ),
    "network_cancelled": ("Cancelled.", "Cancelado."),
    "method_not_allowed": ("Method not allowed.", "Método no permitido."),
}


def normalize_lang(value: str | None) -> str:
    return "es" if str(value or "").lower().replace("_", "-").startswith("es") else "en"


def detect_lang() -> str:
    for value in (os.getenv("TRINAXAI_LANG"), os.getenv("LC_ALL"), os.getenv("LC_MESSAGES"), os.getenv("LANG")):
        if value:
            return normalize_lang(value)
    return "en"


def resolve_lang(explicit: str | None = None, configured: str | None = None) -> str:
    return normalize_lang(explicit or configured or detect_lang())


def text(key: str, lang: str = "en", **values: Any) -> str:
    pair = MESSAGES.get(key)
    if pair is None:
        return key
    result = pair[1 if normalize_lang(lang) == "es" else 0]
    return result.format(**values)


def translate(message: Any, lang: str = "en") -> Any:
    if not isinstance(message, str):
        return message
    normalized = message.strip()
    for key, pair in MESSAGES.items():
        if normalized == pair[0]:
            return pair[1] if normalize_lang(lang) == "es" else pair[0]
    if normalize_lang(lang) != "es":
        return message
    patterns: tuple[tuple[str, str], ...] = (
        (r"^No files in collection '(.+)'\.$", r"No hay archivos en la colección '\1'."),
        (r"^No options available for (.+)\.$", r"No hay opciones disponibles para \1."),
        (r"^Invalid selection: (.+)$", r"Selección inválida: \1"),
        (r"^Not a directory: (.+)$", r"No es una carpeta: \1"),
        (
            r"^Cannot locate index\.py\. Run from the TrinaxAI project root\.$",
            "No se encuentra index.py. Ejecuta el comando desde la raíz de TrinaxAI.",
        ),
        (r"^Indexer exited with code (.+)\.$", r"El indexador terminó con el código \1."),
        (r"^Watching (.+) path\(s\) — (.+) events$", r"Vigilando \1 ruta(s) — \2 eventos"),
        (r"^Last watcher error: (.+)$", r"Último error del watcher: \1"),
        (r"^Unknown action: (.+)$", r"Acción desconocida: \1"),
        (r"^Unknown pair action: (.+)$", r"Acción de pairing desconocida: \1"),
        (r"^One-time pairing code: (.+)$", r"Código de pairing de un solo uso: \1"),
        (r"^Expires at Unix time (.+)$", r"Expira en el tiempo Unix \1"),
        (r"^Revoked (.+)\.$", r"Revocado: \1."),
        (r"^Collection '(.+)' does not exist\.$", r"La colección '\1' no existe."),
        (r"^Created '(.+)' \((.+)\)$", r"Creado '\1' (\2)"),
        (r"^Deleted '(.+)' \(nodes removed: (.+)\)$", r"Eliminado '\1' (nodos eliminados: \2)"),
        (r"^Active collection set to '(.+)' \(saved to (.+)\)\.$", r"Colección activa: '\1' (guardada en \2)."),
        (r"^Added memory (.+)$", r"Memoria añadida \1"),
        (r"^No memory matches prefix '(.+)'\.$", r"Ninguna memoria coincide con el prefijo '\1'."),
        (r"^Exported (.+) record\(s\) → (.+)$", r"Exportados \1 registro(s) → \2"),
        (r"^Current directory: (.+)$", r"Directorio actual: \1"),
        (r"^Stopping (.+)\.\.\.$", r"Deteniendo \1..."),
        (
            r"^Session: (.+) · Mode: auto · Type /help for commands\.$",
            r"Sesión: \1 · Modo: auto · Escribe /help para ver los comandos.",
        ),
        (r"^No memories stored yet\.$", "Todavía no hay memorias guardadas."),
        (
            r"^No collections yet\. Index a folder with /index PATH\.$",
            "Todavía no hay colecciones. Indexa una carpeta con /index PATH.",
        ),
        (r"^Watcher: (.+) · watching: (.+)$", r"Watcher: \1 · vigilando: \2"),
        (r"^Indexer: (.+) · queued: (.+)$", r"Indexador: \1 · en cola: \2"),
    )
    for pattern, replacement in patterns:
        matched = re.match(pattern, normalized)
        if matched:
            return re.sub(pattern, replacement, normalized)
    return message


def help_text(value: str, lang: str = "en") -> str:
    """Translate stable argparse prose while preserving flags and commands."""
    if normalize_lang(lang) != "es":
        return value
    replacements = {
        "TrinaxAI CLI — local-first terminal assistant.": "CLI de TrinaxAI — asistente de terminal local-first.",
        "The default command opens a unified REPL that auto-routes between chat, web search, deep research, the private local coding agent and RAG.": "El comando predeterminado abre un REPL unificado que enruta entre chat, búsqueda web, investigación profunda, agente local privado y RAG.",
        "RAG API base URL (overrides config).": "URL base de la API RAG (sobrescribe la configuración).",
        "CA certificate bundle for verified HTTPS.": "Bundle de certificados CA para HTTPS verificado.",
        "Disable ANSI colour output.": "Desactivar la salida de color ANSI.",
        "Verbose (DEBUG) logging.": "Registro detallado (DEBUG).",
        "Unified REPL (chat · web · research · agent · RAG) or single prompt.": "REPL unificado (chat · web · research · agent · RAG) o una sola pregunta.",
        "Ask one question and exit.": "Hacer una pregunta y salir.",
        "Agentic assistant: read, write and run code in a workspace.": "Asistente con agente: leer, escribir y ejecutar código en un workspace.",
        "Index a folder into the local RAG store.": "Indexar una carpeta en el almacén RAG local.",
        "Browse collections, files and chunks.": "Explorar colecciones, archivos y chunks.",
        "Multi-pass deep research query.": "Consulta de investigación profunda multipaso.",
        "Show local service status.": "Mostrar el estado de los servicios locales.",
        "Start TrinaxAI local services.": "Iniciar los servicios locales de TrinaxAI.",
        "Stop AI services and keep them off after reboot.": "Detener los servicios de IA y mantenerlos apagados tras reiniciar.",
        "Restart TrinaxAI local services.": "Reiniciar los servicios locales de TrinaxAI.",
        "Show or refresh local-network access.": "Mostrar o renovar el acceso de red local.",
        "List installed and recommended local models.": "Listar modelos locales instalados y recomendados.",
        "Pair and manage trusted LAN devices.": "Vincular y administrar dispositivos LAN confiables.",
        "Show active CLI and environment configuration.": "Mostrar la configuración activa de CLI y entorno.",
        "Run local health checks.": "Ejecutar comprobaciones de salud locales.",
        "Print TrinaxAI CLI version.": "Mostrar la versión de la CLI de TrinaxAI.",
        "Show TrinaxAI CLI help.": "Mostrar la ayuda de la CLI de TrinaxAI.",
        "Update code, dependencies and the PWA.": "Actualizar código, dependencias y la PWA.",
        "Guided, safe TrinaxAI uninstaller.": "Desinstalador guiado y seguro de TrinaxAI.",
        "Export a saved session.": "Exportar una sesión guardada.",
        "Import an Obsidian vault into a collection.": "Importar un vault de Obsidian a una colección.",
        "File watcher daemon control.": "Control del daemon de vigilancia de archivos.",
        "Memory store management.": "Administrar el almacén de memoria.",
        "Collection management.": "Administrar colecciones.",
        "Show the current summary.": "Mostrar el resumen actual.",
        "List memories.": "Listar memorias.",
        "Add a memory.": "Añadir una memoria.",
        "Forget a memory by id (prefix ok).": "Olvidar una memoria por ID (se acepta prefijo).",
        "Refresh the memory index.": "Actualizar el índice de memoria.",
        "List collections.": "Listar colecciones.",
        "Create a collection.": "Crear una colección.",
        "Delete a collection.": "Eliminar una colección.",
        "Switch the active collection.": "Cambiar la colección activa.",
        "show this help message and exit": "mostrar este mensaje de ayuda y salir",
        "Interface language (en or es).": "Idioma de la interfaz (en o es).",
        "Path to config TOML (overrides $TRINAXAI_CONFIG and XDG search).": "Ruta al TOML de configuración (sobrescribe $TRINAXAI_CONFIG y la búsqueda XDG).",
        "Full TrinaxAI installation directory (overrides auto-discovery).": "Directorio completo de instalación de TrinaxAI (sobrescribe la detección automática).",
        "Run a single prompt and exit.": "Ejecutar una pregunta y salir.",
        "Session name. A unique name is created when omitted.": "Nombre de sesión. Se crea un nombre único si se omite.",
        "Comma-separated collection ids.": "IDs de colecciones separados por comas.",
        "Chat engine. General uses Ollama without indexed-document context.": "Motor de chat. General usa Ollama sin contexto de documentos indexados.",
        "Agent workspace root for /agent turns (default: current dir).": "Raíz del workspace del agente para turnos /agent (por defecto: carpeta actual).",
        "Question to send, or omit it to read UTF-8 text from stdin.": "Pregunta que enviar; omítela para leer texto UTF-8 desde stdin.",
        "Directory the agent operates in (default: current dir).": "Directorio donde opera el agente (por defecto: carpeta actual).",
        "Ollama model to use (default: the tool-calling coder model).": "Modelo Ollama que usar (por defecto: modelo de código con herramientas).",
        "Max tool-use iterations (default: 25).": "Máximo de iteraciones de herramientas (por defecto: 25).",
        "Auto-approve every action without confirmation (dangerous).": "Aprobar automáticamente todas las acciones sin confirmación (peligroso).",
        "Folder to index, for example: trinaxai index .": "Carpeta que indexar, por ejemplo: trinaxai index .",
        "Folder to index (legacy alias).": "Carpeta que indexar (alias heredado).",
        "Collection id.": "ID de colección.",
        "Append-only (don't remove deleted files).": "Solo añadir (no elimina archivos borrados).",
        "Comma-separated scopes granted to the device.": "Scopes concedidos al dispositivo, separados por comas.",
        "Code lifetime in seconds (60-900).": "Duración del código en segundos (60-900).",
        "Skip confirmation.": "Omitir confirmación.",
        "Use safe non-interactive defaults.": "Usar valores seguros no interactivos.",
        "Update configured Ollama models.": "Actualizar los modelos Ollama configurados.",
        "Confirm and use safe defaults.": "Confirmar y usar valores seguros.",
        "Also remove data, models, certs and Ollama.": "También eliminar datos, modelos, certificados y Ollama.",
        "Output file path.": "Ruta del archivo de salida.",
        "Path to the Obsidian vault root.": "Ruta raíz del vault de Obsidian.",
        "Target collection id.": "ID de la colección destino.",
        "Directories to watch.": "Directorios que vigilar.",
        "Restrict to a single collection path.": "Limitar a una sola ruta de colección.",
        "Memory text (else prompted).": "Texto de memoria (si no, se pregunta).",
        "Comma-separated tags.": "Tags separados por comas.",
        "Memory id or prefix.": "ID o prefijo de memoria.",
        "Exact collection name (must be unique).": "Nombre exacto de colección (debe ser único).",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
        pattern = re.escape(source).replace(r"\ ", r"\s+")
        value = re.sub(pattern, target, value)
    return value


__all__ = ["detect_lang", "help_text", "normalize_lang", "resolve_lang", "text", "translate"]
