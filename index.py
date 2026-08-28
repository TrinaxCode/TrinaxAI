"""
TrinaxAI — Indexador de documentos.

Características:
  • Chunking consciente del lenguaje: CodeSplitter (AST) para código,
    SentenceSplitter para prosa. No parte funciones por la mitad.
  • Qwen3 Embedding (multilingüe, 1024 dims).
  • Metadata de proyecto en cada chunk (para citas y filtro por proyecto).
  • INCREMENTAL: solo re-indexa archivos nuevos o modificados (fingerprint
    de contenido + versión de pipeline). Actualizar = segundos, no horas.
  • Publicación recuperable: índice y manifiesto cambian como una generación,
    con rollback automático si el proceso se interrumpe.
  • Múltiples raíces por colección sin colisiones ni borrados cruzados.
  • Sin LLM cargado al indexar (solo hace falta el embedder).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil as _shutil
import subprocess as _subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import Document

# On Windows, stdout defaults to cp1252 which can't encode emoji/Unicode.
# Wrap it so the indexer doesn't crash mid-job on a harmless print.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")  # type: ignore[assignment]

import config
from trinaxai_core import (
    exclusive_process_lock,
)
from trinaxai_index_documents import (
    COLLECTION_ID,
    EXTRACTOR_EXTS,
    SourceContext,
    emit_progress,
)
from trinaxai_index_documents import (
    COLLECTION_NAME as _documents_collection_name,
)
from trinaxai_index_documents import (
    _html_to_text as _documents_html_to_text,
)
from trinaxai_index_documents import (
    _load_converted_office_document as _documents_load_converted_office_document,
)
from trinaxai_index_documents import (
    _load_email_document as _documents_load_email_document,
)
from trinaxai_index_documents import (
    _load_epub_document as _documents_load_epub_document,
)
from trinaxai_index_documents import (
    _load_extracted_documents as _documents_load_extracted_documents,
)
from trinaxai_index_documents import (
    _load_html_document as _documents_load_html_document,
)
from trinaxai_index_documents import (
    _load_notebook_document as _documents_load_notebook_document,
)
from trinaxai_index_documents import (
    _load_odf_document as _documents_load_odf_document,
)
from trinaxai_index_documents import (
    _load_pdf_documents as _documents_load_pdf_documents,
)
from trinaxai_index_documents import (
    _load_pptx_document as _documents_load_pptx_document,
)
from trinaxai_index_documents import (
    _load_rtf_document as _documents_load_rtf_document,
)
from trinaxai_index_documents import (
    _load_text_document as _documents_load_text_document,
)
from trinaxai_index_documents import (
    _load_xlsx_document as _documents_load_xlsx_document,
)
from trinaxai_index_documents import (
    collect_files as _documents_collect_files,
)
from trinaxai_index_documents import (
    decode_text_bytes as _documents_decode_text_bytes,
)
from trinaxai_index_documents import (
    default_source_context as _default_source_context,
)
from trinaxai_index_documents import (
    document as _documents_document,
)
from trinaxai_index_documents import (
    is_probably_text_file as _documents_is_probably_text_file,
)
from trinaxai_index_documents import (
    relative_path as _documents_relative_path,
)
from trinaxai_index_documents import (
    source_key as _documents_source_key,
)
from trinaxai_index_storage import (
    new_storage_context,
    publish_index_generation,
    recover_interrupted_transaction,
    storage_context_for_persist_dir,
)

MANIFEST_SCHEMA_VERSION = 2
FINGERPRINT_ALGORITHM = "blake2b-256"
_HASH_BLOCK_BYTES = 1024 * 1024

INDEX_BATCH_SIZE = config._env_int("TRINAXAI_INDEX_BATCH_SIZE", 100, minimum=1, maximum=1000)
INDEX_NODE_BATCH_SIZE = config._env_int("TRINAXAI_INDEX_NODE_BATCH_SIZE", 32, minimum=1, maximum=256)
INDEX_LOAD_WORKERS = config._env_int(
    "TRINAXAI_INDEX_LOAD_WORKERS",
    min(4, os.cpu_count() or 4),
    minimum=1,
    maximum=32,
)
APPEND_ONLY = os.getenv("TRINAXAI_INDEX_APPEND", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Keep the historical ``index`` facade patchable for CLI callers and tests.
COLLECTION_NAME = _documents_collection_name
shutil = _shutil
subprocess = _subprocess
collect_files = _documents_collect_files
_html_to_text = _documents_html_to_text
_decode_text_bytes = _documents_decode_text_bytes
_document = _documents_document
_is_probably_text_file = _documents_is_probably_text_file
_rel = _documents_relative_path
_source_key = _documents_source_key
_load_text_document = _documents_load_text_document
_load_html_document = _documents_load_html_document
_load_notebook_document = _documents_load_notebook_document
_load_email_document = _documents_load_email_document
_load_epub_document = _documents_load_epub_document
_load_extracted_documents = _documents_load_extracted_documents
_load_pdf_documents = _documents_load_pdf_documents
_load_pptx_document = _documents_load_pptx_document
_load_xlsx_document = _documents_load_xlsx_document
_load_rtf_document = _documents_load_rtf_document
_load_odf_document = _documents_load_odf_document


def _load_file_documents(path: str) -> list[Document]:
    extension = os.path.splitext(path)[1].lower()
    if extension == ".pdf":
        return _load_pdf_documents(path)
    if extension in {".html", ".htm", ".xhtml"}:
        return [_load_html_document(path)]
    if extension == ".ipynb":
        return [_load_notebook_document(path)]
    if extension == ".eml":
        return [_load_email_document(path)]
    if extension == ".epub":
        return [_load_epub_document(path)]
    if extension == ".pptx":
        return [_load_pptx_document(path)]
    if extension == ".xlsx":
        return [_load_xlsx_document(path)]
    if extension == ".rtf":
        return [_load_rtf_document(path)]
    if extension in {".odt", ".ods", ".odp"}:
        return [_load_odf_document(path)]
    if extension == ".doc":
        return _load_converted_office_document(path, ".docx")
    if extension == ".ppt":
        return _load_converted_office_document(path, ".pptx")
    if extension == ".xls":
        return _load_converted_office_document(path, ".xlsx")
    if extension in EXTRACTOR_EXTS:
        return _load_extracted_documents(path)
    return [_load_text_document(path)]


def _load_converted_office_document(path: str, target_ext: str) -> list[Document]:
    return _documents_load_converted_office_document(path, target_ext, loader=_load_file_documents)


def _load_file_documents_result(path: str) -> tuple[str, list[Document], Exception | None]:
    try:
        return path, _load_file_documents(path), None
    except Exception as exc:
        return path, [], exc


def _pipeline_version() -> str:
    """Stable version of every setting that changes generated chunks/vectors."""
    inputs = {
        "schema": MANIFEST_SCHEMA_VERSION,
        "embed_model": config.EMBED_MODEL,
        "embed_dims": config.EMBED_DIMS,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "code_chunk_lines": config.CODE_CHUNK_LINES,
        "code_chunk_overlap": config.CODE_CHUNK_LINES_OVERLAP,
        "code_max_chars": config.CODE_MAX_CHARS,
        "extractor_version": 2,
    }
    payload = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


# Cache de CodeSplitters por lenguaje (crearlos es caro).
_code_splitters: dict[str, object] = {}
_prose_splitter = None
_embed_configured = False


def ensure_embed_settings() -> None:
    """Initialize Ollama embeddings only when an actual index run starts."""
    global _embed_configured
    if not _embed_configured:
        from llama_index.core import Settings

        Settings.embed_model = config.make_embed()
        _embed_configured = True


def _code_splitter(language: str):
    if language not in _code_splitters:
        from llama_index.core.node_parser import CodeSplitter

        _code_splitters[language] = CodeSplitter(
            language=language,
            chunk_lines=config.CODE_CHUNK_LINES,
            chunk_lines_overlap=config.CODE_CHUNK_LINES_OVERLAP,
            max_chars=config.CODE_MAX_CHARS,
        )
    return _code_splitters[language]


def _sentence_splitter():
    global _prose_splitter
    if _prose_splitter is None:
        from llama_index.core.node_parser import SentenceSplitter

        _prose_splitter = SentenceSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
    return _prose_splitter


def iter_batches(items: list[str], batch_size: int = INDEX_BATCH_SIZE):
    """Yield stable batches without copying the full indexing workload again."""
    for batch_start in range(0, len(items), batch_size):
        yield items[batch_start : batch_start + batch_size]


def total_batches(items: list[str], batch_size: int = INDEX_BATCH_SIZE) -> int:
    """Number of batches :func:`iter_batches` will yield for ``items``."""
    return (len(items) + batch_size - 1) // batch_size if items else 0


def _emit_embed_progress(done: int, total: int) -> None:
    """Emit a machine-parseable, newline-terminated embedding-progress line.

    tqdm's ``show_progress`` bar uses carriage returns, so the supervising
    ``system_service`` process never sees a new stdout line and the UI bar stalls
    at the first "embedding" hit. Printing one real line per batch (with an
    explicit ``N/M``) lets the supervisor map progress proportionally.
    """
    if total <= 0:
        return
    print(f"🔨 Embeddings lote {done}/{total}...", flush=True)
    emit_progress("embedding", batches_processed=done, batches_total=total, determinate=True)


def insert_node_batches(index, nodes: list, *, initialize: bool = False, storage_context=None):
    """Insert bounded batches; progress advances only after a completed batch."""
    from llama_index.core import VectorStoreIndex

    batches_total = total_batches(nodes, INDEX_NODE_BATCH_SIZE)
    current = index
    for batch_number, batch in enumerate(iter_batches(nodes, INDEX_NODE_BATCH_SIZE), start=1):
        if current is None and initialize:
            current = VectorStoreIndex(batch, storage_context=storage_context, show_progress=False)
        else:
            current.insert_nodes(batch, show_progress=False)
        _emit_embed_progress(batch_number, batches_total)
    return current


@dataclass
class LoadResult:
    documents: list[Document] = field(default_factory=list)
    loaded_paths: set[str] = field(default_factory=set)
    failures: dict[str, str] = field(default_factory=dict)


@dataclass
class PreparedBatch:
    nodes: list = field(default_factory=list)
    indexed_paths: set[str] = field(default_factory=set)
    failures: dict[str, str] = field(default_factory=dict)


def load_docs_with_status(paths: list[str], context: SourceContext | None = None) -> LoadResult:
    """Carga documentos y les pone metadata limpia (proyecto, ruta, archivo).

    - doc.id_ = ruta relativa (ID estable → permite borrado/reinserción
      incremental por archivo).
    - Procesa en batches de 100 para no saturar la memoria con directorios
      muy grandes.
    """
    result = LoadResult()
    source_context = context or _default_source_context()
    if not paths:
        return result
    executor = ThreadPoolExecutor(max_workers=INDEX_LOAD_WORKERS) if INDEX_LOAD_WORKERS > 1 else None
    try:
        for batch in iter_batches(paths):
            loaded_results = (
                list(executor.map(_load_file_documents_result, batch))
                if executor is not None and len(batch) > 1
                else [_load_file_documents_result(path) for path in batch]
            )
            for fp, group, error in loaded_results:
                if error is not None:
                    result.failures[fp] = str(error)[:300]
                    print(f"   ⚠️  Error leyendo {os.path.basename(fp)}, se reintentará: {error}")
                    continue
                group = [document for document in group if str(document.text or "").strip()]
                if not group:
                    result.failures[fp] = "no extractable text"
                    print(f"   ⚠️  {os.path.basename(fp)} no contiene texto extraíble; se reintentará")
                    continue
                rel = source_context.relative_path(fp)
                document_id = source_context.source_key_for_relative(rel)
                for i, d in enumerate(group):
                    d.id_ = document_id if len(group) == 1 else f"{document_id}#{i}"
                    metadata = dict(d.metadata or {})
                    metadata.update(
                        {
                            "project": source_context.project_name,
                            "rel_path": rel,
                            "file_name": os.path.basename(fp),
                            "source_key": source_context.source_key_for_relative(rel),
                            "source_id": source_context.source_id,
                            "source_root": source_context.root,
                            "collection_id": source_context.collection_id,
                            "collection_name": source_context.collection_name,
                            "pipeline_version": _pipeline_version(),
                        }
                    )
                    d.metadata = metadata
                    d.excluded_embed_metadata_keys = []
                    d.excluded_llm_metadata_keys = []
                    result.documents.append(d)
                result.loaded_paths.add(fp)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    return result


def load_docs(paths: list[str], context: SourceContext | None = None) -> list[Document]:
    """Compatibility wrapper returning only successfully loaded documents."""
    return load_docs_with_status(paths, context).documents


def build_nodes(documents: list[Document]) -> list:
    """Trocea por extensión: código → AST, prosa → texto. La metadata del
    documento (proyecto, ruta) se hereda automáticamente en cada chunk."""
    from llama_index.core.schema import TextNode

    nodes = []
    code_count = prose_count = fallback = 0
    for doc in documents:
        file_path = doc.metadata.get("rel_path", "")
        ext = os.path.splitext(file_path)[1].lower()
        language = config.CODE_LANG_BY_EXT.get(ext)
        doc_nodes = []

        if language:
            try:
                doc_nodes = _code_splitter(language).get_nodes_from_documents([doc]) or []
                code_count += 1
            except Exception as e:
                print(
                    f"   ⚠️  AST falló en {os.path.basename(file_path)} ({language}): {str(e)[:50]} — troceo por texto"
                )
                fallback += 1
        if not doc_nodes:
            doc_nodes = _sentence_splitter().get_nodes_from_documents([doc]) or []
            prose_count += 1
        if not doc_nodes and str(doc.text or "").strip():
            doc_nodes = [TextNode(text=str(doc.text).strip(), metadata=dict(doc.metadata or {}))]
            fallback += 1
        nodes.extend(doc_nodes)

    print(f"   └─ {code_count} por AST, {prose_count} por texto ({fallback} con fallback) → {len(nodes)} chunks")
    return nodes


def prepare_batch(
    paths: list[str],
    *,
    batch_number: int = 1,
    context: SourceContext | None = None,
) -> PreparedBatch:
    source_context = context or _default_source_context()
    loaded = load_docs_with_status(paths, source_context)
    prepared = PreparedBatch(failures=dict(loaded.failures))
    if not loaded.documents:
        return prepared
    print(f"   📦 Lote {batch_number}: {len(loaded.documents)} documentos, {len(paths)} archivos")
    documents_by_path: dict[str, list[Document]] = {}
    for document in loaded.documents:
        documents_by_path.setdefault(str(document.metadata.get("source_key") or ""), []).append(document)
    path_by_key = {source_context.source_key(path): path for path in loaded.loaded_paths}
    for source_key, documents in documents_by_path.items():
        path = path_by_key.get(source_key)
        if not path:
            continue
        try:
            nodes = build_nodes(documents)
        except Exception as exc:
            prepared.failures[path] = str(exc)[:300]
            print(f"   ⚠️  Error troceando {os.path.basename(path)}, se reintentará: {exc}")
            continue
        if not nodes:
            prepared.failures[path] = "chunking produced no nodes"
            continue
        prepared.nodes.extend(nodes)
        prepared.indexed_paths.add(path)
    return prepared


from trinaxai_index_state import (
    IndexUpdateResult as _state_index_update_result,
)
from trinaxai_index_state import (
    _content_hash as _state_content_hash,
)
from trinaxai_index_state import (
    _entry_belongs_to_source as _state_entry_belongs_to_source,
)
from trinaxai_index_state import (
    _expand_stored_manifest as _state_expand_stored_manifest,
)
from trinaxai_index_state import (
    _manifest_entry as _state_manifest_entry,
)
from trinaxai_index_state import (
    _manifest_for_storage as _state_manifest_for_storage,
)
from trinaxai_index_state import (
    _migrate_manifest_for_context as _state_migrate_manifest_for_context,
)
from trinaxai_index_state import (
    _relative_from_source_key as _state_relative_from_source_key,
)
from trinaxai_index_state import (
    apply_file_updates as _state_apply_file_updates,
)
from trinaxai_index_state import (
    current_state as _state_current_state,
)
from trinaxai_index_state import (
    diff_manifest as _state_diff_manifest,
)
from trinaxai_index_state import (
    insert_files as _state_insert_files,
)
from trinaxai_index_state import (
    merge_final_state as _state_merge_final_state,
)
from trinaxai_index_state import (
    read_manifest as _state_read_manifest,
)
from trinaxai_index_state import (
    remove_obsolete_nodes as _state_remove_obsolete_nodes,
)
from trinaxai_index_state import (
    state_after_failures as _state_after_failures_impl,
)
from trinaxai_index_state import (
    write_manifest as _state_write_manifest,
)

_manifest_entry = _state_manifest_entry
_migrate_manifest_for_context = _state_migrate_manifest_for_context
_expand_stored_manifest = _state_expand_stored_manifest
_manifest_for_storage = _state_manifest_for_storage
read_manifest = _state_read_manifest
write_manifest = _state_write_manifest
_content_hash = _state_content_hash
current_state = _state_current_state
_entry_belongs_to_source = _state_entry_belongs_to_source
diff_manifest = _state_diff_manifest
_relative_from_source_key = _state_relative_from_source_key
remove_obsolete_nodes = _state_remove_obsolete_nodes
IndexUpdateResult = _state_index_update_result
apply_file_updates = _state_apply_file_updates
insert_files = _state_insert_files
_state_after_failures = _state_after_failures_impl
_merge_final_state = _state_merge_final_state


def run_incremental(
    old_state: dict,
    new_state: dict,
    rel_to_path: dict[str, str],
    context: SourceContext | None = None,
) -> int:
    from llama_index.core import load_index_from_storage

    source_context = context or _default_source_context()
    new_files, changed, deleted = diff_manifest(old_state, new_state, rel_to_path, source_context)
    if not (new_files or changed or deleted):
        print("\n✅ Todo al día — no hay cambios que indexar.")
        return 0

    print(f"\n🔄 Incremental: {len(new_files)} nuevos, {len(changed)} modificados, {len(deleted)} eliminados")
    print("📥 Cargando índice existente...")
    sc = storage_context_for_persist_dir(config.PERSIST_DIR)
    index = load_index_from_storage(sc)

    update = apply_file_updates(
        index,
        new_files + changed,
        changed=set(changed),
        deleted=deleted,
        context=source_context,
    )
    if update.removed_nodes:
        print(f"   🗑️  {update.removed_nodes} chunks obsoletos eliminados")
    if update.failures:
        print(f"   ⚠️  {len(update.failures)} archivos conservaron su estado anterior y se reintentarán")
    effective_state = _state_after_failures(old_state, new_state, set(update.failures), source_context)
    merged_state = _merge_final_state(
        old_state,
        effective_state,
        incremental=True,
        context=source_context,
    )
    print("💾 Publicando generación atómica del índice...")
    publish_index_generation(
        index,
        _manifest_for_storage(merged_state),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    final_count = len(merged_state)
    print_summary(final_count, source_context)
    return 0


def _node_source_key(node, context: SourceContext | None = None) -> str | None:
    metadata = node.metadata or {}
    source_key = str(metadata.get("source_key") or "").strip()
    source_id = str(metadata.get("source_id") or "").strip()
    rel_path = str(metadata.get("rel_path") or "").strip()
    collection_id = str(metadata.get("collection_id") or config.DEFAULT_COLLECTION_ID)
    if context is not None and collection_id == context.collection_id and rel_path and not source_id:
        # Adopt nodes created before source roots had identities.
        return context.source_key_for_relative(rel_path)
    if source_key:
        return source_key
    if not rel_path:
        return None
    if source_id:
        return f"{collection_id}:{source_id}:{rel_path}"
    return f"{collection_id}:{rel_path}"


def run_manifest_recovery(
    new_state: dict,
    rel_to_path: dict[str, str],
    context: SourceContext | None = None,
) -> int:
    """Recover a missing/corrupt manifest without replacing other collections."""
    from llama_index.core import load_index_from_storage

    print("\n🛟 Índice existente sin manifiesto válido — recuperación segura")
    storage_context = storage_context_for_persist_dir(config.PERSIST_DIR)
    existing = load_index_from_storage(storage_context)
    source_context = context or _default_source_context()
    node_context = context
    existing_keys = {
        key for node in existing.docstore.docs.values() if (key := _node_source_key(node, node_context)) is not None
    }
    active_prefix = (
        f"{source_context.collection_id}:{source_context.source_id}:" if context is not None else f"{COLLECTION_ID}:"
    )
    deleted = sorted(key for key in existing_keys if key.startswith(active_prefix) and key not in new_state)
    paths = list(rel_to_path.values())
    update = apply_file_updates(
        existing,
        paths,
        changed=set(paths),
        deleted=deleted,
        context=source_context,
    )

    recovered: dict[str, dict] = {}
    successful_keys = {key for key, path in rel_to_path.items() if path in update.indexed_paths}
    for node in existing.docstore.docs.values():
        key = _node_source_key(node, node_context)
        if not key:
            continue
        if key in successful_keys and key in new_state:
            recovered[key] = new_state[key]
        else:
            # A deliberately non-matching fingerprint forces verification when
            # that collection is indexed next, while preserving its nodes now.
            metadata = node.metadata or {}
            recovered_entry = {"unverified": True}
            if metadata.get("source_id"):
                recovered_entry.update(
                    {
                        "schema_version": MANIFEST_SCHEMA_VERSION,
                        "pipeline_version": _pipeline_version(),
                        "source_id": metadata.get("source_id"),
                        "source_root": metadata.get("source_root"),
                        "rel_path": metadata.get("rel_path"),
                    }
                )
            recovered[key] = recovered_entry
    print("💾 Publicando generación recuperada del índice...")
    publish_index_generation(
        existing,
        _manifest_for_storage(recovered),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    if update.failures:
        print(f"   ⚠️  {len(update.failures)} archivos se conservaron y se reintentarán")
    print_summary(len(recovered), source_context)
    return 0


def run_full_index(
    paths: list[str],
    new_state: dict,
    context: SourceContext | None = None,
) -> int:
    source_context = context or _default_source_context()
    print("\n🆕 Indexado completo (primera vez)")
    if not paths:
        print("❌ No se encontraron documentos para indexar.")
        return 1
    print("✂️  Troceando (chunking consciente del lenguaje)...")
    index = None
    storage_context = new_storage_context(config.PERSIST_DIR)
    total_nodes = 0
    indexed_paths: set[str] = set()
    failures: dict[str, str] = {}
    files_total = len(paths)
    files_processed = 0
    for batch_number, batch in enumerate(iter_batches(paths), start=1):
        prepared = prepare_batch(batch, batch_number=batch_number, context=source_context)
        failures.update(prepared.failures)
        files_processed += len(batch)
        nodes = prepared.nodes
        if not nodes:
            emit_progress(
                "chunking",
                files_total=files_total,
                files_processed=files_processed,
                chunks_generated=total_nodes,
                determinate=True,
            )
            continue
        indexed_paths.update(prepared.indexed_paths)
        total_nodes += len(nodes)
        emit_progress(
            "chunking",
            files_total=files_total,
            files_processed=files_processed,
            chunks_generated=total_nodes,
            determinate=True,
        )
        index = insert_node_batches(
            index,
            nodes,
            initialize=index is None,
            storage_context=storage_context,
        )
    if index is None:
        print("❌ No se pudieron generar chunks para indexar.")
        return 1
    successful_state = {
        source_context.source_key(path): new_state[source_context.source_key(path)]
        for path in indexed_paths
        if source_context.source_key(path) in new_state
    }
    print("💾 Publicando primera generación atómica del índice...")
    publish_index_generation(
        index,
        _manifest_for_storage(successful_state),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    final_count = len(successful_state)
    if failures:
        print(f"   ⚠️  {len(failures)} archivos no se marcaron y se reintentarán")
    print_summary(final_count, source_context)
    return 0


def print_summary(final_count: int, context: SourceContext | None = None) -> None:
    source_context = context or _default_source_context()
    print("\n✅ Indexado completado")
    print(f"📚 Colección: {source_context.collection_name} ({source_context.collection_id})")
    print(f"🗂️  Fuente: {source_context.project_name} ({source_context.source_id})")
    print(f"📦 {config.PERSIST_DIR}  ·  {final_count} archivos en el índice")
    print("═" * 45)


def run_index(root: str | None = None) -> int:
    root = root or config.PROJECTS_DIRS[0]
    source_context = SourceContext.create(root)
    print("\n🧠 TrinaxAI — Indexador de Documentos")
    print("═" * 45)
    if not os.path.isdir(root):
        print(f"❌ Directorio no encontrado: {root}")
        return 1
    lock_timeout = config._env_int("TRINAXAI_INDEX_LOCK_TIMEOUT", 3600, minimum=1, maximum=86400)
    lock_path = os.path.join(config.PERSIST_DIR, ".indexing.lock")
    print("🔒 Esperando turno exclusivo del índice...", flush=True)
    try:
        with exclusive_process_lock(lock_path, timeout=lock_timeout):
            recovery = recover_interrupted_transaction(config.PERSIST_DIR, config.MANIFEST_PATH)
            if recovery == "rolled_back":
                print("🛟 Se restauró la generación anterior tras una indexación interrumpida.")
            elif recovery == "committed":
                print("🧹 Se confirmó una generación ya publicada y se limpió su transacción.")
            ensure_embed_settings()
            print(f"📂 Recorriendo: {source_context.root}")
            paths = collect_files(source_context.root)
            rel_to_path = {source_context.source_key(p): p for p in paths}
            old_state = read_manifest(source_context)
            new_state = current_state(paths, source_context)
            print(f"   └─ {len(paths)} archivos candidatos")

            index_exists = os.path.exists(os.path.join(config.PERSIST_DIR, "docstore.json"))
            if index_exists and old_state:
                return run_incremental(old_state, new_state, rel_to_path, source_context)
            if index_exists:
                return run_manifest_recovery(new_state, rel_to_path, source_context)
            return run_full_index(paths, new_state, source_context)
    except TimeoutError as exc:
        print(f"❌ {exc}")
        return 2
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"❌ No se pudo publicar/recuperar el índice: {exc}")
        return 3


# ==================== MAIN ====================
if __name__ == "__main__":
    sys.exit(run_index())
