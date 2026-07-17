"""Agentic assistant service — file/shell tool-use over a workspace via SSE.

Wraps :class:`trinaxai_cli.agent.AgentEngine` behind an HTTP/SSE API so the PWA
can drive the same agent the CLI uses. Two endpoints cooperate:

* ``POST /v1/agent`` opens an ``text/event-stream``. The engine runs on a worker
  thread and pushes events (``tool_start``, ``tool_result``, ``token``,
  ``approval_request``, ``done``, ``error``) onto a queue that the SSE generator
  drains to the browser.
* ``POST /v1/agent/approve`` resolves a pending dangerous action. When the engine
  hits a dangerous tool it emits ``approval_request`` and blocks on a
  ``threading.Event``; this endpoint sets the decision and unblocks it.

Sessions live in an in-memory registry keyed by a per-stream id. They are
short-lived (one turn) and cleaned up when the stream ends. Requested workspace
paths must be inside an operator-registered root. File tools enforce that root;
terminal commands run in the OS sandbox from ``agent.tools`` and fail closed
when the platform cannot provide it. Dangerous tools still require interactive
approval over HTTP unless the separately gated localhost-only yolo policy is on.
"""

from __future__ import annotations

# ruff: noqa: F405
import queue
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.security.admin_auth import authorize_scope
from trinaxai_cli.agent import DEFAULT_TOOLS, AgentEngine, Tool  # noqa: E402
from trinaxai_cli.agent.engine import AgentCancelled  # noqa: E402

from .shared_runtime import *  # noqa: F403

# Pending agent streams. Each entry owns a queue (engine → SSE) and a dict of
# in-flight approval events (approval_id → {"event", "approved"}).
_SESSIONS: dict[str, dict] = {}
_SESSIONS_LOCK = threading.Lock()

# How long the engine waits for a browser approval before auto-denying, so a
# closed tab never wedges a worker thread forever.
_APPROVAL_TIMEOUT_SECONDS = 300
_AGENT_MAX_SECONDS = config._env_float("TRINAXAI_AGENT_TIMEOUT", 600.0, minimum=30.0, maximum=3600.0)
_AGENT_STALL_SECONDS = config._env_float("TRINAXAI_AGENT_STALL_TIMEOUT", 120.0, minimum=15.0, maximum=600.0)
_AGENT_WORKSPACE_KEY = "tc-agent-workspace"


@contextmanager
def _agent_inference_slot():
    """Reserve inference only around each Ollama call, not tool approval waits."""
    with _model_slots:
        with _inference_process_lock():
            yield


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _configured_workspace_roots() -> tuple[Path, ...]:
    """Return canonical roots the HTTP agent is allowed to enter.

    ``TRINAXAI_AGENT_WORKSPACE_ROOTS`` is a platform-path-separator-delimited
    allowlist.  When omitted, the configured indexing roots are used, with the
    repository itself as a safe fallback.  Filesystem roots are never accepted
    as agent roots.
    """
    configured = os.getenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", "").strip()
    if configured:
        candidates = [item.strip() for item in configured.split(os.pathsep) if item.strip()]
    else:
        candidates = [str(item) for item in getattr(config, "PROJECTS_DIRS", ())]
        candidates.append(str(config.BASE_DIR))

    roots: list[Path] = []
    for candidate in candidates:
        try:
            root = Path(candidate).expanduser().resolve()
        except OSError:
            continue
        if not root.is_dir() or root == Path(root.anchor):
            continue
        if root not in roots:
            roots.append(root)
    if not roots:
        fallback = Path(config.BASE_DIR).resolve()
        if fallback.is_dir() and fallback != Path(fallback.anchor):
            roots.append(fallback)
    return tuple(roots)


def _workspace_is_allowed(path: Path, roots: tuple[Path, ...] | None = None) -> bool:
    allowed_roots = roots or _configured_workspace_roots()
    return any(path == root or root in path.parents for root in allowed_roots)


def _resolve_workspace(requested: str | None) -> Path:
    """Resolve a requested workspace inside an operator-registered root."""
    roots = _configured_workspace_roots()
    if not roots:
        raise HTTPException(status_code=503, detail="No agent workspace root is configured.")
    candidate = (requested or "").strip()
    if not candidate:
        try:
            with state.app_state_lock:
                candidate = _read_app_state().get(_AGENT_WORKSPACE_KEY, "").strip()
        except Exception:
            candidate = ""
    if not candidate:
        return roots[0]
    path = Path(candidate).expanduser()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace is not a directory: {path}")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid workspace: {path}") from exc
    if not _workspace_is_allowed(resolved, roots):
        raise HTTPException(
            status_code=403,
            detail="Workspace is outside TRINAXAI_AGENT_WORKSPACE_ROOTS.",
        )
    return resolved


def _http_yolo_enabled() -> bool:
    return os.getenv("TRINAXAI_AGENT_HTTP_YOLO", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _authorize_http_yolo(req: AgentRequest, request: Request) -> None:
    if not req.yolo:
        return
    authorize_scope(request, "agent_yolo")
    if not _http_yolo_enabled():
        raise HTTPException(
            status_code=403,
            detail="HTTP yolo mode is disabled. Dangerous tools require explicit approval.",
        )
    if not _is_local_client(_client_host(request)):
        raise HTTPException(
            status_code=403,
            detail="HTTP yolo mode is restricted to the real localhost transport.",
        )


def _resolve_model(requested: str | None, messages: list[dict] | None = None) -> str:
    """Resolve an explicit model or use TrinaxAI's shared multimodel router."""
    selected = (requested or "").strip()
    if selected and selected.lower() != "auto":
        return selected
    if messages:
        try:
            return config.route_model_for_messages(messages)
        except Exception:  # noqa: BLE001 - preserve the safe configured fallback
            LOG.debug("Agent model auto-routing failed; using the general model", exc_info=True)
    return getattr(config, "MODEL_GENERAL", None) or getattr(config, "LLM_MODEL", "qwen3.5:4b")


def _agent_num_ctx() -> int:
    """Context window for the agent.

    Tool use accumulates file reads and command output, so the agent needs a
    roomier window than plain chat or it silently overflows and small models
    degrade into one-word junk. We take the larger of the configured RAG window
    and a sane floor, capped so CPU-only boxes stay responsive.
    """
    configured = int(getattr(config, "NUM_CTX", 8192) or 8192)
    # Env override wins for power users who know their RAM budget.
    try:
        override = int(os.getenv("TRINAXAI_AGENT_NUM_CTX", "0") or "0")
    except ValueError:
        override = 0
    if override > 0:
        return max(2048, min(override, 131072))
    # The default system prompt plus tool schemas fit in 4K. Starting every
    # small-model turn at 8K roughly doubles prompt evaluation cost on CPU;
    # history trimming already protects longer sessions from overflow.
    return max(4096, min(configured, 16384))


def _identity_key(request: Request) -> tuple[str, str]:
    identity = getattr(request.state, "trinaxai_identity", {}) or {}
    kind = str(identity.get("kind") or "unknown")
    identifier = str(identity.get("id") or kind)
    return kind, identifier


def _register_session(identity_key: tuple[str, str] = ("local", "local")) -> tuple[str, dict]:
    session_id = uuid.uuid4().hex
    session = {
        "queue": queue.Queue(),
        "approvals": {},
        "closed": False,
        "cancelled": threading.Event(),
        "identity_key": identity_key,
        "started_at": time.monotonic(),
        "last_activity": time.monotonic(),
        "current_tool": None,
        "steps": 0,
    }
    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = session
    return session_id, session


def _drop_session(session_id: str) -> None:
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(session_id, None)
    if session:
        session["closed"] = True
        session["cancelled"].set()
        engine = session.get("engine")
        if engine is not None:
            engine.cancel()
        # Unblock any approval still waiting so the worker can exit.
        for pending in session["approvals"].values():
            pending["approved"] = False
            pending["event"].set()


def _wait_for_approval(session: dict, tool: Tool, args: dict) -> bool:
    approval_id = uuid.uuid4().hex
    event = threading.Event()
    pending = {"event": event, "approved": False}
    session["approvals"][approval_id] = pending
    session["queue"].put(
        {
            "type": "approval_request",
            "approval_id": approval_id,
            "tool": tool.name,
            "args": _safe_args(args),
        }
    )
    granted = event.wait(timeout=_APPROVAL_TIMEOUT_SECONDS)
    session["approvals"].pop(approval_id, None)
    if not granted:
        session["queue"].put({"type": "approval_timeout", "approval_id": approval_id})
        return False
    return bool(pending["approved"])


def _safe_args(args: dict) -> dict:
    """Trim large tool arguments so a huge file body doesn't bloat the SSE event."""
    out: dict = {}
    for key, value in args.items():
        text = str(value)
        out[key] = text if len(text) <= 4000 else text[:4000] + "…(truncated)"
    return out


def _touch_session(session: dict, *, current_tool: str | None = None, step: bool = False) -> None:
    session["last_activity"] = time.monotonic()
    session["current_tool"] = current_tool
    if step:
        session["steps"] = int(session.get("steps", 0)) + 1


def _search_knowledge(_workspace_root, query: str = "", **_kwargs) -> str:
    """Query TrinaxAI's indexed knowledge base (RAG) and return matching passages.

    Lets the agent reuse TrinaxAI's retrieval over previously indexed documents,
    not just files in the workspace. Returns file-tagged snippets or a note when
    nothing is indexed / found.
    """
    if state.fusion_retriever is None:
        return "No indexed knowledge base is available. Ask the user to index documents first."
    q = (query or "").strip()
    if not q:
        return "error: 'query' must not be empty"
    try:
        nodes = state.fusion_retriever.retrieve(q)[: config.SIMILARITY_TOP_K]
    except Exception as exc:  # noqa: BLE001 - retrieval failure is reported to the model
        return f"error: knowledge search failed: {exc}"
    if not nodes:
        return f"No indexed passages match: {q}"
    lines = []
    for index, node in enumerate(nodes, start=1):
        meta = getattr(node, "metadata", {}) or {}
        rel = meta.get("rel_path") or meta.get("file_path") or "unknown"
        text = node.get_content() if hasattr(node, "get_content") else str(node)
        snippet = text.strip().replace("\n", " ")
        if len(snippet) > 600:
            snippet = snippet[:600] + "…"
        lines.append(f"[{index}] {rel}\n{snippet}")
    return "\n\n".join(lines)


_SEARCH_KNOWLEDGE_TOOL = Tool(
    name="search_knowledge",
    description=(
        "Search TrinaxAI's indexed knowledge base (documents indexed via RAG) for passages "
        "relevant to a query. Use this to consult indexed documents outside the workspace."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for in the indexed knowledge base."},
        },
        "required": ["query"],
    },
    handler=_search_knowledge,
    dangerous=False,
)


def _web_search(_workspace_root, query: str = "", **_kwargs) -> str:
    """Search the public web (via TrinaxAI's configured provider) and return results.

    Gives the agent live information beyond the workspace and the indexed
    knowledge base. Returns titled snippets with URLs, or a note when web search
    is disabled or nothing is found.
    """
    from .web_search_service import WebSearchError, search_web

    q = (query or "").strip()
    if not q:
        return "error: 'query' must not be empty"
    try:
        results, provider = search_web(q)
    except WebSearchError as exc:
        return f"error: web search unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001 - report failures to the model
        return f"error: web search failed: {exc}"
    if not results:
        return f"No web results found for: {q}"
    lines = [f"Web results (via {provider}) for: {q}"]
    for index, item in enumerate(results, start=1):
        title = (item.get("title") or "").strip() or "(untitled)"
        url = (item.get("url") or "").strip()
        snippet = (item.get("snippet") or "").strip().replace("\n", " ")
        if len(snippet) > 600:
            snippet = snippet[:600] + "…"
        lines.append(f"[{index}] {title}\n{url}\n{snippet}")
    return "\n\n".join(lines)


_WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description=(
        "Search the public web for up-to-date information relevant to a query. Use this when "
        "the answer needs current facts or sources not present in the workspace or indexed knowledge."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for on the web."},
        },
        "required": ["query"],
    },
    handler=_web_search,
    dangerous=False,
)


def _deep_research(_workspace_root, query: str = "", **_kwargs) -> str:
    """Run TrinaxAI's cited multi-pass web research for the agent."""
    from .research_service import _research_sync

    q = (query or "").strip()
    if not q:
        return "error: 'query' must not be empty"
    result = _research_sync(ResearchRequest(
        query=q,
        search_query=q,
        web_search=True,
        include_local=False,
        depth=3,
    ))
    if result.get("error_code"):
        return "error: deep research is temporarily unavailable"
    sources = [
        f"[{index}] {source.get('title') or source.get('file')}\n{source.get('url') or ''}"
        for index, source in enumerate(result.get("sources") or [], start=1)
    ]
    return f"{result.get('answer') or ''}\n\nSOURCES\n" + "\n".join(sources)


_DEEP_RESEARCH_TOOL = Tool(
    name="deep_research",
    description=(
        "Perform multi-pass web research and return a synthesized answer with cited sources. "
        "Use for comparisons, detailed reports, or questions requiring several perspectives."
    ),
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The research question."}},
        "required": ["query"],
    },
    handler=_deep_research,
    dangerous=False,
)


def _agent_tools(
    web_search: bool = False,
    knowledge_search: bool = True,
    deep_research: bool = False,
) -> tuple[Tool, ...]:
    """Default file/shell tools plus TrinaxAI's RAG knowledge search.

    When ``web_search`` is enabled the agent also gets a live web-search tool.
    """
    tools = (*DEFAULT_TOOLS,)
    if knowledge_search:
        tools = (*tools, _SEARCH_KNOWLEDGE_TOOL)
    if web_search:
        tools = (*tools, _WEB_SEARCH_TOOL)
    if deep_research:
        tools = (*tools, _DEEP_RESEARCH_TOOL)
    return tools


def _run_engine_worker(session: dict, req: AgentRequest, workspace: Path, model: str) -> None:
    q: queue.Queue = session["queue"]

    def on_tool_start(tool: Tool, args: dict) -> None:
        _touch_session(session, current_tool=tool.name, step=True)
        q.put({"type": "tool_start", "tool": tool.name, "dangerous": tool.dangerous, "args": _safe_args(args)})

    def on_tool_result(tool: Tool, result: str) -> None:
        _touch_session(session, current_tool=None)
        q.put({"type": "tool_result", "tool": tool.name, "result": result[:4000]})

    def on_token(text: str) -> None:
        _touch_session(session, current_tool=None)
        q.put({"type": "token", "content": text})

    def on_confirm(tool: Tool, args: dict) -> bool:
        if session.get("closed"):
            return False
        return _wait_for_approval(session, tool, args)

    engine = AgentEngine(
        model=model,
        verifier_model=getattr(config, "MODEL_DEEP", None) or getattr(config, "MODEL_CODE", None),
        workspace_root=workspace,
        ollama_url=getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434"),
        max_steps=int(req.max_steps or 25),
        num_ctx=_agent_num_ctx(),
        tools=_agent_tools(
            web_search=bool(getattr(req, "web_search", False)),
            knowledge_search=bool(getattr(req, "knowledge_search", True)),
            deep_research=bool(getattr(req, "deep_research", False)),
        ),
        on_tool_start=on_tool_start,
        on_tool_result=on_tool_result,
        on_token=on_token,
        on_confirm=None if req.yolo else on_confirm,
        inference_guard=_agent_inference_slot,
        should_cancel=session["cancelled"].is_set,
    )
    session["engine"] = engine
    try:
        messages = [dict(m) for m in req.messages]
        answer = engine.run(messages)
        q.put({"type": "done", "answer": answer})
    except AgentCancelled:
        LOG.info("Agent worker cancelled after client disconnect")
    except Exception as exc:  # noqa: BLE001 - report failures to the client
        LOG.exception("Agent worker failed")
        q.put({"type": "error", "error": str(exc)[:300]})
    finally:
        q.put(None)  # sentinel: no more events


def _agent_event_stream(session_id: str, session: dict, req: AgentRequest, workspace: Path, model: str):
    q: queue.Queue = session["queue"]
    q.put({"type": "start", "session_id": session_id, "workspace": str(workspace), "model": model})
    worker = threading.Thread(
        target=_run_engine_worker, args=(session, req, workspace, model), daemon=True
    )
    worker.start()
    try:
        while True:
            try:
                event = q.get(timeout=1.0)
            except queue.Empty:
                now = time.monotonic()
                elapsed = now - session["started_at"]
                idle = now - session["last_activity"]
                timeout = elapsed >= _AGENT_MAX_SECONDS
                stalled = idle >= _AGENT_STALL_SECONDS and not session.get("approvals")
                if timeout or stalled:
                    session["cancelled"].set()
                    engine = session.get("engine")
                    if engine is not None:
                        engine.cancel()
                    reason = (
                        f"Agent execution timed out after {int(elapsed)} seconds."
                        if timeout
                        else f"Agent stalled: no tokens or tool activity for {int(idle)} seconds."
                    )
                    yield _sse({"type": "error", "error": reason, "recoverable": True})
                    break
                yield _sse({
                    "type": "status",
                    "state": "running",
                    "elapsed_seconds": int(elapsed),
                    "idle_seconds": int(idle),
                    "current_tool": session.get("current_tool"),
                    "steps": int(session.get("steps", 0)),
                    "last_activity": time.time() - idle,
                })
                continue
            if event is None:
                break
            yield _sse(event)
    finally:
        _drop_session(session_id)
        worker.join(timeout=2)
    yield _sse_done()


async def agent(req: AgentRequest, request: Request):
    """Open an SSE stream that runs the agent for one turn."""
    _authorize_system(request)
    _authorize_http_yolo(req, request)
    enforce_rate_limit(request, bucket="chat")
    workspace = _resolve_workspace(req.workspace)
    model = _resolve_model(req.model, req.messages)
    session_id, session = _register_session(_identity_key(request))
    return StreamingResponse(
        _agent_event_stream(session_id, session, req, workspace, model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def agent_approve(req: AgentApprovalRequest, request: Request):
    """Resolve a pending dangerous action for a running agent stream."""
    _authorize_system(request)
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(req.session_id)
    if session is not None and session["identity_key"] == _identity_key(request):
        pending = session["approvals"].get(req.approval_id)
        if pending is not None:
            pending["approved"] = bool(req.approved)
            pending["event"].set()
            return {"ok": True, "approved": bool(req.approved)}
    raise HTTPException(status_code=404, detail="No pending approval with that id (it may have timed out).")


def _browse_start_dir(path: str | None) -> Path:
    return _resolve_workspace(path)


async def agent_browse(request: Request):
    """List sub-directories of a host path so the PWA can offer a folder picker.

    Read-only and directory-only: never lists files and never returns their
    contents. Used solely to choose the agent's workspace root.
    """
    _authorize_system(request)
    resolved = _browse_start_dir(request.query_params.get("path"))
    roots = _configured_workspace_roots()
    enclosing_root = next(root for root in roots if resolved == root or root in resolved.parents)
    entries = []
    try:
        for child in sorted(resolved.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith(".") or not child.is_dir():
                continue
            try:
                safe_child = child.resolve()
            except OSError:
                continue
            if not _workspace_is_allowed(safe_child, roots):
                continue
            try:
                readable = os.access(safe_child, os.R_OK)
            except OSError:
                readable = False
            entries.append({"name": child.name, "path": str(safe_child), "readable": readable})
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {resolved}")
    parent = str(resolved.parent) if resolved != enclosing_root else None
    return {"path": str(resolved), "parent": parent, "home": str(roots[0]), "directories": entries}


__all__ = [name for name in globals() if not name.startswith("__")]
