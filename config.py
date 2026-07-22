"""
TrinaxAI — Central shared configuration.

Single source of truth for models, embeddings, chunking, and retrieval.
index.py and the API services import from here to stay in sync.

Everything is overridable via environment variables (useful for systemd).
"""

from __future__ import annotations

import logging
import os
import ssl
from typing import TYPE_CHECKING, Any

from trinaxai_core import VALID_PROFILES, _positive_float, _positive_int, normalize_http_base_url

LOG = logging.getLogger("trinaxai.config")

if TYPE_CHECKING:
    from llama_index.embeddings.ollama import OllamaEmbedding
    from llama_index.llms.ollama import Ollama


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    """Read an int env var, clamped to [minimum, maximum]; falls back on bad input.

    Thin wrapper over ``trinaxai_core._positive_int`` so parsing/clamping stays
    consistent across config/index/core.
    """
    return _positive_int(os.getenv(name, default), default, minimum=minimum, maximum=maximum)


def _env_float(name: str, default: float, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    """Read a float env var, clamped; falls back on bad input."""
    return _positive_float(os.getenv(name, default), default, minimum=minimum, maximum=maximum)


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
    os.path.abspath(os.path.expanduser(os.getenv("TRINAXAI_INDEX_DIR", os.path.dirname(BASE_DIR)))),
]

# ==================== MODELS ====================
OLLAMA_BASE_URL = normalize_http_base_url(os.getenv("OLLAMA_BASE_URL"), "http://localhost:11434")
TRINAXAI_PROFILE = os.getenv("TRINAXAI_PROFILE", "16gb").strip().lower()
TRINAXAI_PERFORMANCE_MODE = os.getenv("TRINAXAI_PERFORMANCE_MODE", "fast").strip().lower() or "fast"
if TRINAXAI_PERFORMANCE_MODE not in {"fast", "balanced", "quality"}:
    LOG.warning(
        "Unknown TRINAXAI_PERFORMANCE_MODE=%r; falling back to 'fast'",
        TRINAXAI_PERFORMANCE_MODE,
    )
    TRINAXAI_PERFORMANCE_MODE = "fast"

# Validate profile — warn on unknown values but don't crash.
if TRINAXAI_PROFILE not in VALID_PROFILES:
    LOG.warning(
        "Unknown TRINAXAI_PROFILE=%r; falling back to '16gb'",
        TRINAXAI_PROFILE,
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
    TRINAXAI_PROFILE in {"max", "high", "max_quality", "quality", "potente", "32gb", "32g", "alto"} or _ULTRA_PROFILE
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
_FAST_MODE = TRINAXAI_PERFORMANCE_MODE == "fast"
_QUALITY_MODE = TRINAXAI_PERFORMANCE_MODE == "quality"

# ── Model fleet for AUTO-ROUTING ──
# The router selects the model based on the query. Low-resource profiles default
# to smaller models so Windows laptops with 8 GB RAM do not pull the 16 GB set.
#
# Each tier leaves room for the embedding model and runtime overhead instead of
# sizing the chat model as if it were the only resident process.
_PROFILE_MODEL = (
    "qwen3.5:35b"
    if _ULTRA_PROFILE
    else "qwen3.5:9b"
    if _MAX_QUALITY_PROFILE
    else "qwen3.5:2b"
    if _LOW_RESOURCE_PROFILE
    else "qwen3.5:4b"
)
_DEFAULT_MODEL_GENERAL = _PROFILE_MODEL
_DEFAULT_MODEL_CODE = "qwen3-coder:30b" if _ULTRA_PROFILE else _PROFILE_MODEL
_DEFAULT_MODEL_FAST = "qwen3.5:4b" if _ULTRA_PROFILE else "qwen3.5:2b"
MODEL_GENERAL = os.getenv("TRINAXAI_MODEL_GENERAL", _DEFAULT_MODEL_GENERAL)  # non-code chat
MODEL_CODE = os.getenv("TRINAXAI_MODEL_CODE", _DEFAULT_MODEL_CODE)  # regular code
MODEL_DEEP = os.getenv(
    "TRINAXAI_MODEL_DEEP",
    _PROFILE_MODEL,
)  # complex reasoning/code
MODEL_FAST = os.getenv("TRINAXAI_MODEL_FAST", _DEFAULT_MODEL_FAST)  # trivial / ultra-fast

# Default model (when auto-router is disabled).
LLM_MODEL = os.getenv("TRINAXAI_LLM", MODEL_CODE)
LLM_MODEL_HEAVY = os.getenv("TRINAXAI_LLM_HEAVY", MODEL_DEEP)
AUTO_ROUTE = os.getenv("TRINAXAI_AUTO_ROUTE", "1") == "1"

# Fleet list for the PWA selector (order = preference, no duplicates).
MODEL_FLEET = list(dict.fromkeys([MODEL_CODE, MODEL_DEEP, MODEL_GENERAL, MODEL_FAST]))

# Embeddings. Qwen3 Embedding is multilingual, instruction-aware, and supports
# 32K context while keeping the same 1024 dimensions at 0.6B.
# Embedding preset (Phase 4.1): balanced | lite | fast.
# - balanced: Qwen3 Embedding 0.6B (multilingual, instruction-aware)
# - lite:     nomic-embed-text (smaller, faster, English-leaning)
# - fast:     all-minilm (very small, English-only, fastest)
EMBED_PRESETS = {
    "balanced": {
        "model": "qwen3-embedding:0.6b",
        "dims": 1024,
        "ctx": 8192,
        "label": "Balanced (Qwen3 Embedding 0.6B, multilingual)",
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
# The 0.6B preset stays practical on CPU-only laptops; larger embedding models
# cost too much latency and resident memory beside the generation model.
_EMBED_PRESET_DEFAULT = "balanced"
_EMBED_PRESET = os.getenv("TRINAXAI_EMBED_PRESET", _EMBED_PRESET_DEFAULT).strip().lower()
EMBED_PRESET = _EMBED_PRESET if _EMBED_PRESET in EMBED_PRESETS else "balanced"
EMBED_MODEL = os.getenv("TRINAXAI_EMBED", EMBED_PRESETS[EMBED_PRESET]["model"])
EMBED_DIMS = _env_int("TRINAXAI_EMBED_DIMS", int(EMBED_PRESETS[EMBED_PRESET]["dims"]), minimum=1, maximum=32768)

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
NUM_CTX = _env_int(
    "TRINAXAI_NUM_CTX",
    16384 if _ULTRA_PROFILE else 8192 if _MAX_QUALITY_PROFILE else 2048 if _LOW_RESOURCE_PROFILE else 4096,
    minimum=512,
    maximum=131072,
)
# Threads per request. 8 (not 16) avoids oversubscription: with several concurrent
# embeddings, 16 threads/req makes slots fight for the CPU and everything goes
# SLOWER on modest hardware. 8 threads/req is usually a balanced value.
NUM_THREAD = _env_int("TRINAXAI_NUM_THREAD", 8, minimum=1, maximum=256)
# Concurrent embeddings. Indexing runs as its own subprocess with NO LLM loaded
# (index.py never sets Settings.llm), so the embedder gets the whole CPU — the
# old "avoid competing with the LLM" cap of 2 left modern multi-core laptops
# (e.g. an 8-core/16-thread Ryzen) idle. The 16 GB profile now issues 4 parallel
# requests to Ollama; still fully overridable for RAM-tight machines.
EMBED_WORKERS = _env_int(
    "TRINAXAI_EMBED_WORKERS",
    6 if _ULTRA_PROFILE else 4 if _MAX_QUALITY_PROFILE else 1 if _LOW_RESOURCE_PROFILE else 4,
    minimum=1,
    maximum=16,
)
EMBED_BATCH_SIZE = _env_int(
    "TRINAXAI_EMBED_BATCH",
    16 if _ULTRA_PROFILE else 8 if not _LOW_RESOURCE_PROFILE else 1,
    minimum=1,
    maximum=64,
)
# Fast mode keeps the local model warm so the next response does not pay the
# Ollama load cost again. Low-memory users can still set TRINAXAI_KEEP_ALIVE=0s.
_KEEP_ALIVE_DEFAULT = (
    "60m"
    if _ULTRA_PROFILE
    else "30m"
    if _MAX_QUALITY_PROFILE
    else "10m"
    if _FAST_MODE and not _LOW_RESOURCE_PROFILE
    else "0s"
)
KEEP_ALIVE = os.getenv("TRINAXAI_KEEP_ALIVE", _KEEP_ALIVE_DEFAULT)
# Embeddings are many short requests during indexing/search. Keeping only the
# embedding model warm prevents Ollama from unloading/reloading it every batch,
# which otherwise causes slow sawtooth CPU/GPU/RAM usage during indexing.
if _ULTRA_PROFILE or _MAX_QUALITY_PROFILE:
    _EMBED_KEEP_ALIVE_DEFAULT = "30m"
elif _LOW_RESOURCE_PROFILE:
    _EMBED_KEEP_ALIVE_DEFAULT = "0s"
else:
    _EMBED_KEEP_ALIVE_DEFAULT = "15m"
EMBED_KEEP_ALIVE = (
    os.getenv("TRINAXAI_EMBED_KEEP_ALIVE", _EMBED_KEEP_ALIVE_DEFAULT).strip() or _EMBED_KEEP_ALIVE_DEFAULT
)
REQUEST_TIMEOUT = _env_float("TRINAXAI_TIMEOUT", 300.0, minimum=1.0, maximum=86400.0)

# ==================== WEB SEARCH ====================
# ``auto`` prefers a configured Brave key, then a configured SearXNG instance,
# and finally DuckDuckGo HTML search (no account required). Search is only
# invoked when a caller opts in or explicitly asks TrinaxAI to search online.
WEB_SEARCH_PROVIDER = os.getenv("TRINAXAI_WEB_SEARCH_PROVIDER", "auto").strip().lower() or "auto"
WEB_SEARCH_BRAVE_API_KEY = os.getenv("TRINAXAI_BRAVE_SEARCH_API_KEY", "").strip()
WEB_SEARCH_SEARXNG_URL = os.getenv("TRINAXAI_SEARXNG_URL", "").strip()
WEB_SEARCH_TIMEOUT = _env_float("TRINAXAI_WEB_SEARCH_TIMEOUT", 15.0, minimum=2.0, maximum=120.0)
WEB_SEARCH_MAX_RESULTS = _env_int("TRINAXAI_WEB_SEARCH_MAX_RESULTS", 6, minimum=1, maximum=10)
WEB_SEARCH_CACHE_SECONDS = _env_int("TRINAXAI_WEB_SEARCH_CACHE_SECONDS", 300, minimum=0, maximum=86400)

# ==================== CHUNKING ====================
# Prose (md, txt, pdf, configs): token-based chunking.
_CHUNK_SIZE_DEFAULT = 1536 if _ULTRA_PROFILE else 896 if _FAST_MODE else 1024
CHUNK_SIZE = _env_int("TRINAXAI_CHUNK_SIZE", _CHUNK_SIZE_DEFAULT, minimum=64, maximum=8192)
CHUNK_OVERLAP = _env_int(
    "TRINAXAI_CHUNK_OVERLAP",
    220 if _ULTRA_PROFILE else 96 if _FAST_MODE else 150,
    minimum=0,
    maximum=CHUNK_SIZE,
)
# Code: AST-based chunking (respects functions/classes), measured in lines.
CODE_CHUNK_LINES = _env_int("TRINAXAI_CODE_CHUNK_LINES", 60, minimum=1, maximum=10000)
CODE_CHUNK_LINES_OVERLAP = _env_int(
    "TRINAXAI_CODE_CHUNK_LINES_OVERLAP", 8 if _FAST_MODE else 12, minimum=0, maximum=CODE_CHUNK_LINES
)
CODE_MAX_CHARS = _env_int("TRINAXAI_CODE_MAX_CHARS", 2000, minimum=100, maximum=100000)

# ==================== RETRIEVAL ====================
# Final chunks injected into the LLM as context.
_TOP_K_DEFAULT = (
    "8"
    if _ULTRA_PROFILE and _QUALITY_MODE
    else "6"
    if _ULTRA_PROFILE
    else "5"
    if _MAX_QUALITY_PROFILE
    else "3"
    if _LOW_RESOURCE_PROFILE and _FAST_MODE
    else "4"
    if _FAST_MODE
    else "5"
)
SIMILARITY_TOP_K = _env_int("TRINAXAI_SIMILARITY_TOP_K", int(_TOP_K_DEFAULT), minimum=1, maximum=100)
# Candidates each retriever (vector / BM25) contributes before fusion.
# With reranking we ask for MORE candidates (the reranker narrows to the best).
_FUSION_CANDIDATES_DEFAULT = (
    "32"
    if _ULTRA_PROFILE and _QUALITY_MODE
    else "20"
    if _ULTRA_PROFILE
    else "12"
    if _MAX_QUALITY_PROFILE
    else "6"
    if _LOW_RESOURCE_PROFILE and _FAST_MODE
    else "8"
    if _FAST_MODE
    else "12"
)
FUSION_CANDIDATES = _env_int("TRINAXAI_FUSION_CANDIDATES", int(_FUSION_CANDIDATES_DEFAULT), minimum=1, maximum=200)
RETRIEVAL_CACHE_SECONDS = _env_int(
    "TRINAXAI_RETRIEVAL_CACHE_SECONDS", 20 if _FAST_MODE else 10, minimum=0, maximum=3600
)
SOURCES_CACHE_SECONDS = _env_int("TRINAXAI_SOURCES_CACHE_SECONDS", 30 if _FAST_MODE else 15, minimum=0, maximum=3600)

# ── RERANKING (cross-encoder, big precision boost) ──
# Reorders candidates by real relevance to the query before passing them
# to the LLM. bge-reranker-v2-m3 = multilingual (Spanish), state of the art.
RERANK_ENABLED = os.getenv("TRINAXAI_RERANK", "0") == "1"
RERANK_MODEL = os.getenv("TRINAXAI_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_TOP_N = _env_int("TRINAXAI_RERANK_TOP_N", SIMILARITY_TOP_K, minimum=1, maximum=100)


def make_llm(
    temperature: float = 0.0,
    model: str | None = None,
    *,
    keep_alive: str | int | None = None,
    aggressive_quant: bool | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    repeat_penalty: float | None = None,
    stop: tuple[str, ...] | list[str] | None = None,
) -> Ollama:
    """Create the configured Ollama LLM.

    The sampling knobs (``num_ctx``/``num_predict``/``top_p``/``top_k``/
    ``repeat_penalty``/``stop``) are optional and backwards-compatible: when a
    caller passes ``None`` the parameter is simply not sent, reproducing the
    historical behaviour (only ``num_ctx``+``num_thread`` reached Ollama).
    The generation pipeline (``app/generation``) uses them to give each task
    type its own decoding regime; direct callers keep the old defaults.
    """
    from llama_index.llms.ollama import Ollama

    effective_ctx = int(num_ctx) if num_ctx else NUM_CTX
    runtime_kwargs: dict[str, Any] = {"num_ctx": effective_ctx, "num_thread": NUM_THREAD}
    # Only inject sampling knobs when explicitly provided so existing call
    # sites (and Ollama's own model defaults) are untouched.
    if num_predict is not None:
        runtime_kwargs["num_predict"] = int(num_predict)
    if top_p is not None:
        runtime_kwargs["top_p"] = float(top_p)
    if top_k is not None:
        runtime_kwargs["top_k"] = int(top_k)
    if repeat_penalty is not None:
        runtime_kwargs["repeat_penalty"] = float(repeat_penalty)
    if stop:
        runtime_kwargs["stop"] = list(stop)

    use_aggressive = TRINAXAI_AGGRESSIVE_QUANT if aggressive_quant is None else aggressive_quant
    if use_aggressive:
        runtime_kwargs["num_gpu"] = 0

    return Ollama(
        model=model or LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        request_timeout=REQUEST_TIMEOUT,
        keep_alive=KEEP_ALIVE if keep_alive is None else keep_alive,
        context_window=effective_ctx,
        # Disable the model's reasoning phase: answers stream immediately instead
        # of spending latency (and tokens) on hidden <think> output. Our fleet is
        # already non-thinking, but this hard-guards any thinking model a user
        # points TrinaxAI at, so a reply is always produced without a long wait.
        thinking=False,
        additional_kwargs=runtime_kwargs,
    )


def make_embed() -> OllamaEmbedding:
    """Create the configured local Ollama embedder."""
    from llama_index.embeddings.ollama import OllamaEmbedding

    embed_kwargs = {
        "num_thread": NUM_THREAD,
        "num_ctx": 4096 if _ULTRA_PROFILE else 2048,
    }
    if TRINAXAI_AGGRESSIVE_QUANT:
        embed_kwargs["num_gpu"] = 0

    return OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
        query_instruction=(
            "Represent this query for retrieving relevant local documents:"
            if EMBED_MODEL.startswith("qwen3-embedding")
            else None
        ),
        keep_alive=EMBED_KEEP_ALIVE,
        embed_batch_size=EMBED_BATCH_SIZE,
        num_workers=EMBED_WORKERS,  # concurrent requests to Ollama
        # Ultra uses larger chunks; the rest keep context bounded for RAM.
        ollama_additional_kwargs=embed_kwargs,
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
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".dart",
    ".lua",
    ".pl",
    ".pm",
    ".erl",
    ".ex",
    ".exs",
    ".clj",
    ".fs",
    ".fsx",
    ".vb",
    ".asm",
    ".s",
    ".r",
    ".jl",
    ".m",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".dockerfile",
    ".sql",
    ".graphql",
    ".gql",
    ".cjs",
    ".mjs",
    # config / data
    ".json",
    ".jsonl",
    ".ndjson",
    ".geojson",
    ".ipynb",
    ".yml",
    ".yaml",
    ".toml",
    ".xml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".env",
    ".csv",
    ".tsv",
    ".ics",
    ".vcf",
    # prose / documents
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".tex",
    ".bib",
    ".log",
    ".html",
    ".htm",
    ".xhtml",
    ".epub",
    ".eml",
    ".srt",
    ".vtt",
    ".org",
    ".adoc",
    ".asciidoc",
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".rtf",
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
MAX_FILE_BYTES = _env_int("TRINAXAI_MAX_FILE_BYTES", 3 * 1024 * 1024, minimum=1024)
DOCUMENT_MAX_FILE_BYTES = _env_int("TRINAXAI_DOCUMENT_MAX_FILE_BYTES", 512 * 1024 * 1024, minimum=1024)
LARGE_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".rtf",
    ".epub",
}


def max_file_bytes(path: str) -> int:
    """Use a higher limit for document containers with embedded media."""
    return DOCUMENT_MAX_FILE_BYTES if os.path.splitext(path.lower())[1] in LARGE_DOCUMENT_EXTENSIONS else MAX_FILE_BYTES


UPLOAD_MAX_FILES = _env_int("TRINAXAI_UPLOAD_MAX_FILES", 2500, minimum=1)
UPLOAD_MAX_BYTES = _env_int("TRINAXAI_UPLOAD_MAX_BYTES", 2 * 1024 * 1024 * 1024, minimum=1024)
INDEX_JOBS_PATH = os.path.join(PERSIST_DIR, "index_jobs.json")
INDEX_STAGE_TIMEOUT = _env_int("TRINAXAI_INDEX_STAGE_TIMEOUT", 900, minimum=10, maximum=86400)
INDEX_TOTAL_TIMEOUT = _env_int("TRINAXAI_INDEX_TIMEOUT", 3600, minimum=30, maximum=172800)

# Persistent memory limits. These keep a single UI/API request from producing
# an unbounded JSON store or an oversized summarization prompt.
MEMORY_MAX_ENTRIES = _env_int("TRINAXAI_MEMORY_MAX_ENTRIES", 1000, minimum=1)
MEMORY_MAX_FILE_BYTES = _env_int("TRINAXAI_MEMORY_MAX_FILE_BYTES", 4 * 1024 * 1024, minimum=1024)
MEMORY_TEXT_MAX_CHARS = _env_int("TRINAXAI_MEMORY_TEXT_MAX_CHARS", 20_000, minimum=100)
MEMORY_MAX_TAGS = _env_int("TRINAXAI_MEMORY_MAX_TAGS", 50, minimum=1)
MEMORY_TAG_MAX_CHARS = _env_int("TRINAXAI_MEMORY_TAG_MAX_CHARS", 100, minimum=1)
MEMORY_SUMMARY_MAX_CHARS = _env_int("TRINAXAI_MEMORY_SUMMARY_MAX_CHARS", 50_000, minimum=1000)


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

_GENERAL_TOPIC_HINTS = (
    "clima",
    "weather",
    "receta",
    "cocina",
    "comida",
    "viaje",
    "vacaciones",
    "película",
    "pelicula",
    "música",
    "musica",
    "deporte",
    "salud",
    "ejercicio",
    "historia",
    "geografía",
    "geografia",
    "capital de",
    "quién es",
    "quien es",
    "quién te creó",
    "quien te creo",
    "qué eres",
    "que eres",
    "qué es",
    "que es",
    "cuéntame",
    "cuentame",
    "consejo",
    "traduce",
    "traducción",
    "translation",
    "recipe",
    "travel",
    "movie",
    "music",
    "who is",
    "what is",
)
_TOPIC_SHIFT_HINTS = (
    "cambiando de tema",
    "cambio de tema",
    "otra cosa",
    "ahora hablemos",
    "dejando el código",
    "dejando el codigo",
    "new topic",
    "change of topic",
    "switching topics",
    "let's talk about",
)


def route_model(text: str, previous_model: str | None = None) -> str:
    """Pick a model instantly, with affinity for the already-warm model.

    Technical intent switches immediately to the coder. Ambiguous follow-ups keep
    the previous model to avoid expensive Ollama model churn.
    """
    if not AUTO_ROUTE or not text:
        return LLM_MODEL
    t = text.lower()
    is_code = ("`" in text) or any(h in t for h in _CODE_HINTS)
    deep_signals = sum(h in t for h in _DEEP_HINTS)
    is_deep_code = is_code and (len(text) > 1_200 or deep_signals >= 2)
    if is_deep_code:
        candidate = MODEL_DEEP
    elif is_code:
        candidate = MODEL_CODE
    elif any(h in t for h in _GENERAL_TOPIC_HINTS):
        candidate = MODEL_GENERAL
    elif len(text.strip()) < 25:
        candidate = MODEL_FAST
    else:
        candidate = MODEL_GENERAL

    text_models = {MODEL_CODE, MODEL_DEEP, MODEL_GENERAL, MODEL_FAST}
    if not previous_model or previous_model not in text_models or previous_model == candidate:
        return candidate
    if is_code:
        return candidate
    explicit_general = any(h in t for h in _TOPIC_SHIFT_HINTS) or any(h in t for h in _GENERAL_TOPIC_HINTS)
    return candidate if explicit_general else previous_model


def route_model_for_messages(messages: list[dict]) -> str:
    """Route a conversation using its last real model or inferred prior intent."""
    chat = [m for m in messages if m.get("role") in {"user", "assistant"}]
    user_turns = [m for m in chat if m.get("role") == "user"]
    if not user_turns:
        return LLM_MODEL
    current = str(user_turns[-1].get("content", ""))
    previous_model = next(
        (
            str(m.get("model", "")).strip()
            for m in reversed(chat[:-1])
            if m.get("role") == "assistant" and str(m.get("model", "")).strip()
        ),
        None,
    )
    if previous_model is None and len(user_turns) >= 2:
        previous_model = route_model(str(user_turns[-2].get("content", "")))
    return route_model(current, previous_model=previous_model)


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
        LOG.warning("Reranker disabled: %s", str(e)[:80])
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


# ==================== VOICE (STT / TTS) ====================
# Local-first voice backend. Used only as a fallback when the browser does not
# support Web Speech API (e.g. Firefox) or when local TTS voices are missing.
# Motor local de voz. Solo se usa como fallback cuando el navegador no soporta
# Web Speech API (p. ej. Firefox) o cuando no hay voces locales de TTS.
VOICE_STT_MODEL = os.getenv("TRINAXAI_VOICE_STT_MODEL", "base").strip()
VOICE_TTS_ENGINE = os.getenv("TRINAXAI_VOICE_TTS_ENGINE", "").strip().lower()
VOICE_MAX_AUDIO_BYTES = _env_int("TRINAXAI_VOICE_MAX_AUDIO_BYTES", 30 * 1024 * 1024, minimum=1024)
VOICE_TTS_MAX_CHARS = _env_int("TRINAXAI_VOICE_TTS_MAX_CHARS", 1200, minimum=1, maximum=100000)
VOICE_RATE_LIMIT_PER_MINUTE = _env_int("TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE", 30, minimum=1, maximum=100000)
