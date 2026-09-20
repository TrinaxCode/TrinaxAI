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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llama_index.core.schema import BaseNode, Document

# On Windows, stdout defaults to cp1252 which can't encode emoji/Unicode.
# Wrap it so the indexer doesn't crash mid-job on a harmless print.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")  # type: ignore[assignment]

import config
from trinaxai_cli.i18n import resolve_lang
from trinaxai_cli.i18n import text as _text
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
_FAILURE_SUMMARY_LIMIT = 20
_FAILURE_REASON_LIMIT = 180
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


def _t(key: str, **values: Any) -> str:
    """Render one indexer message in the language selected for this run."""
    return _text(key, resolve_lang(), **values)


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
_prose_splitter_class = None
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
    global _prose_splitter, _prose_splitter_class
    from llama_index.core.node_parser import SentenceSplitter

    # Keep the cache correct when integrations/tests replace the parser class
    # at runtime; otherwise a stale parser can leak into later indexing runs.
    if _prose_splitter is None or _prose_splitter_class is not SentenceSplitter:
        _prose_splitter = SentenceSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        _prose_splitter_class = SentenceSplitter
    return _prose_splitter


def iter_batches(items: list[str], batch_size: int = INDEX_BATCH_SIZE):
    """Yield stable batches without copying the full indexing workload again."""
    for batch_start in range(0, len(items), batch_size):
        yield items[batch_start : batch_start + batch_size]


def total_batches(items: list[str], batch_size: int = INDEX_BATCH_SIZE) -> int:
    """Number of batches :func:`iter_batches` will yield for ``items``."""
    return (len(items) + batch_size - 1) // batch_size if items else 0


def _emit_embed_progress(
    done: int,
    total: int,
    started: bool = False,
    files: tuple[int, int] | None = None,
) -> None:
    """Emit a machine-parseable, newline-terminated embedding-progress line.

    tqdm's ``show_progress`` bar uses carriage returns, so the supervising
    ``system_service`` process never sees a new stdout line and the UI bar stalls
    at the first "embedding" hit. Printing one real line per batch (with an
    explicit ``N/M``) lets the supervisor map progress proportionally.

    ``started`` fires before the first batch is embedded so the UI can switch its
    phase label immediately instead of waiting for a full batch, and ``files``
    carries the run-level file counters so the supervisor only maps the
    embedding span once every file has been chunked (streaming runs read, chunk
    and embed in the same pass).
    """
    if total <= 0:
        return
    if not started:
        print(_t("idx_embeddings_batch", done=done, total=total), flush=True)
    payload: dict[str, object] = {
        "batches_processed": done,
        "batches_total": total,
        "determinate": not started,
    }
    if files and files[1] > 0:
        payload["files_processed"], payload["files_total"] = files
    emit_progress("embedding", **payload)


def insert_node_batches(
    index,
    nodes: list,
    *,
    initialize: bool = False,
    storage_context=None,
    on_embed_progress=None,
):
    """Insert bounded batches; progress advances only after a completed batch."""
    from llama_index.core import VectorStoreIndex

    batches_total = total_batches(nodes, INDEX_NODE_BATCH_SIZE)
    report = on_embed_progress or _emit_embed_progress
    if batches_total:
        report(0, batches_total, True)
    current = index
    for batch_number, batch in enumerate(iter_batches(nodes, INDEX_NODE_BATCH_SIZE), start=1):
        if current is None and initialize:
            current = VectorStoreIndex(batch, storage_context=storage_context, show_progress=False)
        else:
            current.insert_nodes(batch, show_progress=False)
        report(batch_number, batches_total, False)
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


def _safe_failure_path(path: str, context: SourceContext) -> str:
    try:
        safe_path = context.relative_path(path)
    except ValueError:
        safe_path = os.path.basename(os.path.normpath(path)).replace("\\", "/")
    return "".join(char if char.isprintable() else "_" for char in safe_path)[:240] or "unknown"


def _safe_failure_reason(reason: str) -> str:
    normalized = " ".join(str(reason).split())[:_FAILURE_REASON_LIMIT]
    if "no extractable text" in normalized:
        return "no extractable text"
    if "OCR may be required" in normalized:
        return "OCR may be required"
    if "chunking produced no nodes" in normalized:
        return "chunking produced no nodes"
    if "LibreOffice" in normalized:
        return "LibreOffice conversion is required"
    return "document processing failed"


def emit_failure_summary(failures: dict[str, str], context: SourceContext) -> None:
    """Publish one bounded, machine-readable retry warning for partial runs."""
    if not failures:
        return
    details = [
        {
            "path": _safe_failure_path(path, context),
            "reason": _safe_failure_reason(reason),
        }
        for path, reason in sorted(failures.items())[:_FAILURE_SUMMARY_LIMIT]
    ]
    emit_progress(
        "warning",
        skipped=len(failures),
        failures=details,
        failures_truncated=len(failures) > len(details),
        retry_recommended=True,
        determinate=True,
    )


def load_docs_with_status(
    paths: list[str],
    context: SourceContext | None = None,
    *,
    files_offset: int = 0,
    on_file_read=None,
) -> LoadResult:
    """Carga documentos y les pone metadata limpia (proyecto, ruta, archivo).

    - doc.id_ = ruta relativa (ID estable → permite borrado/reinserción
      incremental por archivo).
    - Procesa en batches de 100 para no saturar la memoria con directorios
      muy grandes.
    - ``on_file_read(files_done)`` reporta cada archivo en cuanto se lee (éxito o
      fallo) para que la barra avance archivo a archivo en lugar de quedarse
      quieta hasta terminar el lote completo.
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
            for position, (fp, group, error) in enumerate(loaded_results, start=1):
                if on_file_read is not None:
                    on_file_read(files_offset + position)
                if error is not None:
                    result.failures[fp] = str(error)[:300]
                    print(_t("idx_read_error", name=os.path.basename(fp), error=error))
                    continue
                group = [document for document in group if str(document.text or "").strip()]
                if not group:
                    result.failures[fp] = "no extractable text"
                    print(_t("idx_no_text", name=os.path.basename(fp)))
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


def build_nodes(documents: list[Document]) -> list[BaseNode]:
    """Trocea por extensión: código → AST, prosa → texto. La metadata del
    documento (proyecto, ruta) se hereda automáticamente en cada chunk."""
    from llama_index.core.schema import TextNode

    nodes: list[BaseNode] = []
    code_count = prose_count = fallback = 0
    for doc in documents:
        file_path = doc.metadata.get("rel_path", "")
        ext = os.path.splitext(file_path)[1].lower()
        language = config.CODE_LANG_BY_EXT.get(ext)
        doc_nodes: list[BaseNode] = []

        if language:
            try:
                doc_nodes = _code_splitter(language).get_nodes_from_documents([doc]) or []
                code_count += 1
            except Exception as e:
                print(
                    _t(
                        "idx_ast_failed",
                        name=os.path.basename(file_path),
                        language=language,
                        error=str(e)[:50],
                    )
                )
                fallback += 1
        if not doc_nodes:
            doc_nodes = _sentence_splitter().get_nodes_from_documents([doc]) or []
            prose_count += 1
        if not doc_nodes and str(doc.text or "").strip():
            doc_nodes = [TextNode(text=str(doc.text).strip(), metadata=dict(doc.metadata or {}))]
            fallback += 1
        nodes.extend(doc_nodes)

    print(
        _t(
            "idx_split_summary",
            code=code_count,
            prose=prose_count,
            fallback=fallback,
            chunks=len(nodes),
        )
    )
    return nodes


def prepare_batch(
    paths: list[str],
    *,
    batch_number: int = 1,
    context: SourceContext | None = None,
    files_offset: int = 0,
    on_file_read=None,
    on_file_chunked=None,
) -> PreparedBatch:
    source_context = context or _default_source_context()
    loaded = load_docs_with_status(
        paths,
        source_context,
        files_offset=files_offset,
        on_file_read=on_file_read,
    )
    prepared = PreparedBatch(failures=dict(loaded.failures))
    if not loaded.documents:
        return prepared
    print(
        _t(
            "idx_batch_loaded",
            batch=batch_number,
            documents=len(loaded.documents),
            files=len(paths),
        )
    )
    documents_by_path: dict[str, list[Document]] = {}
    for document in loaded.documents:
        documents_by_path.setdefault(str(document.metadata.get("source_key") or ""), []).append(document)
    path_by_key = {source_context.source_key(path): path for path in loaded.loaded_paths}
    position_by_path = {path: position for position, path in enumerate(paths, start=1)}
    for source_key, documents in documents_by_path.items():
        path = path_by_key.get(source_key)
        if not path:
            continue
        try:
            nodes = build_nodes(documents)
        except Exception as exc:
            prepared.failures[path] = str(exc)[:300]
            print(_t("idx_split_error", name=os.path.basename(path), error=exc))
            continue
        if not nodes:
            prepared.failures[path] = "chunking produced no nodes"
            continue
        prepared.nodes.extend(nodes)
        prepared.indexed_paths.add(path)
        if on_file_chunked is not None:
            on_file_chunked(files_offset + position_by_path.get(path, 1), len(nodes))
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
        print(_t("idx_up_to_date"))
        return 0

    print(_t("idx_incremental", new=len(new_files), changed=len(changed), deleted=len(deleted)))
    print(_t("idx_loading_existing"))
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
        print(_t("idx_stale_removed", count=update.removed_nodes))
    if update.failures:
        print(_t("idx_kept_state", count=len(update.failures)))
    effective_state = _state_after_failures(old_state, new_state, set(update.failures), source_context)
    merged_state = _merge_final_state(
        old_state,
        effective_state,
        incremental=True,
        context=source_context,
    )
    print(_t("idx_publishing"))
    publish_index_generation(
        index,
        _manifest_for_storage(merged_state),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    final_count = len(merged_state)
    emit_failure_summary(update.failures, source_context)
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

    print(_t("idx_manifest_recovery"))
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
            recovered_entry: dict[str, Any] = {"unverified": True}
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
    print(_t("idx_publishing_recovered"))
    publish_index_generation(
        existing,
        _manifest_for_storage(recovered),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    if update.failures:
        print(_t("idx_retry_count", count=len(update.failures)))
    emit_failure_summary(update.failures, source_context)
    print_summary(len(recovered), source_context)
    return 0


def run_full_index(
    paths: list[str],
    new_state: dict,
    context: SourceContext | None = None,
) -> int:
    source_context = context or _default_source_context()
    print(_t("idx_first_run"))
    if not paths:
        print(_t("idx_no_documents"))
        return 1
    print(_t("idx_chunking"))
    index = None
    storage_context = new_storage_context(config.PERSIST_DIR)
    total_nodes = 0
    indexed_paths: set[str] = set()
    failures: dict[str, str] = {}
    files_total = len(paths)
    files_processed = 0
    chunks_in_batch = 0

    def report_read(files_done: int) -> None:
        emit_progress(
            "extracting",
            files_total=files_total,
            files_processed=files_done,
            determinate=True,
        )

    def report_chunked(files_done: int, chunks_in_file: int) -> None:
        # Running count for the batch in progress; ``total_nodes`` is the
        # authoritative total once the batch closes.
        nonlocal chunks_in_batch
        chunks_in_batch += chunks_in_file
        emit_progress(
            "chunking",
            files_total=files_total,
            files_processed=files_done,
            chunks_generated=total_nodes + chunks_in_batch,
            determinate=True,
        )

    def report_embed(done: int, total: int, started: bool) -> None:
        _emit_embed_progress(done, total, started, files=(files_processed, files_total))

    for batch_number, batch in enumerate(iter_batches(paths), start=1):
        prepared = prepare_batch(
            batch,
            batch_number=batch_number,
            context=source_context,
            files_offset=files_processed,
            on_file_read=report_read,
            on_file_chunked=report_chunked,
        )
        failures.update(prepared.failures)
        files_processed += len(batch)
        nodes = prepared.nodes
        total_nodes += len(nodes)
        chunks_in_batch = 0
        emit_progress(
            "chunking",
            files_total=files_total,
            files_processed=files_processed,
            chunks_generated=total_nodes,
            determinate=True,
        )
        if not nodes:
            continue
        indexed_paths.update(prepared.indexed_paths)
        index = insert_node_batches(
            index,
            nodes,
            initialize=index is None,
            storage_context=storage_context,
            on_embed_progress=report_embed,
        )
    if index is None:
        emit_failure_summary(failures, source_context)
        print(_t("idx_no_chunks"))
        return 1
    successful_state = {
        source_context.source_key(path): new_state[source_context.source_key(path)]
        for path in indexed_paths
        if source_context.source_key(path) in new_state
    }
    print(_t("idx_publishing_first"))
    publish_index_generation(
        index,
        _manifest_for_storage(successful_state),
        persist_dir=config.PERSIST_DIR,
        manifest_path=config.MANIFEST_PATH,
    )
    final_count = len(successful_state)
    if failures:
        print(_t("idx_not_marked", count=len(failures)))
    emit_failure_summary(failures, source_context)
    print_summary(final_count, source_context)
    return 0


def print_summary(final_count: int, context: SourceContext | None = None) -> None:
    source_context = context or _default_source_context()
    print(_t("idx_completed"))
    print(_t("idx_collection_line", name=source_context.collection_name, id=source_context.collection_id))
    print(_t("idx_source_line", project=source_context.project_name, id=source_context.source_id))
    print(_t("idx_files_in_index", path=config.PERSIST_DIR, count=final_count))
    print("═" * 45)


def run_index(root: str | None = None) -> int:
    root = root or config.PROJECTS_DIRS[0]
    source_context = SourceContext.create(root)
    print(_t("idx_banner"))
    print("═" * 45)
    if not os.path.isdir(root):
        print(_t("idx_dir_not_found", path=root))
        return 1
    lock_timeout = config._env_int("TRINAXAI_INDEX_LOCK_TIMEOUT", 3600, minimum=1, maximum=86400)
    lock_path = os.path.join(config.PERSIST_DIR, ".indexing.lock")
    print(_t("idx_lock_wait"), flush=True)
    try:
        with exclusive_process_lock(lock_path, timeout=lock_timeout):
            recovery = recover_interrupted_transaction(config.PERSIST_DIR, config.MANIFEST_PATH)
            if recovery == "rolled_back":
                print(_t("idx_restored_generation"))
            elif recovery == "committed":
                print(_t("idx_confirmed_generation"))
            ensure_embed_settings()
            print(_t("idx_scanning", path=source_context.root))
            paths = collect_files(source_context.root)
            rel_to_path = {source_context.source_key(p): p for p in paths}
            old_state = read_manifest(source_context)
            new_state = current_state(paths, source_context)
            print(_t("idx_candidates", count=len(paths)))

            index_exists = os.path.exists(os.path.join(config.PERSIST_DIR, "docstore.json"))
            if index_exists and old_state:
                return run_incremental(old_state, new_state, rel_to_path, source_context)
            if index_exists:
                return run_manifest_recovery(new_state, rel_to_path, source_context)
            return run_full_index(paths, new_state, source_context)
    except TimeoutError as exc:
        print(_t("idx_error", error=exc))
        return 2
    except (OSError, RuntimeError, ValueError) as exc:
        print(_t("idx_publish_failed", error=exc))
        return 3


# ==================== MAIN ====================
if __name__ == "__main__":
    sys.exit(run_index())
