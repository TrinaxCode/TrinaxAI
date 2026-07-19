"""Turn-level mode routing for the unified TrinaxAI REPL.

A direct port of ``chat-pwa/src/components/chat/modeRouter.ts`` so the terminal
assistant routes exactly like the PWA. Each user turn is classified into one of:

* ``chat``          — ordinary isolated Ollama chat.
* ``rag``           — grounded on indexed collections.
* ``web``           — single-pass answer grounded on a live web search.
* ``deep_research`` — multi-pass research (optionally web-grounded).
* ``agent``         — file/shell tool-use over the workspace.

Routing is *auto + manual*: :func:`decide_mode` picks a mode from the prompt
text, but the REPL may pin a mode (``/agent``, ``/web`` …) which overrides the
automatic choice. The same bilingual (ES/EN) regexes as the PWA are used so the
behaviour is identical across surfaces.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["chat", "rag", "web", "deep_research", "agent"]


@dataclass
class RouteDecision:
    mode: Mode
    source: Literal["manual", "rule"]
    reason: str
    web_search: bool = False
    depth: int = 1
    announce: bool = False


@dataclass
class RouteContext:
    """Ambient state that biases routing, mirroring the PWA's RouteContext."""

    history: list[dict[str, str]] = field(default_factory=list)
    has_documents: bool = False
    web_mode: bool = False
    research_mode: bool = False
    engine: str = "ollama"


def _normalize(value: str) -> str:
    """Lowercase, strip accents and collapse whitespace (matches PWA normalize)."""
    decomposed = unicodedata.normalize("NFD", value or "")
    without_accents = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip().lower()


# Bilingual intent patterns — kept in lockstep with modeRouter.ts. They run
# against the accent-stripped, lowercased text so the Spanish variants omit
# their accents on purpose.
EXPLICIT_AGENT = re.compile(r"\b(?:modo agente|agente trinax|usa(?:r)? el agente|agent mode|use the agent)\b", re.I)
EXPLICIT_WEB = re.compile(
    r"\b(?:modo busqueda|busqueda web|web search|search mode)\b"
    r"|\b(?:busca|buscar|consulta|investiga|verifica|search|look up|check)\b.{0,35}"
    r"\b(?:internet|web|online|en linea)\b"
    r"|\b(?:internet|web|online|en linea)\b.{0,35}"
    r"\b(?:busca|buscar|consulta|investiga|verifica|search|check)\b",
    re.I,
)
CURRENT_INFO = re.compile(
    r"\b(?:actual|actualmente|ahora|hoy|ultima|ultimo|ultimas|ultimos|reciente|noticias|"
    r"novedades|temporada|precio|cotizacion|version actual|latest|current|today|recent|"
    r"news|season|price|schedule|weather|clima)\b",
    re.I,
)
DEEP = re.compile(
    r"\b(?:investiga a fondo|investigacion profunda|modo investigacion|analisis exhaustivo|"
    r"informe detallado|compara varias fuentes|multiples fuentes|distintas perspectivas|"
    r"deep\s*research|research thoroughly|comprehensive research|multiple sources|detailed report)\b",
    re.I,
)
LOCAL_GROUNDING = re.compile(
    r"\b(?:modo rag|rag mode|mis archivos|mis documentos|mi proyecto|mi repo|repositorio|"
    r"documentos indexados|base de conocimiento|indexed documents|my files|my documents|"
    r"my project|my repo|knowledge base)\b",
    re.I,
)
AGENT_ACTION = re.compile(
    r"\b(?:modifica|edita|corrige|implementa|agrega|anade|elimina|refactoriza|ejecuta|instala|"
    r"actualiza|crea|arregla|aplica|modify|edit|fix|implement|add|delete|remove|refactor|run|"
    r"execute|install|update|create|apply)\b",
    re.I,
)
AGENT_TARGET = re.compile(
    r"\b(?:archivo|archivos|proyecto|repo|repositorio|codigo fuente|componente|tests?|pruebas|"
    r"comando|terminal|dependencias|package\.json|file|files|project|repository|codebase|"
    r"component|command|dependencies)\b",
    re.I,
)


def _recent_topic(history: list[dict[str, str]]) -> str:
    users = [m for m in history if m.get("role") == "user"][-2:]
    return _normalize(" ".join(str(m.get("content") or "") for m in users))


def decide_mode(prompt: str, context: RouteContext | None = None) -> RouteDecision:
    """Classify a user turn into a mode, mirroring the PWA's decideAssistantMode."""
    ctx = context or RouteContext()
    current = _normalize(prompt)
    contextual = f"{_recent_topic(ctx.history)} {current}".strip()

    if EXPLICIT_AGENT.search(current):
        return RouteDecision("agent", "rule", "explicit_agent", announce=True)
    if ctx.web_mode and ctx.research_mode:
        return RouteDecision("deep_research", "manual", "manual_web_research", web_search=True, depth=3)
    if ctx.web_mode:
        return RouteDecision("web", "manual", "manual_web", web_search=True)
    if ctx.research_mode:
        return RouteDecision("deep_research", "manual", "manual_research", depth=2)
    if EXPLICIT_WEB.search(current):
        return RouteDecision("web", "rule", "explicit_web", web_search=True, announce=True)

    agent_task = bool(AGENT_ACTION.search(current)) and bool(AGENT_TARGET.search(contextual))
    if agent_task and not ctx.has_documents:
        return RouteDecision("agent", "rule", "workspace_action", announce=True)

    if DEEP.search(current):
        local = (
            bool(LOCAL_GROUNDING.search(contextual))
            and not EXPLICIT_WEB.search(current)
            and not CURRENT_INFO.search(current)
        )
        return RouteDecision(
            "deep_research",
            "rule",
            "deep_local" if local else "deep_web",
            web_search=not local,
            depth=3,
            announce=True,
        )
    if CURRENT_INFO.search(current):
        return RouteDecision("web", "rule", "current_information", web_search=True, announce=True)
    if LOCAL_GROUNDING.search(current):
        return RouteDecision("rag", "rule", "local_grounding", announce=True)
    if ctx.engine == "rag":
        return RouteDecision("rag", "manual", "manual_rag")
    return RouteDecision("chat", "rule", "ordinary_chat")


# Human-readable, bilingual labels for the "→ mode" announcement line.
MODE_LABELS: dict[Mode, tuple[str, str]] = {
    "chat": ("chat general", "general chat"),
    "rag": ("RAG (documentos indexados)", "RAG (indexed docs)"),
    "web": ("búsqueda web", "web search"),
    "deep_research": ("investigación profunda", "deep research"),
    "agent": ("agente", "agent"),
}


def mode_label(mode: Mode, lang: str = "es") -> str:
    es, en = MODE_LABELS.get(mode, (mode, mode))
    return es if lang == "es" else en
