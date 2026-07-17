"""Cross-domain engine, authorization, cache and lifecycle services."""

from __future__ import annotations

from app.security.admin_auth import (
    _is_lan_client,
    _is_local_client,
)
from app.security.admin_auth import (
    authorize_system as _authorize_system,
)
from trinaxai_index_storage import recover_interrupted_transaction

# ruff: noqa: F401,F405
from .runtime_context import *  # noqa: F403


def _index_process_lock():
    return exclusive_process_lock(
        os.path.join(config.PERSIST_DIR, ".indexing.lock"),
        timeout=config._env_float("TRINAXAI_INDEX_LOCK_TIMEOUT", 3600.0, minimum=1.0, maximum=86400.0),
    )


def _inference_process_lock():
    """Coordinate Ollama-heavy work across FastAPI and the PWA gateway."""
    return exclusive_process_lock(
        os.path.join(config.PERSIST_DIR, ".inference.lock"),
        timeout=config._env_float(
            "TRINAXAI_INFERENCE_QUEUE_TIMEOUT",
            600.0,
            minimum=1.0,
            maximum=86400.0,
        ),
        poll_interval=0.1,
    )


def _collection_slug(name: str) -> str:
    return sanitize_collection_id(name)


def _collection_public(item: dict) -> dict:
    now = time.time()
    collection_id = sanitize_collection_id(
        str(item.get("id") or config.DEFAULT_COLLECTION_ID),
        fallback=config.DEFAULT_COLLECTION_ID,
    )
    return {
        "id": collection_id,
        "name": str(item.get("name") or config.DEFAULT_COLLECTION_NAME),
        "created_at": float(item.get("created_at") or now),
        "updated_at": float(item.get("updated_at") or item.get("created_at") or now),
    }


def _default_collection() -> dict:
    now = time.time()
    return {
        "id": config.DEFAULT_COLLECTION_ID,
        "name": config.DEFAULT_COLLECTION_NAME,
        "created_at": now,
        "updated_at": now,
    }


def _read_collections_unlocked() -> list[dict]:
    try:
        with open(config.COLLECTIONS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    items = raw.get("collections") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        items = []
    collections = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        public = _collection_public(item)
        if public["id"] in seen:
            continue
        seen.add(public["id"])
        collections.append(public)
    if config.DEFAULT_COLLECTION_ID not in seen:
        collections.insert(0, _default_collection())
    return collections


def _write_collections_unlocked(collections: list[dict]) -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    tmp = f"{config.COLLECTIONS_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"collections": collections}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config.COLLECTIONS_PATH)


def _get_collection_unlocked(collection_id: str) -> dict | None:
    for item in _read_collections_unlocked():
        if item["id"] == collection_id:
            return item
    return None


def get_llm(
    model: str,
    *,
    keep_alive: str | int | None = None,
    aggressive_quant: bool | None = None,
    temperature: float = 0.0,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    repeat_penalty: float | None = None,
    stop: tuple[str, ...] | None = None,
):
    """Cachea los LLM por nombre (crear el objeto es barato; reusar evita ruido).

    La clave de caché incluye los knobs de muestreo, así que cada régimen de
    generación (código, creativo, RAG) reutiliza su propia instancia sin
    pisar a las demás. Llamado sin knobs extra ⇒ comportamiento histórico.
    """
    cache_key = (
        model,
        str(config.KEEP_ALIVE if keep_alive is None else keep_alive),
        bool(config.TRINAXAI_AGGRESSIVE_QUANT if aggressive_quant is None else aggressive_quant),
        round(float(temperature), 3),
        num_ctx,
        num_predict,
        top_p,
        top_k,
        repeat_penalty,
        tuple(stop) if stop else None,
    )
    with state.llm_cache_lock:
        if cache_key not in state.llm_cache:
            state.llm_cache[cache_key] = config.make_llm(
                temperature=temperature,
                model=model,
                keep_alive=keep_alive,
                aggressive_quant=aggressive_quant,
                num_ctx=num_ctx,
                num_predict=num_predict,
                top_p=top_p,
                top_k=top_k,
                repeat_penalty=repeat_penalty,
                stop=stop,
            )
        return state.llm_cache[cache_key]


def _build_engine_from_disk() -> bool:
    """Load a complete on-disk generation. Caller owns the process lock."""
    with state.engine_lock:
        try:
            recovery = recover_interrupted_transaction(config.PERSIST_DIR, config.MANIFEST_PATH)
            if recovery:
                LOG.info("Index transaction recovery before reload: %s", recovery)
            storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
            index = load_index_from_storage(storage_context)
            state.vector_index = index
            vector_retriever = index.as_retriever(similarity_top_k=config.FUSION_CANDIDATES)
            bm25_retriever = BM25Retriever.from_defaults(
                docstore=index.docstore,
                similarity_top_k=config.FUSION_CANDIDATES,
            )
            state.fusion_retriever = QueryFusionRetriever(
                [vector_retriever, bm25_retriever],
                similarity_top_k=config.FUSION_CANDIDATES,
                num_queries=1,
                mode="reciprocal_rerank",
                # ``retrieve()`` is invoked from worker threads by both the API
                # and CLI paths. QueryFusionRetriever's nested asyncio runner
                # reuses a closed loop in that setup, so keep fusion synchronous.
                # The two local retrievers are cheap compared with embedding and
                # generation, and correctness here is more important than the
                # negligible parallelism win.
                use_async=False,
                llm=get_llm(config.LLM_MODEL),
            )
            state.index_docstore = index.docstore
            state.known_projects = sorted(
                {n.metadata.get("project", "") for n in index.docstore.docs.values() if n.metadata.get("project")}
            )
            _clear_index_runtime_caches()
            LOG.info(
                "Index loaded: %d chunks, %d projects",
                len(index.docstore.docs),
                len(state.known_projects),
            )
            return True
        except Exception as e:
            state.fusion_retriever = None
            state.index_docstore = None
            state.vector_index = None
            state.known_projects = []
            _clear_index_runtime_caches()
            LOG.warning("No index available; run python index.py: %s", e)
            return False


def build_engine(*, acquire_process_lock: bool = True) -> bool:
    """Load the hybrid retriever without observing an index mid-publication.

    The default acquires the same cross-process lock used by ``index.py`` and
    destructive source operations.  A caller that already owns that lock must
    pass ``acquire_process_lock=False`` to avoid attempting a non-reentrant
    process-lock acquisition.
    """
    if not acquire_process_lock:
        return _build_engine_from_disk()
    try:
        with _index_process_lock():
            return _build_engine_from_disk()
    except TimeoutError as exc:
        LOG.warning("Index reload skipped because the process lock timed out: %s", exc)
        return False


def initialize_runtime() -> None:
    """Initialize heavyweight model/index resources during application startup."""
    Settings.embed_model = config.make_embed()
    state.reranker = config.make_reranker()
    if state.reranker is not None:
        LOG.info("Reranker enabled: %s", config.RERANK_MODEL)
    build_engine()


def _retriever_for_collections(active_collections: tuple[str, ...]):
    """Build and cache a hybrid retriever scoped before candidate ranking."""
    if not active_collections:
        return state.fusion_retriever
    with state.collection_retrievers_lock:
        cached = _lru_get(state.collection_retrievers, active_collections)
        if cached is not None:
            return cached
        if state.vector_index is None or state.index_docstore is None:
            return None
        allowed = set(active_collections)
        nodes = [
            node
            for node in state.index_docstore.docs.values()
            if (getattr(node, "metadata", {}) or {}).get("collection_id", config.DEFAULT_COLLECTION_ID) in allowed
        ]
        if not nodes:
            return None
        filters = MetadataFilters(
            filters=[MetadataFilter(key="collection_id", value=collection_id) for collection_id in active_collections],
            condition=FilterCondition.OR,
        )
        vector_retriever = state.vector_index.as_retriever(
            similarity_top_k=config.FUSION_CANDIDATES,
            filters=filters,
        )
        bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=config.FUSION_CANDIDATES,
        )
        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=config.FUSION_CANDIDATES,
            num_queries=1,
            mode="reciprocal_rerank",
            # See the global retriever above: this object is also consumed via
            # synchronous ``retrieve()`` from a worker thread.
            use_async=False,
            llm=get_llm(config.LLM_MODEL),
        )
        _lru_set(
            state.collection_retrievers,
            active_collections,
            retriever,
            max_entries=_RETRIEVER_CACHE_MAX_COMBINATIONS,
        )
        return retriever


def _run_model_task(function, *args, **kwargs):
    with _model_slots:
        with _inference_process_lock():
            return function(*args, **kwargs)


def _research_serialize_node(node) -> dict:
    """Build a chunk payload from a docstore node (matches /v1/sources/.../chunks shape)."""
    meta = getattr(node, "metadata", {}) or {}
    score = getattr(node, "score", None)
    return {
        "id": getattr(node, "node_id", "") or getattr(node, "id_", ""),
        "text": (node.get_content() if hasattr(node, "get_content") else str(node)),
        "metadata": {
            k: meta.get(k)
            for k in (
                "rel_path",
                "project",
                "collection_id",
                "collection_name",
                "source_id",
                "page_label",
                "page",
                "page_number",
                "file_path",
            )
            if k in meta
        },
        "score": round(float(score), 4) if score is not None else None,
    }


def _trim_manifest_keys(keys: set[str], *, source_id: str | None = None) -> None:
    """Remove exact manifest keys, optionally for just one source root."""
    if not keys:
        return
    try:
        with open(config.MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
        if isinstance(manifest, dict):
            trimmed = dict(manifest)
            changed = False
            for key in keys:
                if key not in trimmed:
                    continue
                if source_id is None:
                    trimmed.pop(key, None)
                    changed = True
                    continue
                value = trimmed.get(key)
                if not isinstance(value, dict):
                    continue
                sources = value.get("sources")
                if isinstance(sources, dict) and source_id in sources:
                    updated_value = dict(value)
                    updated_sources = dict(sources)
                    updated_sources.pop(source_id, None)
                    updated_value["sources"] = updated_sources
                    if updated_sources or "legacy" in updated_value:
                        trimmed[key] = updated_value
                    else:
                        trimmed.pop(key, None)
                    changed = True
                elif str(value.get("source_id") or "") == source_id:
                    # Compatibility with a briefly used source-flat manifest.
                    trimmed.pop(key, None)
                    changed = True
            if changed:
                tmp = f"{config.MANIFEST_PATH}.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(trimmed, f)
                os.replace(tmp, config.MANIFEST_PATH)
    except (OSError, ValueError):
        pass


def _delete_indexed_rel_paths_unlocked(
    collection: str,
    rel_paths: set[str],
    *,
    source_id: str | None = None,
) -> int:
    """Delete indexed nodes for a set of relative source paths in one collection."""
    if not rel_paths:
        return 0
    deleted = 0
    source_keys = {f"{collection}:{rel}" for rel in rel_paths}
    storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
    index = load_index_from_storage(storage_context)
    node_ids: list[str] = []
    for node_id, node in index.docstore.docs.items():
        meta = getattr(node, "metadata", {}) or {}
        rid = meta.get("collection_id", config.DEFAULT_COLLECTION_ID)
        if rid != collection:
            continue
        rel = meta.get("rel_path") or meta.get("file_path") or ""
        source_key = meta.get("source_key") or f"{rid}:{rel}"
        if source_id is not None and str(meta.get("source_id") or "") != source_id:
            continue
        if rel in rel_paths or source_key in source_keys:
            node_ids.append(node_id)
    if node_ids:
        index.delete_nodes(node_ids, delete_from_docstore=True)
        index.storage_context.persist(persist_dir=config.PERSIST_DIR)
        deleted = len(node_ids)
    _trim_manifest_keys(source_keys, source_id=source_id)
    return deleted


def _delete_indexed_rel_paths(
    collection: str,
    rel_paths: set[str],
    *,
    source_id: str | None = None,
) -> int:
    with _index_process_lock():
        return _delete_indexed_rel_paths_unlocked(collection, rel_paths, source_id=source_id)


def _empty_usage_summary() -> dict:
    return {
        "messages_total": 0,
        "messages_by_engine": {},
        "tokens_estimated": 0,
        "model_counts": {},
        "collection_counts": {},
        "index_runs": 0,
        "first_seen": 0.0,
        "last_seen": 0.0,
    }


def _apply_usage_record(summary: dict, rec: dict) -> None:
    summary["messages_total"] = int(summary.get("messages_total") or 0) + 1
    summary["tokens_estimated"] = int(summary.get("tokens_estimated") or 0) + int(rec.get("est_tokens") or 0)

    by_engine = summary.setdefault("messages_by_engine", {})
    engine = str(rec.get("engine") or "unknown")
    by_engine[engine] = int(by_engine.get(engine) or 0) + 1

    by_model = summary.setdefault("model_counts", {})
    model = str(rec.get("model") or "unknown")
    by_model[model] = int(by_model.get(model) or 0) + 1

    by_col = summary.setdefault("collection_counts", {})
    for cid in rec.get("collections") or []:
        key = str(cid)
        by_col[key] = int(by_col.get(key) or 0) + 1

    ts = float(rec.get("ts") or 0.0)
    if ts:
        first_seen = float(summary.get("first_seen") or 0.0)
        summary["first_seen"] = ts if first_seen == 0.0 else min(first_seen, ts)
        summary["last_seen"] = max(float(summary.get("last_seen") or 0.0), ts)


def _read_usage_summary_unlocked() -> dict | None:
    try:
        with open(USAGE_SUMMARY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_usage_summary_unlocked(summary: dict) -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    tmp = f"{USAGE_SUMMARY_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False)
    os.replace(tmp, USAGE_SUMMARY_PATH)


def _record_usage(
    engine: str,
    model: str,
    project: str | None,
    collections: list[str] | None,
    est_tokens: int,
) -> None:
    """Append a single usage record. Fire-and-forget; never raises."""
    try:
        os.makedirs(config.PERSIST_DIR, exist_ok=True)
        rec = {
            "ts": time.time(),
            "engine": engine,
            "model": model,
            "project": project,
            "collections": list(collections or []),
            "est_tokens": int(est_tokens),
        }
        with state.usage_lock:
            with open(USAGE_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            summary = _read_usage_summary_unlocked() or _empty_usage_summary()
            _apply_usage_record(summary, rec)
            _write_usage_summary_unlocked(summary)
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)


async def _trinaxai_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Captura HTTPException 500 y devuelve mensaje multilingüe."""
    if exc.status_code == 500:
        return JSONResponse(
            status_code=500,
            content={"detail": _MULTILINGUAL_500},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


async def _trinaxai_generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura cualquier excepción no manejada y devuelve 500 multilingüe."""
    LOG.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": _MULTILINGUAL_500},
    )


__all__ = [name for name in globals() if not name.startswith("__")]
