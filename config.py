"""
TrinaxAI — Central shared configuration.

Single source of truth for models, embeddings, chunking, and retrieval.
index.py, rag_api.py, and query.py import from here to stay in sync.

Everything is overridable via environment variables (useful for systemd).
"""

from __future__ import annotations

import os
import ssl


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


# ==================== PATHS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

PERSIST_DIR = os.path.join(BASE_DIR, "storage")
LOCAL_SOURCES_DIR = os.path.join(BASE_DIR, "local_sources")
# File manifest (path -> mtime) for incremental indexing.
MANIFEST_PATH = os.path.join(PERSIST_DIR, "manifest.json")
COLLECTIONS_PATH = os.path.join(PERSIST_DIR, "collections.json")
DEFAULT_COLLECTION_ID = "default"
DEFAULT_COLLECTION_NAME = "General"

# Directory to index recursively (with subdirectories).
# Override with TRINAXAI_INDEX_DIR (e.g. ~/Documents or ~/Projects).
PROJECTS_DIRS = [
    os.path.abspath(
        os.path.expanduser(os.getenv("TRINAXAI_INDEX_DIR", os.path.dirname(BASE_DIR)))
    ),
]

# ==================== MODELS ====================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TRINAXAI_PROFILE = os.getenv("TRINAXAI_PROFILE", "16gb").strip().lower()

# Validate profile — warn on unknown values but don't crash.
_VALID_PROFILES = {
    "4gb",
    "4g",
    "8gb",
    "8g",
    "16gb",
    "max",
    "high",
    "ultra",
    "gpu",
    "64gb",
    "64g",
    "4090",
    "rtx",
    "workstation",
    "max_quality",
    "quality",
    "potente",
    "32gb",
    "32g",
    "alto",
    "low",
    "min",
    "minimo",
    "lite",
    "light",
    "bajo",
}
if TRINAXAI_PROFILE not in _VALID_PROFILES:
    print(
        f"[TrinaxAI] Unknown TRINAXAI_PROFILE='{TRINAXAI_PROFILE}'. Falling back to '16gb'."
    )
    TRINAXAI_PROFILE = "16gb"

_ULTRA_PROFILE = TRINAXAI_PROFILE in {
    "ultra",
    "gpu",
    "64gb",
    "64g",
    "4090",
    "rtx",
    "workstation",
}
_MAX_QUALITY_PROFILE = (
    TRINAXAI_PROFILE
    in {"max", "high", "max_quality", "quality", "potente", "32gb", "32g", "alto"}
    or _ULTRA_PROFILE
)
_LOW_RESOURCE_PROFILE = TRINAXAI_PROFILE in {
    "4gb",
    "4g",
    "8gb",
    "8g",
    "low",
    "min",
    "minimo",
    "lite",
    "light",
    "bajo",
}

# ── Model fleet for AUTO-ROUTING ──
# The router selects the model based on the query: chat -> general, code -> coder,
# complex -> 3b on 16gb profile or 7b on powerful profile. All NON-thinking.
MODEL_GENERAL = os.getenv("TRINAXAI_MODEL_GENERAL", "llama3.2:3b")  # non-code chat
MODEL_CODE = os.getenv("TRINAXAI_MODEL_CODE", "qwen2.5-coder:3b")  # regular code
MODEL_DEEP = os.getenv(
    "TRINAXAI_MODEL_DEEP",
    "qwen2.5-coder:14b"
    if _ULTRA_PROFILE
    else "qwen2.5-coder:7b"
    if _MAX_QUALITY_PROFILE
    else MODEL_CODE,
)  # complex code (14b on ultra, 7b on powerful profile, 3b default)
MODEL_FAST = os.getenv("TRINAXAI_MODEL_FAST", MODEL_GENERAL)  # trivial / ultra-fast

# Default model (when auto-router is disabled).
LLM_MODEL = os.getenv("TRINAXAI_LLM", MODEL_CODE)
LLM_MODEL_HEAVY = os.getenv("TRINAXAI_LLM_HEAVY", MODEL_DEEP)
AUTO_ROUTE = os.getenv("TRINAXAI_AUTO_ROUTE", "1") == "1"

# Fleet list for the PWA selector (order = preference, no duplicates).
MODEL_FLEET = list(dict.fromkeys([MODEL_CODE, MODEL_DEEP, MODEL_GENERAL, MODEL_FAST]))

# Embeddings. bge-m3 = multilingual, 1024 dims, 8K context, better than nomic.
# Embedding preset (Phase 4.1): balanced | lite | fast.
# - balanced: bge-m3 (default, best multilingual quality)
# - lite:     nomic-embed-text (smaller, faster, English-leaning)
# - fast:     all-minilm (very small, English-only, fastest)
EMBED_PRESETS = {
    "balanced": {
        "model": "bge-m3",
        "dims": 1024,
        "ctx": 8192,
        "label": "Balanced (bge-m3, multilingual)",
    },
    "lite": {
        "model": "nomic-embed-text",
        "dims": 768,
        "ctx": 2048,
        "label": "Lite (nomic-embed-text, fast)",
    },
    "fast": {
        "model": "all-minilm",
        "dims": 384,
        "ctx": 512,
        "label": "Fast (all-minilm, smallest)",
    },
}
_EMBED_PRESET = os.getenv("TRINAXAI_EMBED_PRESET", "balanced").strip().lower()
EMBED_PRESET = _EMBED_PRESET if _EMBED_PRESET in EMBED_PRESETS else "balanced"
EMBED_MODEL = os.getenv("TRINAXAI_EMBED", EMBED_PRESETS[EMBED_PRESET]["model"])
EMBED_DIMS = int(
    os.getenv("TRINAXAI_EMBED_DIMS", str(EMBED_PRESETS[EMBED_PRESET]["dims"]))
)

# Quantization hints (Phase 4.2). Ollama respects OLLAMA_NUM_GPU at runtime.
# We just expose the env var and a profile tag for the /health endpoint.
OLLAMA_NUM_GPU = os.getenv("OLLAMA_NUM_GPU", "").strip()
# Aggressive quantization toggle: 1 enables Q4_K_M-style offloading profile.
TRINAXAI_AGGRESSIVE_QUANT = os.getenv("TRINAXAI_AGGRESSIVE_QUANT", "0").strip() in {
    "1",
    "true",
    "yes",
    "on",
}

# OCR for scanned PDFs (Phase 5.1). Off by default; tesseract is a heavy system dep.
TRINAXAI_OCR = os.getenv("TRINAXAI_OCR", "0").strip() in {"1", "true", "yes", "on"}

# Context window. Must fit: prompt + top_k chunks + response.
NUM_CTX = int(
    os.getenv(
        "TRINAXAI_NUM_CTX",
        "16384"
        if _ULTRA_PROFILE
        else "8192"
        if _MAX_QUALITY_PROFILE
        else "2048"
        if _LOW_RESOURCE_PROFILE
        else "4096",
    )
)
# Threads per request. 8 (not 16) avoids oversubscription: with several concurrent
# embeddings, 16 threads/req makes slots fight for the CPU and everything goes
# SLOWER on modest hardware. 8 threads/req is usually a balanced value.
NUM_THREAD = int(os.getenv("TRINAXAI_NUM_THREAD", "8"))
# Concurrent embeddings. On 16 GB we use 2 workers to avoid competing with the
# LLM; the powerful profile bumps to 4 if RAM is free.
EMBED_WORKERS = _env_int(
    "TRINAXAI_EMBED_WORKERS",
    6
    if _ULTRA_PROFILE
    else 4
    if _MAX_QUALITY_PROFILE
    else 1
    if _LOW_RESOURCE_PROFILE
    else 2,
    minimum=1,
    maximum=16,
)
EMBED_BATCH_SIZE = _env_int(
    "TRINAXAI_EMBED_BATCH",
    16 if _ULTRA_PROFILE else 8 if not _LOW_RESOURCE_PROFILE else 2,
    minimum=1,
    maximum=64,
)
# On 16 GB we unload models after each request. The powerful profile can keep
# them warm for lower latency.
_KEEP_ALIVE_DEFAULT = "60m" if _ULTRA_PROFILE else "30m" if _MAX_QUALITY_PROFILE else "0s"
KEEP_ALIVE = os.getenv("TRINAXAI_KEEP_ALIVE", _KEEP_ALIVE_DEFAULT)
# Embeddings are many short requests during indexing/search. Keeping only the
# embedding model warm prevents Ollama from unloading/reloading it every batch,
# which otherwise causes slow sawtooth CPU/GPU/RAM usage during indexing.
if _ULTRA_PROFILE or _MAX_QUALITY_PROFILE:
    _EMBED_KEEP_ALIVE_DEFAULT = "30m"
elif _LOW_RESOURCE_PROFILE:
    _EMBED_KEEP_ALIVE_DEFAULT = "10m"
else:
    _EMBED_KEEP_ALIVE_DEFAULT = "15m"
EMBED_KEEP_ALIVE = (
    os.getenv("TRINAXAI_EMBED_KEEP_ALIVE", _EMBED_KEEP_ALIVE_DEFAULT).strip()
    or _EMBED_KEEP_ALIVE_DEFAULT
)
REQUEST_TIMEOUT = float(os.getenv("TRINAXAI_TIMEOUT", "300"))

# ==================== CHUNKING ====================
# Prose (md, txt, pdf, configs): token-based chunking.
CHUNK_SIZE = int(os.getenv("TRINAXAI_CHUNK_SIZE", "1536" if _ULTRA_PROFILE else "1024"))
CHUNK_OVERLAP = int(
    os.getenv("TRINAXAI_CHUNK_OVERLAP", "220" if _ULTRA_PROFILE else "150")
)
# Code: AST-based chunking (respects functions/classes), measured in lines.
CODE_CHUNK_LINES = int(os.getenv("TRINAXAI_CODE_CHUNK_LINES", "60"))
CODE_CHUNK_LINES_OVERLAP = int(os.getenv("TRINAXAI_CODE_CHUNK_LINES_OVERLAP", "12"))
CODE_MAX_CHARS = int(os.getenv("TRINAXAI_CODE_MAX_CHARS", "2000"))

# ==================== RETRIEVAL ====================
# Final chunks injected into the LLM as context.
SIMILARITY_TOP_K = int(
    os.getenv("TRINAXAI_SIMILARITY_TOP_K", "8" if _ULTRA_PROFILE else "5")
)
# Candidates each retriever (vector / BM25) contributes before fusion.
# With reranking we ask for MORE candidates (the reranker narrows to the best).
FUSION_CANDIDATES = int(
    os.getenv(
        "TRINAXAI_FUSION_CANDIDATES",
        "32"
        if _ULTRA_PROFILE
        else "20"
        if _MAX_QUALITY_PROFILE
        else "8"
        if _LOW_RESOURCE_PROFILE
        else "12",
    )
)

# ── RERANKING (cross-encoder, big precision boost) ──
# Reorders candidates by real relevance to the query before passing them
# to the LLM. bge-reranker-v2-m3 = multilingual (Spanish), state of the art.
RERANK_ENABLED = os.getenv("TRINAXAI_RERANK", "0") == "1"
RERANK_MODEL = os.getenv("TRINAXAI_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_TOP_N = int(os.getenv("TRINAXAI_RERANK_TOP_N", str(SIMILARITY_TOP_K)))


def make_llm(temperature: float = 0.0, model: str | None = None) -> Ollama:
    """Create the Ollama LLM (qwen2.5-coder: non-thinking, fast on CPU)."""
    from llama_index.llms.ollama import Ollama

    return Ollama(
        model=model or LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        request_timeout=REQUEST_TIMEOUT,
        keep_alive=KEEP_ALIVE,
        context_window=NUM_CTX,
        additional_kwargs={"num_ctx": NUM_CTX, "num_thread": NUM_THREAD},
    )


def make_embed() -> OllamaEmbedding:
    """Create the Ollama embedder using bge-m3's full 8K window."""
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
        keep_alive=EMBED_KEEP_ALIVE,
        embed_batch_size=EMBED_BATCH_SIZE,
        num_workers=EMBED_WORKERS,  # concurrent requests to Ollama
        # Ultra uses larger chunks; the rest keep context bounded for RAM.
        ollama_additional_kwargs={
            "num_thread": NUM_THREAD,
            "num_ctx": 4096 if _ULTRA_PROFILE else 2048,
        },
    )


# ==================== EXTENSION -> LANGUAGE MAP (tree-sitter) ====================
# Extensions with a reliable AST parser. The rest fall back to token chunking.
CODE_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".cjs": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".html": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".sh": "bash",
    ".sql": "sql",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".rs": "rust",
    ".vue": "html",
    ".svelte": "html",
}

# Extensions to index (code + prose + documents).
REQUIRED_EXTS = [
    # code
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".vue",
    ".svelte",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".rs",
    ".sh",
    ".ps1",
    ".dockerfile",
    ".sql",
    ".graphql",
    ".cjs",
    ".mjs",
    # config / data
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".xml",
    ".ini",
    ".csv",
    # prose / documents
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".pdf",
    ".docx",
]

# Aggressive exclusion: third-party deps, builds, binaries, caches.
# This is "the useless stuff" — installed libraries, not your code/content.
# NOTE: EXCLUDE_PATTERNS is consumed by SimpleDirectoryReader's exclude kwarg
# in index.py (load_docs function) to skip matching files at the reader level.
EXCLUDE_PATTERNS = [
    # dependencies and environments
    "**/node_modules/**",
    "**/.git/**",
    "**/.svn/**",
    "**/venv/**",
    "**/.venv/**",
    "**/env/**",
    "**/site-packages/**",
    "**/Lib/**",
    "**/lib/python*/**",
    "**/.tox/**",
    "**/.nox/**",
    "**/*.egg-info/**",
    "**/*.dist-info/**",
    # builds and outputs
    "**/dist/**",
    "**/build/**",
    "**/.next/**",
    "**/.nuxt/**",
    "**/out/**",
    "**/.output/**",
    "**/.firebase/**",
    "**/.vercel/**",
    "**/coverage/**",
    "**/.cache/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    # editors / tools
    "**/.idea/**",
    "**/.vscode/**",
    "**/.continue/**",
    "**/.github/**",
    # the index itself and backups
    "**/storage/**",
    "**/storage.bak*/**",
    # logs and runtime artifacts
    "**/logs/**",
    # generated / minified / lockfiles
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",
    "**/*.log",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/poetry.lock",
    "**/composer.lock",
]

# Folder names to PRUNE during traversal (do not descend into them).
# Much faster than enumerating everything and filtering afterwards.
EXCLUDE_DIR_NAMES = {
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    "venv",
    ".venv",
    "env",
    ".env",
    "site-packages",
    "Lib",
    "lib64",
    ".tox",
    ".nox",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "out",
    ".output",
    ".firebase",
    ".vercel",
    "coverage",
    ".cache",
    ".idea",
    ".vscode",
    ".continue",
    ".github",
    "storage",
    "storage.bak.nomic",
    "logs",
    "certs",
    "backups",
}

# Max size per file. Avoids giant generated CSV/HTML that would produce
# thousands of useless chunks. Generous but bounded.
MAX_FILE_BYTES = int(os.getenv("TRINAXAI_MAX_FILE_BYTES", str(3 * 1024 * 1024)))
UPLOAD_MAX_FILES = int(os.getenv("TRINAXAI_UPLOAD_MAX_FILES", "2500"))
UPLOAD_MAX_BYTES = int(os.getenv("TRINAXAI_UPLOAD_MAX_BYTES", str(512 * 1024 * 1024)))


# ==================== MODEL AUTO-ROUTER ====================
# Hints that the query is CODE-related.
_CODE_HINTS = (
    "código",
    "codigo",
    "function",
    "función",
    "funcion",
    "def ",
    "class ",
    "import",
    "const ",
    "let ",
    "var ",
    "react",
    "python",
    "javascript",
    "typescript",
    "html",
    "css",
    "api",
    "endpoint",
    "sql",
    "query",
    "regex",
    "bug",
    "error",
    "traceback",
    "exception",
    "compil",
    "deploy",
    "docker",
    "git",
    "npm",
    "vite",
    "tailwind",
    "componente",
    "librería",
    "libreria",
    "dependencia",
    "framework",
    "archivo",
    "script",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    "package.json",
)
# Hints the query is COMPLEX (deserves the larger 7b/14b model).
_DEEP_HINTS = (
    "refactor",
    "optimiz",
    "arquitect",
    "architecture",
    "depura",
    "debug",
    "por qué",
    "porque falla",
    "explica a fondo",
    "paso a paso",
    "detalle",
    "rendimiento",
    "performance",
    "seguridad",
    "security",
    "diseña",
    "implementa",
    "completo",
    "varios archivos",
    "compara",
    "analiza",
    "revisa",
)


def route_model(text: str) -> str:
    """Pick the best model based on the query (heuristic, offline, instant).

    Complex -> 7b/14b · Code -> coder 3b · Chat -> general. Trivial -> fast.
    """
    if not AUTO_ROUTE or not text:
        return LLM_MODEL
    t = text.lower()
    is_code = ("`" in text) or any(h in t for h in _CODE_HINTS)
    is_deep = len(text) > 600 or any(h in t for h in _DEEP_HINTS)
    if is_deep:
        return MODEL_DEEP  # complex (code or not) -> large model
    if is_code:
        return MODEL_CODE  # regular code -> coder 3b
    if len(text.strip()) < 25:
        return MODEL_FAST  # greeting / trivial -> ultra-fast
    return MODEL_GENERAL  # general chat -> llama3.2


def make_reranker():
    """Create the cross-encoder reranker (or None if disabled/unavailable).

    Loads the model into RAM (~2 GB) once. GREATLY improves RAG precision:
    reorders candidates by real relevance to the query.
    """
    if not RERANK_ENABLED:
        return None
    try:
        try:
            from llama_index.core.postprocessor import SentenceTransformerRerank
        except ImportError:
            from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank
        return SentenceTransformerRerank(model=RERANK_MODEL, top_n=RERANK_TOP_N)
    except (ImportError, ModuleNotFoundError, OSError) as e:  # torch/sentence-transformers not installed, etc.
        print(f"[TrinaxAI] Reranker disabled ({str(e)[:80]})")
        return None


def project_of(file_path: str) -> str:
    """First segment of the relative path = project/folder name."""
    try:
        rel = os.path.relpath(file_path, PROJECTS_DIRS[0])
    except ValueError:
        return "(unknown)"
    rel = rel.replace("\\", "/")
    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else "(root)"


# ── TLS / SSL ──
TLS_VERIFY = os.getenv("TRINAXAI_TLS_VERIFY", "0") == "1"


def create_ssl_context(verify: bool | None = None) -> "ssl.SSLContext | None":
    """Return an SSL context respecting TRINAXAI_TLS_VERIFY.

    When verify is False (the default for localhost self-signed certs),
    returns a context that skips hostname checking and certificate verification.
    When verify is True, returns None so urllib uses the default secure context.
    """
    if verify is None:
        verify = TLS_VERIFY
    if verify:
        return None  # Use default secure context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
