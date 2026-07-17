# TrinaxAI API Reference

The FastAPI service connects the PWA and CLI to RAG, memory, voice, and local administration. Its default managed URL is `https://localhost:3333`. Live schema endpoints are `/docs`, `/redoc`, and `/openapi.json`.

## Authorization

Protected endpoints allow a direct loopback request, a scoped paired-device
credential (`X-TrinaxAI-Device-Token`), or the administrator super-credential
(`X-Admin-Token`). The private-LAN fallback is limited to legacy system control
when no admin token is configured and LAN control was explicitly enabled. The local PWA gateway strips
client identity headers and signs the original peer, method and path with a
fresh HMAC assertion. FastAPI accepts that assertion only from loopback;
`Forwarded` and `X-Forwarded-For` are never identity.

Chat, STT, and TTS use separate monotonic token buckets per verified IP.
General capacity is 30 and an empty bucket refills over 60 seconds.

```bash
curl -k https://localhost:3333/health
curl -k -H "X-Admin-Token: $TOKEN" https://localhost:3333/v1/memory
curl -k -H "X-TrinaxAI-Device-Token: $DEVICE_TOKEN" https://localhost:3333/v1/memory
```

Device scopes are `chat`, `read_private`, `index`, `system`, `agent`, and
`agent_yolo`. Admin tokens grant every scope. An invalid supplied credential is
never bypassed merely because its transport peer is loopback. Default pairing
grants only `chat` and `read_private`; grant elevated scopes only when needed.

## Endpoint map

| Method and path | Access | Purpose |
|---|---|---|
| `POST /v1/chat/completions`, `/v1/research` | `chat` + rate limited | JSON/SSE chat and research. |
| `POST /v1/agent`, `/v1/agent/approve`, `GET /v1/agent/browse` | `agent` | Workspace agent stream, approval, and registered-root browsing. |
| `GET/POST /v1/voice/*` | `chat` + rate limited | Speech recognition and synthesis. |
| `POST /documents/extract` | LAN/VPN or `chat` + rate limited | Stateless temporary document extraction. |
| `GET /v1/sources/*`, `/v1/memory/*`, `GET /v1/stats` | `read_private` | Private indexed and user data. |
| `DELETE /v1/sources/*`, `/v1/watch/*`, collection mutations | `index` | Index content and watcher administration. |
| `POST /v1/usage` | `chat` | Local usage accounting. |
| `GET /health`, `GET /resources` | Public | Service health and RAM data. |
| `GET/PUT/DELETE /app-state` | `read_private` | Versioned shared PWA state and factory reset. |
| `POST /attachments`, `GET/DELETE /attachments/{attachment_id}` | `read_private` + rate limited | Store, retrieve, or delete host-backed chat attachments. |
| `GET /collections` / mutations | `read_private` / `index` | Collection metadata and administration. |
| `/system/index*` / other `/system/*` | `index` / `system` | Indexing versus lifecycle/reload/self-test. |
| `/v1/pairing/*` | Mixed | One-time device pairing and revocation. |

## Device pairing

Create codes only from a real loopback peer or with the admin token:

```http
POST /v1/pairing/start
{"scopes":["chat","read_private"],"ttl_seconds":300,"device_ttl_days":null}
```

The clear code is returned once. A LAN/VPN client claims it with
`POST /v1/pairing/claim {"code":"ABCD-EFGH","device_name":"Phone"}`.
Claim attempts are limited to five per client per five minutes. The returned
device token is also shown once; only keyed hashes are persisted. Codes expire
after 60–900 seconds and are single-use.

The PWA stores the bearer in `sessionStorage`, so closing the browser removes
it from that session. The registry and hashing secret are separate atomic
mode-0600 files. Pairing authenticates a device/capability; it is not a
multi-user account or authorization delegation system.

`GET /v1/pairing/me` and `DELETE /v1/pairing/me` use the device-token header.
`GET /v1/pairing/devices` and `DELETE /v1/pairing/devices/{id}` are loopback/admin
operations. Revocation takes effect for FastAPI and the Ollama gateway.

## RAG chat

```http
POST /v1/chat/completions
Content-Type: application/json
```

```json
{
  "model": null,
  "messages": [{"role": "user", "content": "How does authorization work?"}],
  "stream": true,
  "collections": ["default"],
  "mode": "knowledge",
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`messages` accepts 1–100 `system`, `user`, or `assistant` objects, requires a
user message, limits each message to 100,000 characters and the conversation to
200,000 characters. A null/empty model enables routing. Up to 50 collection IDs
are accepted. `mode` is one of:

- `auto`: classify whether indexed evidence is needed;
- `knowledge`: always retrieve, or return the explicit no-index response;
- `model`: do not retrieve, even when the wording resembles a document query.

With `stream=false`, the result is an OpenAI-shaped `chat.completion` plus
`trinaxai` metadata (`mode`, `rag_used`, collections, result count, request ID
and sources) and an explicitly estimated `usage`. With `stream=true`, SSE emits
the plan, content deltas, sources, retrieval metadata, estimated usage, timing,
post-stream **quality heuristics**, and finally `[DONE]`. These heuristics detect
likely omissions or malformed output; they are not a compiler, type checker,
browser test or proof of correctness. A missing index produces an informative
response rather than an HTTP failure.

## Research

```json
{
  "query": "Compare persistence mechanisms",
  "collections": ["default"],
  "depth": 2,
  "model": null,
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`POST /v1/research` clamps depth to 1–3 and returns JSON fields `answer`,
`sub_questions`, `sources`, `passes`, `model`, `web_search`, `web_provider` and
`search_query`. Web research searches first, then attempts to read a bounded set
of pages. Each web source reports `content_scope: "full_page"` when bounded page
text was extracted or `"snippet_only"` with `fetch_error` when only the search
excerpt was available. URL fetches reject credentials, non-HTTP schemes,
private/loopback/link-local destinations and unsafe redirects, resolve once and
connect to the validated public IP to limit SSRF/DNS-rebinding exposure, and cap
redirects, bytes, text and time. `full_page` still means bounded extracted text,
not a complete archival copy.

## Sources and collections

```http
GET    /v1/sources?collection=default
GET    /v1/sources/{collection}/{file}/chunks?source_id=ID&limit=50&offset=0&q=text
DELETE /v1/sources/{collection}/{file}?source_id=ID
DELETE /v1/sources/{collection}
```

File paths may contain slashes and must be URL-encoded. A collection can contain
the same relative path from several independently synchronized roots; use the
`source_id` returned by the source list to address one root without deleting its
namesake. Chunk limits are clamped to 1–500. Deleting all sources from the
default collection is rejected.

```http
GET    /collections
POST   /collections                 {"name":"Documentation"}
PATCH  /collections/{collection_id} {"name":"New name"}
DELETE /collections/{collection_id}
```

Collection listing returns `{ok, collections}`. The default collection cannot be deleted. Removing collection metadata and clearing its indexed sources are distinct operations.

## Browser indexing

`POST /system/index-upload` accepts multipart `files` plus optional `label`, `collection_id`, `embed_model`, `aggressive_quant`, and `watch_id`. It returns a `job_id` and upload summary while indexing continues in the background.

```http
GET  /system/index-jobs/{job_id}
POST /system/index-jobs/{job_id}/cancel
POST /system/index-jobs/{job_id}/retry
DELETE /system/index-imports  {"path":"...","collection_id":"..."}
```

Job status persists across frontend reconnects and reports phase, elapsed time, recent activity, page/chunk/batch counters, and whether `progress` is exact. Failed or cancelled jobs can be retried while their uploaded source remains available. The delete operation only accepts safe paths inside managed local imports.

## Memory, watcher, and usage

```http
GET    /v1/memory
POST   /v1/memory             {"text":"...","tags":["style"],"kind":"preference","provenance":"manual","expires_at":null}
PATCH  /v1/memory/{memory_id} {"text":"...","kind":"decision","clear_expiration":true}
DELETE /v1/memory/{memory_id}
POST   /v1/memory/context     {"query":"current turn","max_entries":8}
POST   /v1/memory/refresh     {"scope":null}
GET    /v1/memory/summary

POST /v1/watch/start          {"paths":["/path"],"collection":"default"}
POST /v1/watch/stop
GET  /v1/watch/status

POST /v1/usage               {"engine":"ollama","model":"...","est_tokens":100}
GET  /v1/stats
```

Memory kinds are `fact`, `preference`, `decision`, and `note`; provenance is
`manual` or `inferred`, and expired entries are excluded. `/context` returns
only active entries relevant to the query. PWA, CLI, and backend delimit those
entries as untrusted data rather than instructions. The global summary is a
human-facing overview only and is never injected into a turn. The PWA confirms
deletion and exposes edit, provenance, kind, and expiry controls. Its local
`tc-project-memory` scratchpad is not prompt context.

The watcher requires `watchdog` and existing directories. Usage data never leaves local storage.

## Shared state

- `GET /app-state` requires authorization and returns
  `{ok, schema_version:2, revision, values}` with an ETag of the form
  `"trinaxai-app-state-v2-N"`; `If-None-Match` may return `304`.
- `PUT /app-state` sends `schema_version:2`, a stable `device_id`, the
  `base_revision`, and ordered `set`/`delete` operations. The server applies the
  batch atomically only when the base revision matches. A stale writer receives
  `409` plus the current revision/values and must merge/retry. `If-Match` may
  carry the same revision.
- Legacy `{"values":{...}}` is accepted only with optimistic concurrency (or
  against a pristine revision-zero store); otherwise the API returns `428`.
- `DELETE /app-state` requires authorization plus
  `X-TrinaxAI-Confirm: reset-app-state` and advances the revision so an offline
  pre-reset client cannot silently restore deleted state.

The default state limit is 6 MiB (`TRINAXAI_APP_STATE_MAX_BYTES`).

## Attachments, documents, and voice

`POST /attachments` accepts one authorized multipart upload and stores it under
`storage/chat_attachments/` so synchronized conversations can open it in
another authorized browser. It returns the ID, name, size, MIME type, and a
`server:` storage key. GET and DELETE require the same authorization and are
rate limited. Unknown response types are downloads with `nosniff`. Defaults are
512 MiB per file, 4 GiB total, and 1,000 retained files. Chat history stores the
attachment reference, not a second persistent copy of the full extracted text.

## Agent

`POST /v1/agent` streams tool-use events over SSE; dangerous calls pause at an
`approval_request` until `POST /v1/agent/approve` accepts or denies it. Approvals
must include both the `session_id` from the stream's `start` event and
the `approval_id`, and must use the same authenticated identity that opened the stream.
Requested workspaces must be descendants of `TRINAXAI_AGENT_WORKSPACE_ROOTS` (configured
index roots and the repository are the fallback), and filesystem roots are
rejected. HTTP yolo is off by default and, even when enabled, only works over a
real loopback transport with the `agent_yolo` capability. Remote agent callers
always approve dangerous actions individually.
File tools reject symlink/path escapes. On Linux, shell commands require
networkless bubblewrap and expose only the workspace as writable; on unsupported
hosts terminal execution fails closed unless the operator explicitly accepts
full user-level access with `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1`.

`POST /documents/extract` accepts one multipart file and returns `{ok, name, text, chars, truncated}`. PDF, DOCX, and PPTX have specialized extraction; text formats are decoded directly. Extraction does not index or persist the document, so an unauthenticated peer may use it from the local network or VPN. Public-network callers still require the `chat` scope.

```http
GET  /v1/voice/capabilities
POST /v1/voice/stt   multipart: file, lang=en
POST /v1/voice/tts   {"text":"Hello","lang":"en"}
```

TTS returns audio bytes with the detected content type. STT/TTS return `501` if no suitable local backend is installed.

## System and diagnostics

| Endpoint | Result |
|---|---|
| `POST /system/shutdown` | Stop AI while leaving the PWA available. |
| `POST /system/startup` | Start AI services. |
| `POST /system/stop-all` | Stop all services. |
| `POST /system/reload` | Reload the persisted index in memory. |
| `POST /system/self-test` | Check Ollama, embeddings, and RAG/index state. |
| `GET /health` | Models, profile, collections, index state, and feature flags. |
| `GET /resources` | RAM values in bytes; VRAM is currently `null`. |

FastAPI errors use `{"detail":"message"}`. Common statuses are `400`, `403`, `404`, `409`, `413`, `422`, `429`, `500`, `501`, and `503`. See [configuration](CONFIGURATION.md) for limits and network settings.
