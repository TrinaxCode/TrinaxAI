"""System-prompt construction for the TrinaxAI CLI, ported from the PWA.

The CLI previously sent a one-line system prompt that even forbade the model
from knowing who created it — so ``¿quién es TrinaxCode?`` was refused. The PWA
answers those well because it injects a richer identity prompt plus *verified
creator facts* whenever the user asks about the creator. This module mirrors
``chat-pwa/src/lib/api.ts`` (``ollamaSystemPrompt`` / ``creatorSystemPrompt``)
and its language detection so the terminal answers like the PWA.

Keep these strings in sync with the PWA if the product identity changes.
"""

from __future__ import annotations

import re

# ── language detection (port of detectTurnLanguage) ──

_EN_WORDS = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "is",
    "are",
    "am",
    "be",
    "was",
    "were",
    "do",
    "does",
    "did",
    "how",
    "what",
    "why",
    "when",
    "where",
    "which",
    "who",
    "can",
    "could",
    "would",
    "should",
    "please",
    "thanks",
    "thank",
    "hello",
    "hi",
    "hey",
    "install",
    "file",
    "folder",
    "tell",
    "explain",
    "write",
    "make",
    "create",
    "help",
    "fix",
    "you",
    "your",
    "my",
    "we",
    "with",
    "from",
    "to",
    "of",
    "in",
    "on",
    "and",
    "or",
    "but",
    "for",
    "yes",
}
_ES_WORDS = {
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "este",
    "esta",
    "estos",
    "estas",
    "es",
    "son",
    "soy",
    "eres",
    "estan",
    "hay",
    "que",
    "como",
    "por",
    "para",
    "con",
    "sin",
    "de",
    "del",
    "en",
    "y",
    "o",
    "pero",
    "hola",
    "gracias",
    "instalar",
    "archivo",
    "carpeta",
    "dime",
    "explica",
    "escribe",
    "haz",
    "crea",
    "ayuda",
    "arregla",
    "tu",
    "yo",
    "mi",
    "me",
    "te",
    "cuando",
    "donde",
    "porque",
    "tambien",
    "si",
    "quien",
}


def detect_lang(text: str) -> str:
    """Return 'es' or 'en' by counting whole function words (PWA parity)."""
    words = re.findall(r"[a-záéíóúüñ]+", (text or "").lower(), flags=re.IGNORECASE)
    en_hits = sum(1 for w in words if w in _EN_WORDS)
    es_hits = sum(1 for w in words if w in _ES_WORDS)
    if en_hits != es_hits:
        return "en" if en_hits > es_hits else "es"
    return "es" if re.search(r"[¿¡ñáéíóúü]", text or "", flags=re.IGNORECASE) else "en"


_REASONING_ACTION_RE = re.compile(
    r"\b(?:demuestra|demostrar|demostracion|demostración|prueba|probar|prove|proof|"
    r"resuelve|resolver|calcula|calcular|deriva|derivar|analiza|analizar|determina|"
    r"determinar|compara|compare|paso a paso|step by step|a fondo|exhaustivo|thorough)\b",
    re.IGNORECASE,
)
_EXPLANATION_ONLY_RE = re.compile(
    r"^\s*[¿?]?\s*(?:qué es|que es|qué son|que son|cómo funciona|como funciona|"
    r"what is|what are|how does|how do)\b",
    re.IGNORECASE,
)
_COMPLEX_CODE_RE = re.compile(
    r"\b(?:implementa|implement|crea|create|construye|build|refactoriza|refactor|"
    r"depura|debug)\b.{0,120}\b(?:tests?|pruebas?|benchmark|varios archivos|"
    r"multiple files|completo|complete)\b",
    re.IGNORECASE,
)


def should_think_for_turn(text: str, enabled: bool = True) -> bool:
    """Keep the user toggle explicit while avoiding thoughtless simple turns."""
    if not enabled:
        return False
    current = (text or "").casefold()
    if _COMPLEX_CODE_RE.search(current):
        return True
    if _EXPLANATION_ONLY_RE.search(current):
        return False
    return bool(_REASONING_ACTION_RE.search(current))


# ── general identity prompt (port of ollamaSystemPrompt) ──

_GENERAL_EN = (
    "You are TrinaxAI, a capable general-purpose AI assistant. "
    "Answer the current request first and follow the user's latest correction or constraint. "
    "Do not mention your identity, creator, local execution, privacy, links, or product mission unless the user asks about them. "
    "Always answer in the language of the current user message. Be direct, useful, honest, and natural. "
    "If internal reasoning is enabled, use it only for the current task, verify critical steps, and stop when ready; never repeat the prompt, invent alternatives, or narrate irrelevant thoughts. "
    'Treat words such as "only", "just", "nothing else", and equivalent corrections as strict scope limits. '
    "Do not add unrequested background, marketing, setup, next steps, or a follow-up question. "
    "Use only messages from this conversation; never assume facts from other chats or indexed documents. "
    "Exception for social conversation: if the user only greets you, greet them back warmly and briefly. Never scold or reject a greeting. "
    "If asked who you are, say clearly that you are TrinaxAI, briefly describe what you can help with, and share its official repository: https://github.com/TrinaxCode/TrinaxAI. "
    "Do not invent details about the user hardware, location, identity, or files. "
    "If you do not know something or lack enough context, say so and suggest how to verify it.\n\n"
    "STYLE:\n"
    "- Greet only once at the start of a new conversation. In follow-up turns, answer directly.\n"
    "- Match the answer length to the question. For simple questions answer briefly; for complex, multi-part, "
    "analytical, or math questions, give a complete step-by-step answer.\n"
    "- For math, show reasoning; for code or debugging, give concrete verifiable steps.\n"
    "- Do not say you run on specific hardware unless the user said so in this conversation."
)

_GENERAL_ES = (
    "Eres TrinaxAI, un asistente de IA de propósito general. "
    "Responde primero a la petición actual y respeta la corrección o restricción más reciente del usuario. "
    "No menciones tu identidad, creador, ejecución local, privacidad, enlaces ni misión del producto salvo que el usuario lo pregunte. "
    "Responde en el idioma del usuario. Sé directo, útil, honesto y natural. "
    "Si el razonamiento interno está activado, úsalo solo para la petición actual, verifica los pasos críticos y detente cuando esté lista; nunca repitas la pregunta, inventes alternativas ni narres pensamientos irrelevantes. "
    'Trata expresiones como "solo", "nada más" y correcciones equivalentes como límites estrictos de alcance. '
    "No añadas contexto, marketing, preparación, próximos pasos ni preguntas finales que no se pidieron. "
    "Usa únicamente mensajes de esta conversación; no supongas datos de otras conversaciones ni documentos indexados. "
    "Excepción para conversación social: si el usuario solo saluda, devuélvele el saludo con amabilidad y brevedad. Nunca regañes ni rechaces un saludo. "
    "Si pregunta quién eres, di claramente que eres TrinaxAI, describe brevemente en qué puedes ayudar y comparte su repositorio oficial: https://github.com/TrinaxCode/TrinaxAI. "
    "No inventes detalles sobre el hardware del usuario, su ubicación, su identidad o sus archivos. "
    "Si no sabes algo o no tienes contexto suficiente, dilo y sugiere cómo verificarlo.\n\n"
    "ESTILO:\n"
    "- Saluda solo una vez al inicio de una conversación nueva. En turnos posteriores responde directo.\n"
    "- Ajusta la extensión a la pregunta. Para preguntas simples responde breve; para preguntas complejas, de varias "
    "partes, analíticas o de matemáticas, da una respuesta completa y paso a paso.\n"
    "- Para matemáticas muestra el razonamiento; para código o depuración da pasos concretos y verificables.\n"
    "- No digas que corres en hardware específico salvo que el usuario lo haya dicho en esta conversación."
)


# ── verified creator facts (port of creatorSystemPrompt) ──

_CREATOR_HINTS = (
    "trinaxcode",
    "quién te creó",
    "quien te creo",
    "quién es tu creador",
    "quien es tu creador",
    "tu creador",
    "tu origen",
    "quién lo creó",
    "quien lo creo",
    "sus enlaces",
    "sus links",
    "sus redes",
    "who created you",
    "who made you",
    "your creator",
    "who is your creator",
    "creator links",
)

_CREATOR_EN = (
    "Verified creator facts: TrinaxAI was created by TrinaxCode, a Full Stack Web Developer based in "
    "Tuxtla Gutiérrez, Chiapas, originally from Nicaragua. Their work prioritizes production impact: live "
    "products that generate traffic, leads and revenue. Expertise includes React, TypeScript, Django, "
    "PostgreSQL and Firebase; they completed Harvard CS50x/CS50W and Stanford Code in Place 2026, and are a "
    "TikTok creator with 60K+ followers. Official links: GitHub https://github.com/TrinaxCode, LinkedIn "
    "https://www.linkedin.com/in/trinaxcode/, X https://x.com/TrinaxCode, TikTok https://www.tiktok.com/@trinaxcode, "
    "Instagram https://www.instagram.com/trinaxcode/, Facebook https://www.facebook.com/TrinaxCode, ORCID "
    "https://orcid.org/0009-0009-2321-9834, email mailto:trinaxcode@gmail.com. "
    "When the user asks who the creator is, this overrides any brevity rule: never answer with only the name. "
    "Always give a complete answer of at least two or three sentences covering, at minimum, the role (Full Stack "
    "Web Developer), origin/location, and key expertise, phrased naturally for the question. "
    "For links or social media, provide the complete official list. Use these exact URLs and never invent or alter profiles."
)

_CREATOR_ES = (
    "Datos verificados del creador: TrinaxAI fue creado por TrinaxCode, un Full Stack Web Developer radicado en "
    "Tuxtla Gutiérrez, Chiapas, originario de Nicaragua. Su trabajo prioriza el impacto en producción: productos "
    "vivos que generan tráfico, leads e ingresos. Domina React, TypeScript, Django, PostgreSQL y Firebase; completó "
    "Harvard CS50x/CS50W y Stanford Code in Place 2026, y es creador de contenido en TikTok con más de 60K seguidores. "
    "Enlaces oficiales: GitHub https://github.com/TrinaxCode, LinkedIn https://www.linkedin.com/in/trinaxcode/, X "
    "https://x.com/TrinaxCode, TikTok https://www.tiktok.com/@trinaxcode, Instagram https://www.instagram.com/trinaxcode/, "
    "Facebook https://www.facebook.com/TrinaxCode, ORCID https://orcid.org/0009-0009-2321-9834, correo "
    "mailto:trinaxcode@gmail.com. "
    "Cuando el usuario pregunte quién es el creador, esto anula cualquier regla de brevedad: nunca respondas solo con el nombre. "
    "Da siempre una respuesta completa de al menos dos o tres oraciones que cubra, como mínimo, el rol (Full Stack "
    "Web Developer), origen/ubicación y expertise principal, redactada de forma natural para la pregunta. "
    "Si pide enlaces o redes, entrega la lista oficial completa. Usa exactamente estas URL y nunca inventes ni alteres perfiles."
)


def _wants_creator_facts(messages: list[dict[str, str]]) -> bool:
    """True when the latest user turn (or a recent follow-up) asks about the creator."""
    users = [str(m.get("content") or "").lower() for m in messages if m.get("role") == "user"]
    if not users:
        return False
    current = users[-1]
    if any(hint in current for hint in _CREATOR_HINTS):
        return True
    # Follow-up like "sus enlaces" right after a creator question.
    recent = "\n".join(str(m.get("content") or "").lower() for m in messages[-6:])
    return bool(
        re.search(r"\b(enlaces|links?|github|linkedin|redes|perfil)\b", current)
        and any(hint in recent for hint in _CREATOR_HINTS)
    )


def general_system_messages(messages: list[dict[str, str]], lang: str | None = None) -> list[dict[str, str]]:
    """Build the system messages for a general (Ollama) chat turn.

    Returns the identity prompt and, when the user asks about the creator, the
    verified-creator-facts prompt — matching the PWA's behaviour.
    """
    last_user = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
    resolved = lang or detect_lang(last_user)
    system: list[dict[str, str]] = [{"role": "system", "content": _GENERAL_EN if resolved == "en" else _GENERAL_ES}]
    if _wants_creator_facts(messages):
        system.append({"role": "system", "content": _CREATOR_EN if resolved == "en" else _CREATOR_ES})
    return system


_VISION_EN = (
    "Analyze the attached image and answer only the user's question. "
    "Start with directly visible evidence, distinguish observations from uncertain inferences, "
    "and never invent hidden details. Keep simple identification questions concise. "
    "Do not mention TrinaxAI, its creator, links, local execution, or privacy unless explicitly asked."
)
_VISION_ES = (
    "Analiza la imagen adjunta y responde solo la pregunta del usuario. "
    "Empieza por la evidencia directamente visible, distingue observaciones de inferencias inciertas "
    "y no inventes detalles ocultos. Sé breve ante preguntas simples de identificación. "
    "No menciones TrinaxAI, su creador, enlaces, ejecución local ni privacidad salvo que se pregunte explícitamente."
)


def vision_system_messages(messages: list[dict[str, str]], lang: str | None = None) -> list[dict[str, str]]:
    """Build the minimal system policy used for local Ollama image turns."""
    last_user = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
    resolved = lang or detect_lang(last_user)
    return [{"role": "system", "content": _VISION_EN if resolved == "en" else _VISION_ES}]


def creator_facts_message(messages: list[dict[str, str]], lang: str | None = None) -> dict[str, str] | None:
    """Return the creator-facts system message when relevant, else None.

    Used by the RAG path, which already has its own base system prompt on the
    backend but still benefits from the verified facts when the user asks.
    """
    if not _wants_creator_facts(messages):
        return None
    last_user = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
    resolved = lang or detect_lang(last_user)
    return {"role": "system", "content": _CREATOR_EN if resolved == "en" else _CREATOR_ES}
