"""Cross-domain engine, authorization, cache and lifecycle services."""

from __future__ import annotations

from app.errors import generic_exception_handler, http_exception_handler
from app.security.admin_auth import (
    _is_lan_client,
    _is_local_client,
)
from app.security.admin_auth import (
    authorize_system as _authorize_system,
)
from trinaxai_index_storage import (
    SQLiteVectorStore,
    atomic_write_json,
    publish_index_generation,
    recover_interrupted_transaction,
)

# The split service modules import their shared runtime dependencies explicitly.
# Keep this compatibility surface in one place while avoiding wildcard imports.
# ruff: noqa: F401
from .runtime_context import (
    _RETRIEVER_CACHE_MAX_COMBINATIONS,
    _SAFE_ATTACHMENT_TYPES,
    _SAFE_INLINE_ATTACHMENT_TYPES,
    _SAFE_SEGMENT,
    APP_STATE_MAX_BYTES,
    APP_STATE_PATH,
    CHAT_ATTACHMENT_MAX_BYTES,
    CHAT_ATTACHMENTS_DIR,
    CHAT_ATTACHMENTS_MAX_BYTES,
    CHAT_ATTACHMENTS_MAX_FILES,
    DOC_EXTRACT_MAX_BYTES,
    DOC_EXTRACT_MAX_CHARS,
    LOG,
    NO_INDEX_MSG,
    USAGE_PATH,
    USAGE_SUMMARY_PATH,
    USER_MEMORY_PATH,
    AgentApprovalRequest,
    AgentCancelRequest,
    AgentRequest,
    Any,
    AppStateRequest,
    BM25Retriever,
    BytesIO,
    ChatRequest,
    CollectionCreateRequest,
    CollectionUpdateRequest,
    File,
    FileResponse,
    FilterCondition,
    Form,
    HTTPException,
    IndexImportDeleteRequest,
    JSONResponse,
    MemoryContextRequest,
    MemoryCreateRequest,
    MemoryRefreshRequest,
    MemoryUpdateRequest,
    MetadataFilter,
    MetadataFilters,
    QueryBundle,
    QueryFusionRetriever,
    Regime,
    Request,
    ResearchRequest,
    Response,
    ResponseMode,
    Settings,
    StorageContext,
    StreamingResponse,
    UploadFile,
    UsageRecordRequest,
    WatchStartRequest,
    _cache_get,
    _cache_set,
    _clear_index_runtime_caches,
    _client_host,
    _document_slots,
    _lru_get,
    _lru_set,
    _model_slots,
    _WDFileSystemEventHandler,
    build_generation_prompt,
    build_task_spec,
    config,
    enforce_rate_limit,
    exclusive_process_lock,
    get_response_synthesizer,
    grounded_template,
    json,
    load_index_from_storage,
    os,
    re,
    run_in_threadpool,
    sanitize_collection_id,
    shutil,
    source_id_for_root,
    state,
    subprocess,
    sys,
    tempfile,
    threading,
    time,
    uuid,
    validate_output,
    wants_creator_bio,
)
from .runtime_engine import (
    _build_engine_from_disk,
    _collection_public,
    _collection_scope,
    _collection_slug,
    _default_collection,
    _index_process_lock,
    _inference_process_lock,
    _public_rel_path,
    _read_collections_unlocked,
    _reconcile_index_collections,
    _research_serialize_node,
    _retriever_for_collections,
    _run_model_task,
    _write_collections_unlocked,
    build_engine,
    get_llm,
    initialize_runtime,
)
from .runtime_index import (
    _delete_indexed_collection,
    _delete_indexed_collection_unlocked,
    _delete_indexed_rel_paths,
    _delete_indexed_rel_paths_unlocked,
    _manifest_without_keys,
    _manifest_without_prefix,
    _read_manifest_unlocked,
    _trim_manifest_keys,
)
from .runtime_usage import (
    _apply_usage_record,
    _empty_usage_summary,
    _read_usage_summary_unlocked,
    _record_usage,
    _write_usage_summary_unlocked,
)


def storage_context_for_persist_dir(persist_dir: str):
    """Load the active index with the embedded vector store.

    Keep the factory here so existing tests and integrations can continue to
    patch ``shared_runtime.StorageContext`` at the compatibility boundary.
    """
    return StorageContext.from_defaults(
        persist_dir=persist_dir,
        vector_store=SQLiteVectorStore.for_persist_dir(persist_dir),
    )


async def _trinaxai_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Compatibility alias for the centralized HTTP error handler."""
    return await http_exception_handler(request, exc)


async def _trinaxai_generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Compatibility alias for the centralized generic exception handler."""
    return await generic_exception_handler(request, exc)


__all__ = [name for name in globals() if not name.startswith("__")]
