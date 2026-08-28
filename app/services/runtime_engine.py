"""Index lifecycle, collection scoping and model concurrency."""

from __future__ import annotations


def _runtime():
    """Resolve the compatibility facade after module initialization."""
    from . import shared_runtime

    return shared_runtime


def _index_process_lock():
    runtime = _runtime()
    return runtime.exclusive_process_lock(
        runtime.os.path.join(runtime.config.PERSIST_DIR, ".indexing.lock"),
        timeout=runtime.config._env_float("TRINAXAI_INDEX_LOCK_TIMEOUT", 60.0, minimum=1.0, maximum=86400.0),
    )


def _inference_process_lock():
    """Coordinate Ollama-heavy work across FastAPI and the PWA gateway."""
    runtime = _runtime()
    return runtime.exclusive_process_lock(
        runtime.os.path.join(runtime.config.PERSIST_DIR, ".inference.lock"),
        timeout=runtime.config._env_float(
            "TRINAXAI_INFERENCE_QUEUE_TIMEOUT",
            600.0,
            minimum=1.0,
            maximum=86400.0,
        ),
        poll_interval=0.1,
    )


def _collection_slug(name: str) -> str:
    return _runtime().sanitize_collection_id(name)


def _public_rel_path(metadata: dict) -> str:
    """Return a source label without exposing legacy absolute paths."""
    runtime = _runtime()
    rel_path = str(metadata.get("rel_path") or "").strip().replace("\\", "/")
    if rel_path and not (
        runtime.os.path.isabs(rel_path)
        or rel_path.startswith("//")
        or (len(rel_path) >= 3 and rel_path[1] == ":" and rel_path[2] == "/")
    ):
        return rel_path
    file_path = str(metadata.get("file_path") or rel_path).strip().replace("\\", "/")
    return file_path.rsplit("/", 1)[-1] or "(unknown)"


def _collection_public(item: dict) -> dict:
    runtime = _runtime()
    now = runtime.time.time()
    collection_id = runtime.sanitize_collection_id(
        str(item.get("id") or runtime.config.DEFAULT_COLLECTION_ID),
        fallback=runtime.config.DEFAULT_COLLECTION_ID,
    )
    return {
        "id": collection_id,
        "name": str(item.get("name") or runtime.config.DEFAULT_COLLECTION_NAME),
        "created_at": float(item.get("created_at") or now),
        "updated_at": float(item.get("updated_at") or item.get("created_at") or now),
    }


def _default_collection() -> dict:
    runtime = _runtime()
    now = runtime.time.time()
    return {
        "id": runtime.config.DEFAULT_COLLECTION_ID,
        "name": runtime.config.DEFAULT_COLLECTION_NAME,
        "created_at": now,
        "updated_at": now,
    }


def _read_collections_unlocked() -> list[dict]:
    runtime = _runtime()
    try:
        with open(runtime.config.COLLECTIONS_PATH, encoding="utf-8") as stream:
            raw = runtime.json.load(stream)
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
    if runtime.config.DEFAULT_COLLECTION_ID not in seen:
        collections.insert(0, _default_collection())
    return collections


def _write_collections_unlocked(collections: list[dict]) -> None:
    runtime = _runtime()
    runtime.atomic_write_json(runtime.config.COLLECTIONS_PATH, {"collections": collections})


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
    thinking: bool = True,
):
    """Cache LLM instances by model and decoding configuration."""
    runtime = _runtime()
    cache_key = (
        model,
        str(runtime.config.KEEP_ALIVE if keep_alive is None else keep_alive),
        bool(runtime.config.TRINAXAI_AGGRESSIVE_QUANT if aggressive_quant is None else aggressive_quant),
        round(float(temperature), 3),
        num_ctx,
        num_predict,
        top_p,
        top_k,
        repeat_penalty,
        tuple(stop) if stop else None,
        thinking,
    )
    with runtime.state.llm_cache_lock:
        if cache_key not in runtime.state.llm_cache:
            runtime.state.llm_cache[cache_key] = runtime.config.make_llm(
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
                thinking=thinking,
            )
        return runtime.state.llm_cache[cache_key]


def _reconcile_index_collections(docstore) -> None:
    """Register collections present in indexed node metadata."""
    runtime = _runtime()
    discovered: dict[str, str] = {}
    for node in getattr(docstore, "docs", {}).values():
        metadata = getattr(node, "metadata", {}) or {}
        raw_collection_id = str(metadata.get("collection_id") or "").strip()
        if not raw_collection_id:
            continue
        collection_id = runtime.sanitize_collection_id(
            raw_collection_id,
            fallback=runtime.config.DEFAULT_COLLECTION_ID,
        )
        discovered.setdefault(
            collection_id,
            str(metadata.get("collection_name") or collection_id).strip() or collection_id,
        )
    if not discovered:
        return
    with runtime.state.collections_lock:
        collections = runtime._read_collections_unlocked()
        existing = {item["id"] for item in collections}
        now = runtime.time.time()
        for collection_id, name in discovered.items():
            if collection_id not in existing:
                collections.append({"id": collection_id, "name": name[:80], "created_at": now, "updated_at": now})
        if len(collections) != len(existing):
            runtime._write_collections_unlocked(collections)


def _build_engine_from_disk() -> bool:
    """Load a complete on-disk generation. Caller owns the process lock."""
    runtime = _runtime()
    with runtime.state.engine_lock:
        try:
            recovery = runtime.recover_interrupted_transaction(
                runtime.config.PERSIST_DIR,
                runtime.config.MANIFEST_PATH,
            )
            if recovery:
                runtime.LOG.info("Index transaction recovery before reload: %s", recovery)
            storage_context = runtime.storage_context_for_persist_dir(runtime.config.PERSIST_DIR)
            index = runtime.load_index_from_storage(storage_context)
            runtime.state.vector_index = index
            vector_retriever = index.as_retriever(similarity_top_k=runtime.config.FUSION_CANDIDATES)
            bm25_retriever = runtime.BM25Retriever.from_defaults(
                docstore=index.docstore,
                similarity_top_k=runtime.config.FUSION_CANDIDATES,
            )
            runtime.state.fusion_retriever = runtime.QueryFusionRetriever(
                [vector_retriever, bm25_retriever],
                similarity_top_k=runtime.config.FUSION_CANDIDATES,
                num_queries=1,
                mode="reciprocal_rerank",
                # ``retrieve()`` is invoked from worker threads by both the API
                # and CLI paths. Keep fusion synchronous to avoid closed-loop
                # failures in nested asyncio runners.
                use_async=False,
                llm=runtime.get_llm(runtime.config.LLM_MODEL),
            )
            runtime.state.index_docstore = index.docstore
            runtime._reconcile_index_collections(runtime.state.index_docstore)
            runtime.state.known_projects = sorted(
                {
                    node.metadata.get("project", "")
                    for node in index.docstore.docs.values()
                    if node.metadata.get("project")
                }
            )
            runtime._clear_index_runtime_caches()
            runtime.LOG.info(
                "Index loaded: %d chunks, %d projects",
                len(index.docstore.docs),
                len(runtime.state.known_projects),
            )
            return True
        except Exception as exc:
            runtime.state.fusion_retriever = None
            runtime.state.index_docstore = None
            runtime.state.vector_index = None
            runtime.state.known_projects = []
            runtime._clear_index_runtime_caches()
            runtime.LOG.warning("No index available; run python index.py: %s", exc)
            return False


def build_engine(*, acquire_process_lock: bool = True) -> bool:
    """Load the hybrid retriever without observing an index mid-publication."""
    runtime = _runtime()
    if not acquire_process_lock:
        return runtime._build_engine_from_disk()
    try:
        with runtime._index_process_lock():
            return runtime._build_engine_from_disk()
    except TimeoutError as exc:
        runtime.LOG.warning("Index reload skipped because the process lock timed out: %s", exc)
        return False


def initialize_runtime() -> None:
    """Initialize heavyweight model/index resources during application startup."""
    runtime = _runtime()
    runtime.state.lifecycle_stopping.clear()
    try:
        runtime.Settings.embed_model = runtime.config.make_embed()
    except Exception:
        runtime.LOG.exception("Embedding model initialization failed; API will start in degraded mode")
    try:
        runtime.state.reranker = runtime.config.make_reranker()
    except Exception:
        runtime.state.reranker = None
        runtime.LOG.exception("Reranker initialization failed; continuing without reranking")
    if runtime.state.reranker is not None:
        runtime.LOG.info("Reranker enabled: %s", runtime.config.RERANK_MODEL)
    try:
        runtime.build_engine()
    except Exception:
        runtime.LOG.exception("Index initialization failed; continuing without document retrieval")


def _collection_scope(collections: list[str] | tuple[str, ...] | None) -> tuple[tuple[str, ...], str | None]:
    """Normalize and validate an optional collection scope against indexed nodes."""
    runtime = _runtime()
    requested = tuple(
        dict.fromkeys(
            runtime.sanitize_collection_id(value, fallback=runtime.config.DEFAULT_COLLECTION_ID)
            for value in (collections or [])
            if isinstance(value, str) and value.strip()
        )
    )
    if not requested:
        return (), None
    with runtime.state.collections_lock:
        existing = {item["id"] for item in runtime._read_collections_unlocked()}
    missing = next((collection_id for collection_id in requested if collection_id not in existing), None)
    if missing:
        return requested, "collection_not_found"
    docs = getattr(runtime.state.index_docstore, "docs", {}) if runtime.state.index_docstore is not None else {}
    populated = {
        str((getattr(node, "metadata", {}) or {}).get("collection_id") or runtime.config.DEFAULT_COLLECTION_ID)
        for node in docs.values()
    }
    if not any(collection_id in populated for collection_id in requested):
        return requested, "collection_empty"
    return requested, None


def _retriever_for_collections(active_collections: tuple[str, ...]):
    """Build and cache a hybrid retriever scoped before candidate ranking."""
    runtime = _runtime()
    if not active_collections:
        return runtime.state.fusion_retriever
    with runtime.state.collection_retrievers_lock:
        cached = runtime._lru_get(runtime.state.collection_retrievers, active_collections)
        if cached is not None:
            return cached
        if runtime.state.vector_index is None or runtime.state.index_docstore is None:
            return None
        allowed = set(active_collections)
        nodes = [
            node
            for node in runtime.state.index_docstore.docs.values()
            if (getattr(node, "metadata", {}) or {}).get("collection_id", runtime.config.DEFAULT_COLLECTION_ID)
            in allowed
        ]
        if not nodes:
            return None
        filters = runtime.MetadataFilters(
            filters=[
                runtime.MetadataFilter(key="collection_id", value=collection_id) for collection_id in active_collections
            ],
            condition=runtime.FilterCondition.OR,
        )
        vector_retriever = runtime.state.vector_index.as_retriever(
            similarity_top_k=runtime.config.FUSION_CANDIDATES,
            filters=filters,
        )
        bm25_retriever = runtime.BM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=runtime.config.FUSION_CANDIDATES,
        )
        retriever = runtime.QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=runtime.config.FUSION_CANDIDATES,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
            llm=runtime.get_llm(runtime.config.LLM_MODEL),
        )
        runtime._lru_set(
            runtime.state.collection_retrievers,
            active_collections,
            retriever,
            max_entries=runtime._RETRIEVER_CACHE_MAX_COMBINATIONS,
        )
        return retriever


def _run_model_task(function, *args, **kwargs):
    runtime = _runtime()
    with runtime._model_slots:
        with runtime._inference_process_lock():
            return function(*args, **kwargs)


def _research_serialize_node(node) -> dict:
    """Build a chunk payload for the sources/chunks API."""
    meta = getattr(node, "metadata", {}) or {}
    score = getattr(node, "score", None)
    public_metadata = {
        key: meta.get(key)
        for key in (
            "rel_path",
            "project",
            "collection_id",
            "collection_name",
            "source_id",
            "page_label",
            "page",
            "page_number",
        )
        if key in meta
    }
    if "rel_path" in public_metadata:
        public_metadata["rel_path"] = _public_rel_path(meta)
    return {
        "id": getattr(node, "node_id", "") or getattr(node, "id_", ""),
        "text": (node.get_content() if hasattr(node, "get_content") else str(node)),
        "metadata": public_metadata,
        "score": round(float(score), 4) if score is not None else None,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
