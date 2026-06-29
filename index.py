"""
TrinaxAI — Indexador de documentos.

Características:
  • Chunking consciente del lenguaje: CodeSplitter (AST) para código,
    SentenceSplitter para prosa. No parte funciones por la mitad.
  • Embeddings bge-m3 (multilingüe, 1024 dims).
  • Metadata de proyecto en cada chunk (para citas y filtro por proyecto).
  • INCREMENTAL: solo re-indexa archivos nuevos o modificados (manifiesto
    por fecha de modificación). Actualizar = segundos, no horas.
  • Sin LLM cargado al indexar (solo hace falta el embedder).
"""

import json
import os
import sys

from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core.schema import Document

import config


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


# ==================== SETTINGS ====================
Settings.embed_model = config.make_embed()
# NO se define Settings.llm: indexar solo necesita embeddings.
COLLECTION_ID = (
    os.getenv("TRINAXAI_COLLECTION_ID", config.DEFAULT_COLLECTION_ID).strip()
    or config.DEFAULT_COLLECTION_ID
)
COLLECTION_NAME = (
    os.getenv("TRINAXAI_COLLECTION_NAME", config.DEFAULT_COLLECTION_NAME).strip()
    or config.DEFAULT_COLLECTION_NAME
)

INDEX_BATCH_SIZE = _env_int("TRINAXAI_INDEX_BATCH_SIZE", 100, minimum=1, maximum=1000)
APPEND_ONLY = os.getenv("TRINAXAI_INDEX_APPEND", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Splitter de prosa (md, txt, json, yaml, configs, etc.)
prose_splitter = SentenceSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
)

# Cache de CodeSplitters por lenguaje (crearlos es caro).
_code_splitters: dict[str, CodeSplitter] = {}


def _code_splitter(language: str) -> CodeSplitter:
    if language not in _code_splitters:
        _code_splitters[language] = CodeSplitter(
            language=language,
            chunk_lines=config.CODE_CHUNK_LINES,
            chunk_lines_overlap=config.CODE_CHUNK_LINES_OVERLAP,
            max_chars=config.CODE_MAX_CHARS,
        )
    return _code_splitters[language]


# ==================== LECTOR DE ARCHIVOS ====================
def collect_files(root: str) -> list[str]:
    """Recorre `root` PODANDO carpetas de dependencias.

    No desciende en node_modules/site-packages/venv/etc., así que es
    órdenes de magnitud más rápido que enumerar todo y filtrar después.
    """
    allowed = {e.lower() for e in config.REQUIRED_EXTS}
    allowed_names = {"dockerfile"}
    files: list[str] = []
    skipped_big = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Podar: quita in-place las carpetas excluidas y las ocultas.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in config.EXCLUDE_DIR_NAMES
            and not d.startswith(".")
            and not d.endswith((".egg-info", ".dist-info"))
        ]
        for fn in filenames:
            if fn.startswith("."):
                continue
            if (
                fn.lower() not in allowed_names
                and os.path.splitext(fn)[1].lower() not in allowed
            ):
                continue
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) > config.MAX_FILE_BYTES:
                    skipped_big += 1
                    continue
            except OSError:
                continue
            files.append(full)
            file_count += 1
            if file_count % 5000 == 0:
                print(f"   📂 {file_count} archivos encontrados...", flush=True)
    if file_count >= 5000:
        print(f"   📂 {file_count} archivos encontrados en total")
    if skipped_big:
        print(
            f"   ⏭️  {skipped_big} archivos omitidos por tamaño "
            f"(> {config.MAX_FILE_BYTES // (1024 * 1024)} MB)"
        )
    return files


def _rel(path: str) -> str:
    try:
        rel = os.path.relpath(path, config.PROJECTS_DIRS[0])
        return rel.replace("\\", "/")
    except ValueError:
        return path


def _source_key(path: str) -> str:
    return f"{COLLECTION_ID}:{_rel(path)}"


def load_docs(paths: list[str]) -> list[Document]:
    """Carga documentos y les pone metadata limpia (proyecto, ruta, archivo).

    - doc.id_ = ruta relativa (ID estable → permite borrado/reinserción
      incremental por archivo).
    - Procesa en batches de 100 para no saturar la memoria con directorios
      muy grandes.
    """
    if not paths:
        return []
    out: list[Document] = []
    for batch_start in range(0, len(paths), INDEX_BATCH_SIZE):
        batch = paths[batch_start : batch_start + INDEX_BATCH_SIZE]
        try:
            docs = SimpleDirectoryReader(
                input_files=batch,
                exclude_hidden=False,
                exclude=config.EXCLUDE_PATTERNS,
            ).load_data()
        except Exception as e:
            print(f"   ⚠️  Error reading batch, skipping: {e}")
            continue
        by_path: dict[str, list[Document]] = {}
        for d in docs:
            by_path.setdefault(d.metadata.get("file_path", ""), []).append(d)
        for fp, group in by_path.items():
            rel = _rel(fp)
            for i, d in enumerate(group):
                d.id_ = rel if len(group) == 1 else f"{rel}#{i}"
                d.metadata = {
                    "project": config.project_of(fp),
                    "rel_path": rel,
                    "file_name": os.path.basename(fp),
                    "source_key": f"{COLLECTION_ID}:{rel}",
                    "collection_id": COLLECTION_ID,
                    "collection_name": COLLECTION_NAME,
                }
                d.excluded_embed_metadata_keys = []
                d.excluded_llm_metadata_keys = []
                out.append(d)
    return out


def build_nodes(documents: list[Document]) -> list:
    """Trocea por extensión: código → AST, prosa → texto. La metadata del
    documento (proyecto, ruta) se hereda automáticamente en cada chunk."""
    nodes = []
    code_count = prose_count = fallback = 0
    for doc in documents:
        file_path = doc.metadata.get("rel_path", "")
        ext = os.path.splitext(file_path)[1].lower()
        language = config.CODE_LANG_BY_EXT.get(ext)

        doc_nodes = None
        if language:
            try:
                doc_nodes = _code_splitter(language).get_nodes_from_documents([doc])
                code_count += 1
            except Exception as e:
                print(
                    f"   ⚠️  AST falló en {os.path.basename(file_path)} "
                    f"({language}): {str(e)[:50]} — troceo por texto"
                )
                fallback += 1
        if doc_nodes is None:
            doc_nodes = prose_splitter.get_nodes_from_documents([doc])
            prose_count += 1
        nodes.extend(doc_nodes)

    print(
        f"   └─ {code_count} por AST, {prose_count} por texto "
        f"({fallback} con fallback) → {len(nodes)} chunks"
    )
    return nodes


# ==================== MANIFIESTO (incremental) ====================
def read_manifest() -> dict:
    try:
        with open(config.MANIFEST_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    canonical = {}
    for k, v in raw.items():
        if ":" not in k:
            if COLLECTION_ID == config.DEFAULT_COLLECTION_ID:
                canonical[f"{COLLECTION_ID}:{k}"] = v
            else:
                canonical[k] = v
        else:
            canonical[k] = v
    return canonical


def write_manifest(m: dict) -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    tmp = f"{config.MANIFEST_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f)
    os.replace(tmp, config.MANIFEST_PATH)


def current_state(paths: list[str]) -> dict:
    """{ruta_relativa: mtime} de los archivos actuales en disco."""
    state = {}
    for p in paths:
        try:
            state[_source_key(p)] = int(os.path.getmtime(p))
        except OSError:
            pass
    return state


def diff_manifest(old_state: dict, new_state: dict, rel_to_path: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    new_files: list[str] = []
    changed: list[str] = []
    for key, path in rel_to_path.items():
        if key in old_state:
            if old_state[key] != new_state[key]:
                changed.append(path)
        else:
            new_files.append(path)
    prefix = f"{COLLECTION_ID}:"
    deleted = [] if APPEND_ONLY else [key for key in old_state if key.startswith(prefix) and key not in new_state]
    return new_files, changed, deleted


def remove_obsolete_nodes(index: VectorStoreIndex, changed: list[str], deleted: list[str]) -> int:
    rels_to_remove = {_source_key(path) for path in changed} | set(deleted)
    node_ids = [
        nid
        for nid, node in index.docstore.docs.items()
        if node.metadata.get("source_key") in rels_to_remove
        or node.metadata.get("rel_path") in rels_to_remove
    ]
    if node_ids:
        index.delete_nodes(node_ids, delete_from_docstore=True)
    return len(node_ids)


def insert_files(index: VectorStoreIndex, paths: list[str]) -> int:
    if not paths:
        return 0
    print("✂️  Troceando cambios...")
    nodes = build_nodes(load_docs(paths))
    if nodes:
        print(f"🔨 Embeddings de {len(nodes)} chunks (bge-m3)...")
        index.insert_nodes(nodes, show_progress=True)
    return len(nodes)


def persist_final_state(old_state: dict, new_state: dict, *, incremental: bool) -> int:
    if incremental and APPEND_ONLY:
        merged_state = dict(old_state)
        merged_state.update(new_state)
        write_manifest(merged_state)
        return len(merged_state)
    write_manifest(new_state)
    return len(new_state)


def run_incremental(old_state: dict, new_state: dict, rel_to_path: dict[str, str]) -> int:
    new_files, changed, deleted = diff_manifest(old_state, new_state, rel_to_path)
    if not (new_files or changed or deleted):
        print("\n✅ Todo al día — no hay cambios que indexar.")
        return 0

    print(
        f"\n🔄 Incremental: {len(new_files)} nuevos, {len(changed)} "
        f"modificados, {len(deleted)} eliminados"
    )
    print("📥 Cargando índice existente...")
    sc = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
    index = load_index_from_storage(sc)

    removed = remove_obsolete_nodes(index, changed, deleted)
    if removed:
        print(f"   🗑️  {removed} chunks obsoletos eliminados")
    insert_files(index, new_files + changed)
    index.storage_context.persist(persist_dir=config.PERSIST_DIR)
    final_count = persist_final_state(old_state, new_state, incremental=True)
    print_summary(final_count)
    return 0


def run_full_index(paths: list[str], new_state: dict) -> int:
    print("\n🆕 Indexado completo (primera vez)")
    if not paths:
        print("❌ No se encontraron documentos para indexar.")
        return 1
    print("✂️  Troceando (chunking consciente del lenguaje)...")
    nodes = build_nodes(load_docs(paths))
    print(f"🔨 Embeddings de {len(nodes)} chunks (bge-m3)...")
    index = VectorStoreIndex(nodes, show_progress=True)
    index.storage_context.persist(persist_dir=config.PERSIST_DIR)
    final_count = persist_final_state({}, new_state, incremental=False)
    print_summary(final_count)
    return 0


def print_summary(final_count: int) -> None:
    print("\n✅ Indexado completado")
    print(f"📚 Colección: {COLLECTION_NAME} ({COLLECTION_ID})")
    print(f"📦 {config.PERSIST_DIR}  ·  {final_count} archivos en el índice")
    print("═" * 45)


def run_index(root: str | None = None) -> int:
    root = root or config.PROJECTS_DIRS[0]
    print("\n🧠 TrinaxAI — Indexador de Documentos")
    print("═" * 45)
    if not os.path.isdir(root):
        print(f"❌ Directorio no encontrado: {root}")
        return 1

    print(f"📂 Recorriendo: {root}")
    paths = collect_files(root)
    rel_to_path = {_source_key(p): p for p in paths}
    new_state = current_state(paths)
    print(f"   └─ {len(paths)} archivos candidatos")

    old_state = read_manifest()
    index_exists = os.path.exists(os.path.join(config.PERSIST_DIR, "docstore.json"))
    incremental = index_exists and bool(old_state)
    if incremental:
        return run_incremental(old_state, new_state, rel_to_path)
    return run_full_index(paths, new_state)


# ==================== MAIN ====================
if __name__ == "__main__":
    sys.exit(run_index())
