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


# Bilingual intent patterns, shared with modeRouter.ts for chat/web/research/RAG. The web app has no
# workspace-action routing (its agent is a mode the user turns on); the terminal does, so the
# agent/file/git patterns below exist only here. They run
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
DIRECT_LOOKUP = re.compile(
    r"\b(?:busca|buscar|buscame|búscame|buscalo|búscalo|search|look\s+up|find\s+out)\b\s+(?!como\b|how\b)\S+",
    re.I,
)
CURRENT_INFO = re.compile(
    r"\b(?:actual|actualmente|ahora|hoy|ultima|ultimo|ultimas|ultimos|reciente|noticias|"
    r"novedades|temporada|precio|cotizacion|version actual|latest|current|today|recent|"
    r"news|season|price|schedule|weather|clima)\b",
    re.I,
)
DEEP = re.compile(
    r"\b(?:investiga a fondo|investigacion profunda|investigacion compleja|modo investigacion|"
    r"analisis exhaustivo|estudio exhaustivo|analisis comparativo|revision de varias fuentes|"
    r"informe detallado|compara varias fuentes|multiples fuentes|distintas perspectivas|"
    r"deep\s*research|research thoroughly|complex research|comprehensive research|multiple sources|"
    r"detailed report|comparative analysis)\b",
    re.I,
)
LOCAL_GROUNDING = re.compile(
    r"\b(?:modo rag|rag mode|mis archivos|mis documentos|mi proyecto|mi repo|repositorio|"
    r"documentos indexados|base de conocimiento|indexed documents|my files|my documents|"
    r"my project|my repo|knowledge base)\b",
    re.I,
)
PERSONAL_KNOWLEDGE = re.compile(
    r"\b(?:he hecho|hice|he creado|mis programas|mis proyectos|mi trabajo|mi codigo|"
    r"mis aplicaciones|cuando hice|lo que hice|lo que he hecho|proyectos que hice|proyectos hice|"
    r"i made|i created|what i made|what i built|my projects|my work|my code|my apps|projects i made)\b",
    re.I,
)
AGENT_ACTION = re.compile(
    r"\b(?:modifica|edita|corrige|implementa|agrega|anade|elimina|refactoriza|ejecuta|instala|"
    r"actualiza|crea|crear|arregla|aplica|disena|disenar|modify|edit|fix|implement|add|delete|remove|"
    r"refactor|run|execute|install|update|create|apply|design|build|develop)\b",
    re.I,
)
AGENT_TARGET = re.compile(
    r"\b(?:archivo|archivos|proyecto|repo|repositorio|codigo fuente|componente|tests?|pruebas|"
    r"comando|terminal|dependencias|package\.json|pagina web|sitio web|landing page|frontend|"
    r"front-end|interfaz web|aplicacion web|web app|website|web|file|files|project|repository|codebase|"
    r"component|command|dependencies|web interface)\b",
    re.I,
)
# A file name with a code/text extension is a workspace target on its own ("arregla el bug en
# calc.py"). Framework names that end in ".js" (node.js, next.js, ...) are not files.
FILE_REFERENCE = re.compile(
    r"(?<![\w./\\-])(?!(?:node|next|vue|react|nuxt|express|three|d3|angular|ember|backbone|socket|chart|p5|alpine|"
    r"svelte|deno|bun)\.js\b)[\w/\\-][\w./\\-]*\.(?:py|pyi|js|jsx|ts|tsx|mjs|cjs|json|ya?ml|toml|md|txt|html|css|scss|"
    r"sh|bash|ps1|rs|go|java|kt|c|h|cpp|hpp|cs|rb|php|sql|ini|cfg|env|lock|csv)\b",
    re.I,
)
READ_ACTION = re.compile(r"\b(?:lee|leer|abre|abrir|revisa|resume|read|open|review|inspect|summari[sz]e)\b", re.I)
# Version-control orders. A bare "commit"/"push" is usually a noun in a question, so they must
# open the message or follow `git`.
_GIT_SUBCOMMAND = r"git\s+(?:status|diff|log|add|commit|push|pull|fetch|branch|checkout|switch|merge|rebase|stash|tag|reset|restore)\b"
GIT_ACTION = re.compile(
    rf"^(?:por favor |please )?{_GIT_SUBCOMMAND}"
    rf"|\b(?:run|ejecuta|execute|usa|use|haz|hacer|do)\s+(?:un\s+|a\s+|el\s+|the\s+)?{_GIT_SUBCOMMAND}"
    rf"|^(?:por favor |please )?(?:show(?: me)?|muestra(?:me)?|ensename|dame|give me)\s+(?:the\s+|el\s+|mi\s+|my\s+)?{_GIT_SUBCOMMAND}"
    r"|^(?:por favor |please )?(?:haz(?:me)? (?:un )?(?:commit|push)|hacer (?:un )?commit|commitea|"
    r"commit\s+(?:these|this|the|my|all|everything|changes|los|las|mis|todo|estos|este)\b|"
    r"push\s+(?:these|this|the|my|all|everything|changes|to|los|las|mis|todo|estos|este)\b|"
    r"sube\s+(?:los |mis |estos )?cambios|make a commit)",
    re.I,
)
# A question about how something works, as opposed to an order to do it: it opens with a question
# word, ends in a question mark together with one, or compares ("rebase vs merge"). "tell me what
# is in it" inside an order is not a question.
_QUESTION_WORD = (
    r"(?:why|por que|what(?: does| is| are)?|que(?: significa| es| son)?|how(?: do| does| can| to)?|"
    r"como(?: hago| puedo| se| funciona)?|explain|explica(?:me|r)?|difference|diferencia)"
)
CONCEPTUAL_QUESTION = re.compile(
    rf"^(?:por favor |please )?[?¿]*\s*{_QUESTION_WORD}\b"
    rf"|\b{_QUESTION_WORD}\b.*\?\s*$"
    r"|\b(?:vs\.?|versus|difference between|diferencia entre)\b",
    re.I,
)
EDUCATIONAL_ONLY = re.compile(
    r"\b(?:explica(?:me|r)?|como|ejemplo|ensena(?:me|r)?|explain|how to|example|teach)\b.{0,100}"
    r"\b(?:editar|modificar|corregir|ejecutar|instalar|crear|construir|disenar|desarrollar|"
    r"edit|modify|fix|run|install|create|build|design|develop)\b",
    re.I,
)
EXPLICIT_NEGATION = re.compile(
    r"\b(?:no|sin|never|don't|do not|solo|just)\b.{0,40}"
    r"\b(?:modificar|editar|ejecutar|instalar|modify|edit|run|install)\b",
    re.I,
)


_URL = re.compile(
    r"\b[a-z][a-z0-9+.-]*://\S+"  # https://example.com/page.html
    r"|\bwww\.\S+"
    # docs.python.org/3/library/os.html; only well-known endings, so my.app/src/main.py stays a path
    r"|(?<![\w./\\-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|dev|edu|gov|ai|co|me|info|es|uk|de|fr)/\S*",
    re.I,
)


def _without_urls(text: str) -> str:
    """Web addresses end in names like page.html or post.md but are not workspace files."""
    return _URL.sub(" ", text)


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
    local_grounding = bool(LOCAL_GROUNDING.search(contextual) or PERSONAL_KNOWLEDGE.search(contextual))
    direct_lookup = bool(DIRECT_LOOKUP.search(current))
    explicit_web = bool(EXPLICIT_WEB.search(current))
    file_named = bool(FILE_REFERENCE.search(_without_urls(current)))
    # "why does git push fail?" or "explain how to read data.csv" ask about a tool; they do not order it.
    conceptual = bool(CONCEPTUAL_QUESTION.search(current))
    agent_task = (
        (bool(AGENT_ACTION.search(current)) and (bool(AGENT_TARGET.search(contextual)) or file_named))
        or (bool(READ_ACTION.search(current)) and file_named and not conceptual)
        or (bool(GIT_ACTION.search(current)) and not conceptual)
    )
    needs_web_evidence = bool(explicit_web or CURRENT_INFO.search(current) or DEEP.search(current))
    needs_combined_evidence = local_grounding and needs_web_evidence
    educational_only = bool(EDUCATIONAL_ONLY.search(current) or EXPLICIT_NEGATION.search(current))
    if (
        (agent_task and not ctx.has_documents or needs_combined_evidence)
        and not educational_only
        and ctx.engine != "rag"
        and not ctx.web_mode
        and not ctx.research_mode
    ):
        return RouteDecision("agent", "rule", "workspace_action" if agent_task else "hybrid_evidence", announce=True)
    if local_grounding and not explicit_web and not CURRENT_INFO.search(current):
        return RouteDecision("rag", "rule", "local_grounding", announce=True)
    if (
        direct_lookup
        and not explicit_web
        and not educational_only
        and not local_grounding
        and not DEEP.search(current)
        and ctx.engine != "rag"
        and not ctx.web_mode
        and not ctx.research_mode
    ):
        return RouteDecision("web", "rule", "direct_lookup", web_search=True, announce=True)
    if ctx.web_mode and ctx.research_mode:
        return RouteDecision("deep_research", "manual", "manual_web_research", web_search=True, depth=3)
    if ctx.web_mode:
        return RouteDecision("web", "manual", "manual_web", web_search=True)
    if ctx.research_mode:
        return RouteDecision("deep_research", "manual", "manual_research", depth=2)
    if explicit_web:
        return RouteDecision("web", "rule", "explicit_web", web_search=True, announce=True)

    if DEEP.search(current):
        local = local_grounding and not explicit_web and not CURRENT_INFO.search(current)
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
