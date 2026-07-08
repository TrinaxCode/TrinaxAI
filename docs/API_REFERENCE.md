# TrinaxAI API Reference

The RAG API is a FastAPI server (default port **3333**) that powers the PWA, CLI, and any third-party integrations. System endpoints require authorization. Chat endpoints are open but constrained by the configured CORS allowlist.

---

## Authentication

System endpoints (`/system/*`, `/app-state`, `/v1/memory`, collection CRUD) require authorization:

- **localhost** — allowed by default.
- **private LAN** — disabled by default. Enable explicitly with `TRINAXAI_ALLOW_LAN_SYSTEM=1`.
- **Admin token** — set `TRINAXAI_ADMIN_TOKEN` in `.env` and pass it as the `X-Admin-Token: <token>` header.

Chat endpoints (`/v1/chat/completions`, `/health`) are open to trusted origins (CORS filter on private IPs + ports 3334/3335).

---

## Chat & Retrieval

### `POST /v1/chat/completions`

OpenAI-compatible chat endpoint with RAG retrieval. Supports SSE streaming.

**Request:**
```json
{
  "model": "auto",
  "messages": [
    {"role": "user", "content": "How does the auth module work?"},
    {"role": "assistant", "content": "..."}
  ],
  "stream": true,
  "collections": ["default", "my-project"]
}
```

**Response (streaming SSE):**
```
data: {"trinaxai":{"model":"qwen2.5-coder:7b","project":"Insider"}}
data: {"choices":[{"delta":{"content":"The auth module..."}}]}
data: {"trinaxai_sources":[{"file":"auth.py","snippet":"...","score":0.89}]}
data: [DONE]
```

**Non-streaming:**
```json
{
  "choices": [{"message": {"role": "assistant", "content": "..."}}],
  "trinaxai": {"model": "qwen2.5-coder:7b", "sources": [...]}
}
```

| Field | Notes |
|---|---|
| `model` | `"auto"` (default) or any Ollama model name |
| `stream` | `true` for SSE, `false` for single JSON response |
| `collections` | Optional list of collection IDs to search |

---

### `POST /v1/research`

Deep multi-pass research query with sub-question decomposition.

**Request:**
```json
{
  "query": "Compare authentication patterns across the project",
  "depth": 2,
  "collections": ["default"]
}
```

**Response:** SSE stream with research pass results and final synthesis.

---

## System Control

### `POST /system/shutdown`

Shuts down Ollama + RAG API. **Requires authorization.**

Returns `{"ok": true, "output": "AI shutdown initiated. ..."}`.

### `POST /system/startup`

Starts Ollama + RAG API. **Requires authorization.**

Returns `{"ok": true|false, "output": "...", "error": "..."}`.

### `POST /system/stop-all`

Stops all services immediately. **Requires authorization.**

### `POST /system/reload`

Hot-reloads the RAG index from `storage/`. **Requires authorization.**

Returns `{"ok": true}` or error.

### `POST /system/self-test`

Runs automated health checks: Ollama, embeddings, RAG query. **Requires authorization.**

Returns `{"ok": true|false, "results": {"ollama": bool, "embedding": bool, "rag_query": bool, "rag_indexed": bool}}`.

---

## Indexing

### `POST /system/index-upload`

Upload a folder for indexing (browser file picker). **Requires authorization.**

**Request:** `multipart/form-data` with files from a folder.

**Response:** `{"job_id": "abc123", "status": "starting"}`

### `GET /system/index-jobs/{job_id}`

Poll an index job's progress.

**Response:**
```json
{
  "status": "indexing",
  "progress": 65,
  "phase": "embedding",
  "eta": 12
}
```

### `POST /system/index-jobs/{job_id}/cancel`

Cancel a running index job. **Requires authorization.**

---

## Collections

### `GET /collections`

List all RAG collections.

**Response:** `["default", "my-project", "docs"]`

### `POST /collections`

Create a collection. **Requires authorization.**

**Request:** `{"name": "My Project"}`

### `PUT /collections/{collection_id}`

Rename a collection. **Requires authorization.**

**Request:** `{"name": "New Name"}`

### `DELETE /collections/{collection_id}`

Delete a collection and all its chunks. **Requires authorization.**

---

## Knowledge Browser

### `GET /v1/sources`

List indexed files with chunk counts in a collection.

**Query:** `?collection=default`

**Response:**
```json
[
  {"file": "app/auth.py", "project": "Insider", "chunks": 45, "collection": "General"}
]
```

### `GET /v1/sources/{file_path}`

Get full chunks for a specific file.

**Query:** `?collection=default&limit=50`

---

## Memory

### `GET /v1/memory`

List all persistent memory entries.

**Response:** `[{"id": "abc", "text": "User prefers Python", "tags": ["pref"]}]`

### `POST /v1/memory`

Add a memory entry. **Requires authorization.**

**Request:** `{"text": "User prefers Python 3.12+", "tags": ["pref", "python"]}`

### `DELETE /v1/memory/{memory_id}`

Delete a memory entry. **Requires authorization.**

### `POST /v1/memory/refresh`

Refresh the auto-summary from memory entries. **Requires authorization.**

### `GET /v1/memory/summary`

Get the current auto-summary text.

---

## File Watcher

### `POST /v1/watch/start`

Start the file system watcher. **Requires authorization.** Requires `watchdog` pip package.

**Request:** `{"paths": ["/home/user/projects"], "collection": "default"}`

### `POST /v1/watch/stop`

Stop the file watcher. **Requires authorization.**

### `GET /v1/watch/status`

Get watcher status: running, watching paths, event count.

---

## Stats

### `GET /v1/stats`

Get usage statistics from `storage/usage.jsonl`.

**Response:**
```json
{
  "total_messages": 1523,
  "estimated_tokens": 450000,
  "top_models": {"qwen2.5-coder:3b": 800},
  "top_collections": {"default": 1200}
}
```

---

## Health & Telemetry

### `GET /health`

System status overview.

**Response:**
```json
{
  "status": "ok",
  "models": ["qwen2.5-coder:3b", "llama3.2:3b", "bge-m3"],
  "indexed": true,
  "profile": "16gb",
  "projects": ["Insider", "MyApp"],
  "features": {"reranker": false, "ocr": false, "watcher": false}
}
```

### `GET /resources`

Basic local RAM/VRAM telemetry. Requires `psutil`.

**Response:**
```json
{
  "ram": {"total_gb": 32, "used_gb": 12, "percent": 37.5},
  "ollama_processes": 2
}
```

---

## App State (Cross-Device Sync)

### `GET /app-state`

Read shared configuration stored in `storage/app_state.json`.

### `PUT /app-state`

Save shared state (settings, chat history, preferences). **Requires authorization.**

**Request:** `{"values": {"theme": "dark", "language": "en"}}`

### `DELETE /app-state`

Nuclear reset of shared state to host defaults. **Requires authorization.**

---

## Document Extraction

### `POST /documents/extract`

Extract text from PDF/DOCX/TXT for temporary analysis (not indexed).

**Request:** `multipart/form-data` with file.

**Response:** `{"ok": true, "name": "doc.pdf", "text": "...", "chars": 5000, "truncated": false}`

---

## Error Codes

| HTTP | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request (missing params, invalid data) |
| 401 | Unauthorized (system endpoint without token) |
| 404 | Not found (collection, job, memory) |
| 429 | Rate limited (30 req/min per IP) |
| 500 | Internal error |
| 501 | Not implemented (e.g., watchdog missing) |
| 503 | Service unavailable (Ollama down, index not loaded) |

---

## Rate Limiting

- **30 requests per minute** per IP address
- Window: 60 seconds rolling
- Affects: chat completions and system endpoints
- Returns HTTP 429 when exceeded
