"""Deterministic multi-label intent classifier (Phase 3 of the audit).

Zero LLM cost: pure string/lexical analysis over the current user turn (plus a
little history context). Produces a :class:`Classification` with the set of
matched categories and the primary regime.

Design goals:
- Never worse than the old binary router: everything the old ``_CODE_HINTS``
  caught still lands in a code/creative regime.
- Distinguish *generation* (create/implement) from *grounded QA about the
  user's own indexed docs*, because they need opposite decoding regimes.
- Fully overridable and fail-safe: on any doubt, fall back to a safe regime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.generation.spec import Regime

# ── Lexicons ──────────────────────────────────────────────────────────────
# Kept intentionally close to the historical config._CODE_HINTS so we never
# regress detection, then split by sub-domain for finer regime/param control.

_FRONTEND = (
    "react", "vue", "svelte", "angular", "next.js", "nextjs", "jsx", "tsx",
    "component", "componente", "tailwind", "css", "html", "landing", "ui",
    "ux", "responsive", "glassmorphism", "animation", "animación", "animacion",
    "hero", "navbar", "footer", "modal", "flexbox", "grid", "diseño web",
    "front-end", "frontend", "styling", "estilos", ".tsx", ".jsx", ".html",
    ".css", ".vue", ".svelte",
)
_BACKEND = (
    "backend", "back-end", "api", "endpoint", "rest", "graphql", "fastapi",
    "django", "flask", "express", "server", "servidor", "database", "base de datos",
    "sql", "postgres", "mysql", "mongodb", "redis", "auth", "jwt", "middleware",
    "microservice", "microservicio", "queue", "cola",
)
_PYTHON = ("python", "def ", "import ", "pip", ".py", "pytest", "asyncio", "pandas", "numpy")
_JS_TS = (
    "javascript", "typescript", "node", "npm", "yarn", "pnpm", "vite", "webpack",
    "const ", "let ", "var ", "=>", ".ts", ".js",
)
_DEBUG = (
    "bug", "error", "traceback", "exception", "stack trace", "no funciona",
    "falla", "falló", "crash", "segfault", "undefined", "null pointer",
    "fix", "arregla", "corrige", "depura", "debug", "por qué falla", "porque falla",
    "not working", "broken",
)
_ARCH = (
    "arquitect", "architecture", "design pattern", "patrón de diseño", "escalab",
    "scalab", "microservic", "system design", "diseña el sistema", "estructura del proyecto",
    "trade-off", "tradeoff", "diagrama",
)
_ALGO = (
    "algoritm", "algorithm", "complejidad", "complexity", "o(1)", "o(n)", "o(log",
    "big-o", "big o", "lru", "ttl", "cache", "caché", "dynamic programming",
    "programación dinámica", "recursion", "recursión", "sorting", "búsqueda binaria",
    "binary search", "hash", "árbol", "grafo", "graph", "estructura de datos",
    "data structure", "benchmark", "optimiz",
)
_DOC = (
    "documenta", "documentation", "readme", "docstring", "explica", "explain",
    "explícame", "explicame", "resume", "summar", "qué hace", "que hace",
    "cómo funciona", "como funciona", "tutorial", "guía", "guide", "comenta el código",
)
_CREATIVE_STRONG = (
    "landing", "landing page", "página de aterrizaje", "pagina de aterrizaje",
    "glassmorphism", "diseño premium", "moderna", "modern design", "portfolio",
    "hero section", "sección hero", "onepage", "one-page", "dashboard bonito",
    "web moderna", "sitio web", "página web", "pagina web", "website",
)
_GENERATION_VERBS = (
    "crea", "créame", "creame", "genera", "genérame", "generame", "implementa",
    "impleméntame", "implementame", "construye", "haz", "hazme", "escribe",
    "desarrolla", "build", "create", "generate", "implement", "make me", "write",
    "diseña", "add ", "añade", "agrega",
)
_RAG_LOOKUP = (
    "en mi proyecto", "en mi repo", "según el archivo", "segun el archivo",
    "en el archivo", "en mis documentos", "en la documentación indexada",
    "busca en", "según mis", "segun mis", "in my repo", "in my project",
    "in the indexed", "from my docs", "qué dice el documento", "que dice el documento",
    "resume el archivo", "en el pdf", "en el código del proyecto",
)
_GENERAL_TOPIC = (
    "clima", "weather", "receta", "cocina", "comida", "viaje", "película",
    "pelicula", "música", "musica", "deporte", "salud", "historia", "geografía",
    "capital de", "quién es", "quien es", "recipe", "travel", "movie",
)

# Reuse of the legacy broad code net so nothing that used to route to coder is lost.
_CODE_BROAD = _FRONTEND + _BACKEND + _PYTHON + _JS_TS + (
    "código", "codigo", "function", "función", "funcion", "class ", "regex",
    "docker", "git", "framework", "librería", "libreria", "dependencia",
    "package.json", "compil", "deploy", "script",
)


@dataclass(frozen=True)
class Classification:
    """Result of :func:`classify`."""

    categories: frozenset[str]
    regime: Regime
    is_code: bool
    is_generation: bool
    has_code_fence: bool
    num_requirements: int = 0
    num_deliverables: int = 0
    extras: dict = field(default_factory=dict)


def _count_any(text: str, needles) -> int:
    return sum(1 for n in needles if n in text)


def _count_requirements(text: str) -> int:
    """Estimate distinct requirements.

    Requirements arrive in two shapes: explicit bullet/numbered lists, and
    inline enumerations ("glassmorphism, animations, a chat, FAQ and responsive
    design"). Both count — the second is common in short-but-dense prompts,
    which the audit found are the hardest for a 7B and were being under-scored.
    """
    bullets = len(re.findall(r"(?m)^\s*[-*•]\s+", text))
    numbered = len(re.findall(r"(?m)^\s*\d+[.)]\s+", text))
    if bullets or numbered:
        return bullets + numbered
    # No explicit list: infer from inline enumeration (commas + coordinating
    # conjunctions) only when the text is a request of some length.
    commas = text.count(",")
    conj = len(re.findall(r"\b(y|e|and|además|also|con|with)\b", text.lower()))
    inline = commas + conj
    return min(inline, 8)


_DELIVERABLE_HINTS = (
    "test", "tests", "pruebas", "benchmark", "documenta", "docstring", "readme",
    "faq", "chat", "animaci", "responsive", "ejemplo", "example", "typescript",
    "types", "tipado", "comentarios", "diagrama", "seo", "accesib", "a11y",
)


def classify(text: str, history_text: str = "") -> Classification:
    """Classify one user turn into categories + a primary regime.

    ``history_text`` is optional context (previous turns) used only to keep a
    warm code regime on ambiguous follow-ups; it never overrides an explicit
    signal in ``text``.
    """
    raw = text or ""
    t = raw.lower()
    has_fence = "```" in raw or ("`" in raw and raw.count("`") >= 2)

    cats: set[str] = set()
    if _count_any(t, _FRONTEND):
        cats.add("frontend")
    if _count_any(t, _BACKEND):
        cats.add("backend")
    if _count_any(t, _PYTHON):
        cats.add("python")
    if _count_any(t, _JS_TS):
        cats.add("javascript")
    if _count_any(t, _DEBUG):
        cats.add("debugging")
    if _count_any(t, _ARCH):
        cats.add("architecture")
    if _count_any(t, _ALGO):
        cats.add("algorithm")
    if _count_any(t, _DOC):
        cats.add("documentation")
    if _count_any(t, _CREATIVE_STRONG):
        cats.add("creative")
    if _count_any(t, _RAG_LOOKUP):
        cats.add("rag_lookup")
    if _count_any(t, _GENERAL_TOPIC):
        cats.add("general")

    is_generation = bool(_count_any(t, _GENERATION_VERBS))
    if is_generation:
        cats.add("generation")

    # Explanation-question intent ("what is X", "how does Y work", "explain…").
    # A code *topic* asked as a question wants EXPLAIN, not code generation.
    is_question = bool(
        _count_any(
            t,
            (
                "qué es", "que es", "qué son", "que son", "what is", "what are",
                "cómo funciona", "como funciona", "how does", "how do", "why ",
                "por qué", "por que", "explica", "explícame", "explicame",
                "diferencia entre", "difference between", "para qué sirve",
            ),
        )
    ) or t.strip().endswith("?")

    is_code = has_fence or bool(_count_any(t, _CODE_BROAD)) or bool(
        cats & {"frontend", "backend", "python", "javascript", "algorithm", "debugging"}
    )

    num_req = _count_requirements(raw)
    num_deliv = _count_any(t, _DELIVERABLE_HINTS)

    regime = _pick_regime(cats, is_code, is_generation, is_question, history_text)

    return Classification(
        categories=frozenset(cats),
        regime=regime,
        is_code=is_code,
        is_generation=is_generation,
        has_code_fence=has_fence,
        num_requirements=num_req,
        num_deliverables=num_deliv,
    )


def _pick_regime(
    cats: set[str], is_code: bool, is_generation: bool, is_question: bool,
    history_text: str,
) -> Regime:
    """Resolve the single behaviour regime from the detected categories."""
    # Explicit lookup into the user's own indexed material → grounded QA.
    if "rag_lookup" in cats:
        return Regime.GROUNDED_QA

    # Creative UI work: landing/design, especially when asked to *create* it.
    if "creative" in cats or ("frontend" in cats and is_generation):
        return Regime.CREATIVE

    # A code *question* (what is / how does / explain), with no build verb →
    # explain regime, even though the topic is code.
    if is_code and is_question and not is_generation:
        return Regime.EXPLAIN

    # Any code build/fix intent (generate/debug/algorithm/backend) → code regime.
    if is_code and (is_generation or cats & {"debugging", "algorithm", "backend"}):
        return Regime.CODE_GEN
    if is_code and not is_question:
        return Regime.CODE_GEN

    # Pure documentation/explanation.
    if "documentation" in cats and not is_code:
        return Regime.EXPLAIN

    # Everyday/general questions with no indexed-doc reference: explain regime
    # (free generation from model knowledge), NOT grounded QA. This is the key
    # fix — the old pipeline forced these through "answer only from context".
    if "general" in cats:
        return Regime.EXPLAIN

    # Warm-follow-up affinity: if the recent history was clearly code, keep code.
    if history_text and _count_any(history_text.lower(), _CODE_BROAD):
        return Regime.CODE_GEN

    # Default: explain regime (model may use its own knowledge). Grounded QA is
    # only chosen when the user explicitly points at indexed material or when an
    # index is present and the caller opts in (handled in presets).
    return Regime.EXPLAIN
