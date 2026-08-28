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
    "query_required": ("--query is required.", "--query es obligatorio."),
    "file_path_required": ("File path required (use --file).", "Indica la ruta del archivo (usa --file)."),
    "service_start": ("Starting TrinaxAI services...", "Iniciando los servicios de TrinaxAI..."),
    "service_stop": ("Stopping TrinaxAI services...", "Deteniendo los servicios de TrinaxAI..."),
    "cancelled_lower": ("cancelled.", "cancelado."),
    "memory_text_prompt": ("Memory text", "Texto de memoria"),
    "memory_id_prompt": ("Memory id (or prefix)", "ID de memoria (o prefijo)"),
    "collection_name_prompt": ("Collection name", "Nombre de colección"),
    "collection_id_prompt": ("Collection id", "ID de colección"),
    "active_collection_prompt": ("Collection id to activate", "ID de colección que activar"),
    "agent_prompt": ("agent", "agente"),
    "select_number": ("Select number (or q to cancel)", "Selecciona un número (o q para cancelar)"),
    "conversation_cleared": ("Conversation cleared.", "Conversación borrada."),
    "not_found": ("Not found.", "No encontrado."),
    "deleted": ("Deleted.", "Eliminado."),
    "status_ok": ("ok", "correcto"),
    "status_running": ("running", "activo"),
    "status_stopped": ("stopped", "detenido"),
    "status_pending": ("pending", "pendiente"),
    "status_failed": ("failed", "falló"),
    "status_passed": ("passed", "correcto"),
    "status_warning": ("warning", "aviso"),
    "status_healthy": ("healthy", "saludable"),
    "status_unhealthy": ("unhealthy", "no saludable"),
    "slash_commands_title": ("Slash commands:", "Comandos slash:"),
    "installed_models_title": ("Installed TrinaxAI models:", "Modelos de TrinaxAI instalados:"),
    "model_usage_title": ("Use this model in:", "Usa este modelo en:"),
    "rag_collections_title": ("PWA collections available for RAG:", "Colecciones PWA disponibles para RAG:"),
    "collections_title": ("Collections", "Colecciones"),
    "paired_devices_title": ("Paired devices", "Dispositivos vinculados"),
    "models_title": ("TrinaxAI models", "Modelos de TrinaxAI"),
    "config_title": ("TrinaxAI config", "Configuración de TrinaxAI"),
    "doctor_title": ("TrinaxAI doctor", "Doctor de TrinaxAI"),
    "memory_summary_title": ("Memory summary", "Resumen de memoria"),
    "current_summary_title": ("Current summary", "Resumen actual"),
    "subquestions_title": ("Sub-questions", "Subpreguntas"),
    "agent_title": ("TrinaxAI Agent", "Agente de TrinaxAI"),
    "welcome_title": ("Welcome to TrinaxAI", "Bienvenido a TrinaxAI"),
    "table_setting": ("setting", "configuración"),
    "table_value": ("value", "valor"),
    "table_model": ("model", "modelo"),
    "table_status": ("status", "estado"),
    "table_detail": ("detail", "detalle"),
    "table_check": ("check", "comprobación"),
    "table_id": ("id", "id"),
    "table_name": ("name", "nombre"),
    "provide_either_collection": (
        "Provide either --collection-id or --name, not both.",
        "Indica --collection-id o --name, no ambos.",
    ),
    "cancelled_title": ("Cancelled.", "Cancelado."),
    "index_timeout": (
        "Indexing timed out; the indexer process group was stopped.",
        "La indexación agotó el tiempo; se detuvo el grupo de procesos del indexador.",
    ),
    "vault_required": ("--vault PATH is required.", "--vault PATH es obligatorio."),
    "local_ai_request": ("Local AI request", "Solicitud a la IA local"),
    "agent_setup": ("Agent setup", "Configuración del agente"),
    "agent_task": ("Agent task", "Tarea del agente"),
    "list_models": ("List Ollama models", "Listar modelos de Ollama"),
    "list_collections": ("List PWA collections", "Listar colecciones de la PWA"),
    "watch_status": ("Watch status", "Estado del watcher"),
    "research_action": ("Research", "Investigación"),
    "index_action": ("Index", "Indexación"),
    "load_session": ("Load session", "Cargar sesión"),
    "write_export": ("Write export", "Escribir exportación"),
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
    for _key, pair in MESSAGES.items():
        if normalized == pair[0]:
            return pair[1] if normalize_lang(lang) == "es" else pair[0]
    if normalize_lang(lang) != "es":
        return message
    patterns: tuple[tuple[str, str], ...] = (
        (r"^No files in collection '(.+)'\.$", r"No hay archivos en la colección '\1'."),
        (
            r"^Collection name '(.+)' is ambiguous; use --collection-id\.$",
            r"El nombre de colección '\1' es ambiguo; usa --collection-id.",
        ),
        (
            r"^Collection name '(.+)' is not found; use --collection-id\.$",
            r"No se encontró el nombre de colección '\1'; usa --collection-id.",
        ),
        (r"^Files in '(.+)' \((.+)\)$", r"Archivos en '\1' (\2)"),
        (r"^#(.+) score=(.+)$", r"#\1 puntuación=\2"),
        (r"^Memories \((.+)\)$", r"Memorias (\1)"),
        (r"^Host: (.+)$", r"Anfitrión: \1"),
        (r"^LAN addresses: (.+)$", r"Direcciones LAN: \1"),
        (r"^LAN trust CA for phones: (.+)$", r"CA de confianza LAN para teléfonos: \1"),
        (r"^LAN certificate for phones: (.+)$", r"Certificado LAN para teléfonos: \1"),
        (
            r"^Install this CA only on devices you control; never share the private key\.$",
            "Instala esta CA solo en dispositivos que controles; nunca compartas la clave privada.",
        ),
        (
            r"^Import this certificate only on devices you control; never share the private key\.$",
            "Importa este certificado solo en dispositivos que controles; nunca compartas la clave privada.",
        ),
        (r"^--query is required\.$", "--query es obligatorio."),
        (r"^Researching \(depth=(.+)\)\.\.\.$", r"Investigando (profundidad=\1)..."),
        (r"^Passes: (.+) · Model: (.+)$", r"Pasadas: \1 | Modelo: \2"),
        (r"^passes: (.+) \| model: (.+)( \| web: (.+))?$", r"pasadas: \1 | modelo: \2\4"),
        (r"^(.+) source\(s\):$", r"Fuentes: \1"),
        (
            r"^Cannot locate the TrinaxAI installation\. Set TRINAXAI_HOME or run the installer again\.$",
            "No se encuentra la instalación de TrinaxAI. Define TRINAXAI_HOME o ejecuta de nuevo el instalador.",
        ),
        (
            r"^Cannot locate the TrinaxAI installation\. Set TRINAXAI_HOME or run this command there\.$",
            "No se encuentra la instalación de TrinaxAI. Define TRINAXAI_HOME o ejecuta este comando allí.",
        ),
        (
            r"^Timed out while running service action: (.+)$",
            r"Se agotó el tiempo al ejecutar la acción del servicio: \1",
        ),
        (r"^service action failed: (.+)$", r"Falló la acción del servicio: \1"),
        (
            r"^MCP server integration is planned and is not configured in this release\.$",
            "La integración con el servidor MCP está prevista, pero no está configurada en esta versión.",
        ),
        (
            r"^Use the TrinaxAI HTTP API or CLI commands directly for now\.$",
            "Por ahora, usa directamente la API HTTP o los comandos de la CLI de TrinaxAI.",
        ),
        (r"^Stop (.+)\?$", r"¿Detener \1?"),
        (r"^Restart TrinaxAI AI services\?$", "¿Reiniciar los servicios de IA de TrinaxAI?"),
        (
            r"^Copied (.+) note\(s\) from '(.+)' into collection '(.+)' \(skipped: (.+)\)\.$",
            r"Se copiaron \1 nota(s) de '\2' a la colección '\3' (omitidas: \4).",
        ),
        (
            r"^Run `trinaxai index --folder (.+)` to build the index\.$",
            r"Ejecuta `trinaxai index --folder \1` para construir el índice.",
        ),
        (r"^No options available for (.+)\.$", r"No hay opciones disponibles para \1."),
        (r"^Invalid selection: (.+)$", r"Selección inválida: \1"),
        (
            r"^argument (.+): invalid choice: '(.+)' \(choose from (.+)\)$",
            r"argumento \1: opción inválida: '\2' (opciones: \3)",
        ),
        (r"^argument (.+): invalid int value: '(.+)'$", r"argumento \1: valor entero inválido: '\2'"),
        (r"^argument (.+): expected one argument$", r"argumento \1: falta un valor"),
        (r"^the following arguments are required: (.+)$", r"faltan los siguientes argumentos: \1"),
        (r"^unrecognized arguments: (.+)$", r"argumentos no reconocidos: \1"),
        (r"^Not a directory: (.+)$", r"No es una carpeta: \1"),
        (
            r"^Cannot locate index\.py\. Run from the TrinaxAI project root\.$",
            "No se encuentra index.py. Ejecuta el comando desde la raíz de TrinaxAI.",
        ),
        (r"^Indexer exited with code (.+)\.$", r"El indexador terminó con el código \1."),
        (r"^Watching (.+) path\(s\) - (.+) events$", r"Vigilando \1 ruta(s) - \2 eventos"),
        (r"^Last watcher error: (.+)$", r"Último error del watcher: \1"),
        (r"^Model is not installed or is not chat-capable: (.+)$", r"El modelo no está instalado o no admite chat: \1"),
        (r"^Mode must be 'ollama', 'general', or 'rag'\.$", "El modo debe ser 'ollama', 'general' o 'rag'."),
        (r"^General / Ollama \(isolated, no indexed context\)$", "General / Ollama (aislado, sin contexto indexado)"),
        (r"^RAG \(uses one PWA collection\)$", "RAG (usa una colección PWA)"),
        (
            r"^Agent auto-approve ENABLED — dangerous actions run without asking\.$",
            "Aprobación automática del agente ACTIVADA - las acciones peligrosas se ejecutan sin preguntar.",
        ),
        (
            r"^Agent auto-approve disabled — actions ask for confirmation\.$",
            "Aprobación automática del agente desactivada - las acciones pedirán confirmación.",
        ),
        (r"^Searching the web\.\.\.$", "Buscando en la web..."),
        (r"^cd: too many arguments$", "cd: demasiados argumentos"),
        (r"^cd: not a directory: (.+)$", r"cd: no es una carpeta: \1"),
        (r"^bye\.$", "adiós."),
        (
            r"^Make sure the TrinaxAI RAG service is running\.$",
            "Asegúrate de que el servicio RAG de TrinaxAI esté activo.",
        ),
        (
            r"^No PWA collections exist yet\. Create or index one first\.$",
            "Todavía no hay colecciones de la PWA. Crea o indexa una primero.",
        ),
        (r"^RAG enabled with collection: (.+) \| Model: (.+)$", r"RAG activado con la colección: \1 | Modelo: \2"),
        (r"^General chat pinned \| Model: (.+)$", r"Chat general fijado | Modelo: \1"),
        (
            r"^Automatic mode routing enabled\. TrinaxAI picks the best mode per turn\.$",
            "Routing automático activado. TrinaxAI elige el mejor modo en cada turno.",
        ),
        (r"^Agent mode pinned \| Workspace: (.+) \| (.+)$", r"Modo agente fijado | Workspace: \1 | \2"),
        (r"^Web-search mode pinned\.$", "Modo de búsqueda web fijado."),
        (r"^Deep-research mode pinned\.$", "Modo de investigación profunda fijado."),
        (r"^Agent workspace set to: (.+)$", r"Workspace del agente: \1"),
        (
            r"^Provide one memory id; the positional id and --memory-id disagree\.$",
            "Indica un solo ID de memoria; el ID posicional y --memory-id no coinciden.",
        ),
        (r"^Ambiguous id prefix; matches: (.+)$", r"El prefijo del ID es ambiguo; coincidencias: \1"),
        (r"^Refreshed summary \((.+) memories\)\.$", r"Resumen actualizado (\1 memorias)."),
        (r"^File path required \(use --file\)\.$", "Indica la ruta del archivo (usa --file)."),
        (r"^Unknown subcommand: (.+)$", r"Subcomando desconocido: \1"),
        (r"^Total: (.+)$", r"Total: \1"),
        (r"^Session '(.+)' is empty\.$", r"La sesión '\1' está vacía."),
        (
            r"^No private LAN address was detected\. Connect the host to Wi-Fi or Ethernet and try again\.$",
            "No se detectó una dirección LAN privada. Conecta el anfitrión a Wi-Fi o Ethernet e inténtalo de nuevo.",
        ),
        (
            r"^Use 'trinaxai network refresh' after changing Wi-Fi or router\.$",
            "Usa 'trinaxai network refresh' después de cambiar de Wi-Fi o router.",
        ),
        (
            r"^Current network added and local HTTPS certificate renewed\.$",
            "Se añadió la red actual y se renovó el certificado HTTPS local.",
        ),
        (
            r"^Restart TrinaxAI before opening the new address\.$",
            "Reinicia TrinaxAI antes de abrir la nueva dirección.",
        ),
        (
            r"^Administrator approval is required once to restart the HTTPS services\.$",
            "Se requiere aprobación de administrador una vez para reiniciar los servicios HTTPS.",
        ),
        (
            r"^Configuration is ready\. Restart the PWA and RAG services to activate it\.$",
            "La configuración está lista. Reinicia los servicios PWA y RAG para activarla.",
        ),
        (
            r"^Installation is incomplete: (.+) was not found in (.+)\.$",
            r"La instalación está incompleta: no se encontró \1 en \2.",
        ),
        (
            r"^Interrupted; stopped (.+) and its child processes\.$",
            r"Interrumpido; se detuvieron \1 y sus procesos secundarios.",
        ),
        (r"^Provide either --collection-id or --name, not both\.$", "Indica --collection-id o --name, no ambos."),
        (
            r"^Delete collection '(.+)' and its indexed files\?$",
            r"¿Eliminar la colección '\1' y sus archivos indexados?",
        ),
        (r"^Allow (.+)\? \(will create/overwrite a file\)$", r"¿Permitir \1? (creará o sobrescribirá un archivo)"),
        (r"^Allow (.+)\? \(will modify a file\)$", r"¿Permitir \1? (modificará un archivo)"),
        (r"^Allow (.+)\? \(will run a shell command\)$", r"¿Permitir \1? (ejecutará un comando de shell)"),
        (
            r"^Allow (.+)\? \(will run a side-effecting action\)$",
            r"¿Permitir \1? (ejecutará una acción con efectos secundarios)",
        ),
        (r"^AI boot preference: on$", "Preferencia de inicio de IA: activada"),
        (r"^AI boot preference: off$", "Preferencia de inicio de IA: desactivada"),
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
        (r"^Exported (.+) record\(s\) -> (.+)$", r"Exportados \1 registro(s) -> \2"),
        (r"^Exported (.+) record\(s\) → (.+)$", r"Exportados \1 registro(s) -> \2"),
        (r"^Current directory: (.+)$", r"Directorio actual: \1"),
        (r"^Stopping (.+)\.\.\.$", r"Deteniendo \1..."),
        (
            r"^Session: (.+) \| Mode: auto \| Type /help for commands\.$",
            r"Sesión: \1 | Modo: auto | Escribe /help para ver los comandos.",
        ),
        (r"^No memories stored yet\.$", "Todavía no hay memorias guardadas."),
        (
            r"^No collections yet\. Index a folder with /index PATH\.$",
            "Todavía no hay colecciones. Indexa una carpeta con /index PATH.",
        ),
        (r"^Watcher: (.+) \| watching: (.+)$", r"Watcher: \1 | vigilando: \2"),
        (r"^Indexer: (.+) \| queued: (.+)$", r"Indexador: \1 | en cola: \2"),
    )
    for pattern, replacement in patterns:
        matched = re.match(pattern, normalized)
        if matched:
            return re.sub(pattern, replacement, normalized)
    return message


def help_text(value: str, lang: str = "en") -> str:
    """Translate stable argparse prose while preserving flags and commands."""
    if normalize_lang(lang) != "es":
        return re.sub(r"(?m)^\s*mcp\s+==SUPPRESS==\s*$\n?", "", value)
    replacements = {
        "TrinaxAI CLI - local-first terminal assistant.": "CLI de TrinaxAI - asistente de terminal local-first.",
        "The default command opens a unified REPL that auto-routes between chat, web search, deep research, the private local coding agent and RAG.": "El comando predeterminado abre un REPL unificado que enruta entre chat, búsqueda web, investigación profunda, agente local privado y RAG.",
        "RAG API base URL (overrides config).": "URL base de la API RAG (sobrescribe la configuración).",
        "CA certificate bundle for verified HTTPS.": "Bundle de certificados CA para HTTPS verificado.",
        "Disable ANSI colour output.": "Desactivar la salida de color ANSI.",
        "Verbose (DEBUG) logging.": "Registro detallado (DEBUG).",
        "Unified REPL (chat | web | research | agent | RAG) or single prompt.": "REPL unificado (chat | web | investigación | agente | RAG) o una sola pregunta.",
        "Ask one question and exit.": "Hacer una pregunta y salir.",
        "Run a single task and exit.": "Ejecutar una tarea y salir.",
        "List all collections.": "Listar todas las colecciones.",
        "List files in a collection.": "Listar archivos de una colección.",
        "Show chunks for a file.": "Mostrar chunks de un archivo.",
        "Agentic assistant: read, write and run code in a workspace.": "Asistente con agente: leer, escribir y ejecutar código en un workspace.",
        "Index a folder into the local RAG store.": "Indexar una carpeta en el almacén RAG local.",
        "Browse collections, files and chunks.": "Explorar colecciones, archivos y chunks.",
        "Multi-pass deep research query.": "Consulta de investigación profunda multipaso.",
        "Show local service status.": "Mostrar el estado de los servicios locales.",
        "Start TrinaxAI local services.": "Iniciar los servicios locales de TrinaxAI.",
        "Stop AI services and keep them off after reboot.": "Detener los servicios de IA y mantenerlos apagados tras reiniciar.",
        "Restart TrinaxAI local services.": "Reiniciar los servicios locales de TrinaxAI.",
        "Show or refresh local-network access.": "Mostrar o renovar el acceso de red local.",
        "Renew HTTPS and allow the current LAN.": "Renovar HTTPS y permitir la LAN actual.",
        "Update files without restarting services.": "Actualizar archivos sin reiniciar servicios.",
        "List installed and recommended local models.": "Listar modelos locales instalados y recomendados.",
        "Pair and manage trusted LAN devices.": "Vincular y administrar dispositivos LAN confiables.",
        "Generate a short, one-time pairing code.": "Generar un código de vinculación corto y de un solo uso.",
        "Optional device credential lifetime.": "Duración opcional de la credencial del dispositivo.",
        "PWA origin used in the displayed pairing link.": "Origen de la PWA usado en el enlace de vinculación mostrado.",
        "List paired and revoked devices.": "Listar dispositivos vinculados y revocados.",
        "Revoke one paired device.": "Revocar un dispositivo vinculado.",
        "Show active CLI and environment configuration.": "Mostrar la configuración activa de CLI y entorno.",
        "Run local health checks.": "Ejecutar comprobaciones de salud locales.",
        "Return a non-zero exit code when any critical health check fails.": "Devolver un código distinto de cero si falla una comprobación crítica.",
        "Emit machine-readable JSON instead of a human table.": "Emitir JSON legible por máquinas en lugar de una tabla para personas.",
        "Print TrinaxAI CLI version.": "Mostrar la versión de la CLI de TrinaxAI.",
        "Show TrinaxAI CLI help.": "Mostrar la ayuda de la CLI de TrinaxAI.",
        "Update code, dependencies and the PWA.": "Actualizar código, dependencias y la PWA.",
        "Guided, safe TrinaxAI uninstaller.": "Desinstalador guiado y seguro de TrinaxAI.",
        "Export a saved session.": "Exportar una sesión guardada.",
        "Import an Obsidian vault into a collection.": "Importar un vault de Obsidian a una colección.",
        "File watcher daemon control.": "Control del daemon de vigilancia de archivos.",
        "Start the watcher.": "Iniciar el watcher.",
        "Stop the watcher.": "Detener el watcher.",
        "Show watcher status.": "Mostrar el estado del watcher.",
        "List memories.": "Listar memorias.",
        "Memory store management.": "Administrar el almacén de memoria.",
        "Collection management.": "Administrar colecciones.",
        "Show the current summary.": "Mostrar el resumen actual.",
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
    value = re.sub(r"(?m)^\s*mcp\s+==SUPPRESS==\s*$\n?", "", value)
    value = re.sub(
        r"Full TrinaxAI installation directory\s+\(overrides auto-\s*discovery\)\.",
        "Directorio completo de instalación de TrinaxAI (sobrescribe la detección automática).",
        value,
    )
    return value


def slash_help(lang: str = "en") -> str:
    """Return the stable interactive slash-command help in the selected language."""
    english = """Slash commands:
  /help              Show this help
  /exit              Exit chat
  /clear             Clear the in-memory conversation

  Modes (auto-detected each turn, or pin one):
  /chat              General chat (isolated Ollama)
  /agent (task)      Agentic mode: read/write/run code in a workspace
  /web (query)       Web-search-grounded answer
  /research (query)  Multi-pass deep research
  /rag (collection)  Ground answers on an indexed collection
  /general           Alias of /chat
  /auto              Back to automatic mode routing

  Tools & session:
  /model             Select an installed model and Ollama/RAG mode
  /model NAME MODE   Set directly, e.g. /model qwen3.5:4b rag
  /workspace (path)  Set the agent workspace (default: current dir)
  cd PATH            Change the session directory
  /yolo              Toggle agent auto-approve (dangerous)
  /thinking on|off   Enable or disable efficient reasoning
  /index (path)      Index a folder, default: current directory
  /memory            List persistent memories
  /collections       List indexed collections
  /watch             Show the file-watcher status
  /status            Show local service status"""
    spanish = """Comandos slash:
  /help              Mostrar esta ayuda
  /exit              Salir del chat
  /clear             Borrar la conversación en memoria

  Modos (detectados en cada turno o fijados manualmente):
  /chat              Chat general (Ollama aislado)
  /agent (tarea)     Modo agente: leer, escribir y ejecutar código en un workspace
  /web (consulta)    Respuesta fundamentada con búsqueda web
  /research (consulta) Investigación profunda multipaso
  /rag (colección)   Respuestas fundamentadas en una colección indexada
  /general           Alias de /chat
  /auto              Volver al routing automático

  Herramientas y sesión:
  /model             Seleccionar un modelo instalado y el modo Ollama/RAG
  /model NOMBRE MODO Configurar directamente, por ejemplo /model qwen3.5:4b rag
  /workspace (ruta)  Configurar el workspace del agente (por defecto: carpeta actual)
  cd RUTA            Cambiar el directorio de la sesión
  /yolo              Activar o desactivar aprobación automática del agente (peligroso)
  /thinking on|off   Activar o desactivar el razonamiento eficiente
  /index (ruta)      Indexar una carpeta; por defecto, la carpeta actual
  /memory            Listar memorias persistentes
  /collections       Listar colecciones indexadas
  /watch             Mostrar el estado del watcher de archivos
  /status            Mostrar el estado de los servicios locales"""
    return spanish if normalize_lang(lang) == "es" else english


__all__ = ["detect_lang", "help_text", "normalize_lang", "resolve_lang", "slash_help", "text", "translate"]
