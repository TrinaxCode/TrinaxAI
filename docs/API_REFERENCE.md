<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🧩 API Reference
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="API_REFERENCE.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The FastAPI service connects the PWA and CLI to RAG, memory, voice, and local administration. Its default managed URL is `https://localhost:3333`. Live schema endpoints are `/docs`, `/redoc`, and `/openapi.json`.

Managed installations prefer HTTPS. Use the public CA printed by `trinaxai
network` with API clients; direct HTTP is only a loopback development fallback.
LAN clients must enter through the PWA gateway on port `3334`, trust the public
CA on their device, and must not connect directly to port `3333` or Ollama
`11434`. For a symptom-first recovery path, see [Troubleshooting](TROUBLESHOOTING.md).

## Authorization

Protected low-risk endpoints allow a direct loopback request, a scoped
paired-device credential (`X-TrinaxAI-Device-Token`), or the administrator
credential (`X-Admin-Token`). Host-only scopes (`system`, `index`, `agent`, and
`agent_yolo`) first require verified original loopback provenance; no credential
and no legacy LAN setting can override that requirement. The local PWA gateway strips
client identity headers and signs the original peer, method and path with a
fresh, single-use HMAC assertion. FastAPI accepts that assertion only from
loopback or an explicitly configured private runtime peer that also proves the
shared key; `Forwarded` and `X-Forwarded-For` are never identity.

Chat, STT, and TTS use separate monotonic token buckets per verified IP.
General capacity is 30 and an empty bucket refills over 60 seconds.

```bash
curl -k https://localhost:3333/health
curl -k -H "X-Admin-Token: $TOKEN" https://localhost:3333/v1/memory
curl -k -H "X-TrinaxAI-Device-Token: $DEVICE_TOKEN" https://localhost:3333/v1/memory
```

Device scopes are `chat`, `read_private`, and `web`; default pairing grants
`chat` and `read_private`. Requests for retired scopes (`index`, `system`,
`agent`, and `agent_yolo`) are rejected, and those scopes are ignored on old
tokens. An admin token can authenticate protected reads but cannot turn a LAN
peer into localhost. An invalid supplied credential is never bypassed merely
because its transport peer is loopback.

## Endpoint map

| Method and path | Access | Purpose |
|---|---|---|
| `POST /v1/chat/completions`, `/v1/research` | `chat` + rate limited | JSON/SSE chat and research. |
| `POST /v1/agent`, `/v1/agent/approve`, `/v1/agent/cancel`, `GET /v1/agent/browse` | Loopback only | Workspace agent stream, approval/cancellation, and registered-root browsing. |
| `GET/POST /v1/voice/*` | `chat` + rate limited | Speech recognition and synthesis. |
| `POST /documents/extract` | LAN/VPN or `chat` + rate limited | Stateless temporary document extraction. |
| `GET /v1/sources/*`, `GET /v1/memory/*`, `POST /v1/memory/context`, `GET /v1/stats` | `read_private` | Private indexed and user data. |
| `DELETE /v1/sources/*`, memory writes, `/v1/watch/*`, collection mutations | Loopback only | Host data and watcher administration. |
| `POST /v1/usage` | `chat` | Local usage accounting. |
| `GET /health`, `GET /ready`, `GET /resources` | Public | Liveness, model-provider readiness, and RAM data. |
| `GET/PUT/DELETE /v1/settings/web-search*` | Loopback only | Host-local web-search provider settings and credential reset. |
| `GET/PUT /app-state` / `DELETE /app-state` | `read_private` / loopback (`system`) | Versioned shared PWA state / factory reset. |
| `POST /attachments`, `GET /attachments/{id}` / `DELETE /attachments/{id}`, `POST /attachments/{id}/open` | `read_private` / loopback (`system`) | Store/retrieve versus delete/open host-backed chat attachments. |
| `GET /collections` / mutations | `read_private` / loopback only | Collection metadata and administration. |
| `/system/index*` / other `/system/*` | Loopback only | Indexing versus lifecycle/reload/self-test. |
| `/v1/pairing/*` | Mixed | One-time device pairing and revocation. |

## Error contract

Every API error returns a safe `error` object (and the same canonical fields in
`detail`):
`category`, internal `code`, user-facing `message`, `recovery`, and `retryable`.
Categories are `internet_unavailable`, `external_service_unavailable`,
`ai_model_unavailable`, `model_loading_failed`, `tool_timeout`,
`permission_denied`, `authentication_failed`, `resource_exhausted`,
`memory_limit_reached`, `gpu_unavailable`, `file_not_found`,
`document_unreadable`, `invalid_input`, `unsupported_format`,
`network_timeout`, `internal_server_error`, and `unknown_error`. Raw exception
details stay in server-side developer logs; `request_id` is returned for support.
Safe idempotent browser/CLI reads retry once when `retryable` is true.

Older RAG responses may identify an empty or missing collection with the legacy
codes `collection_empty` or `collection_not_found`. The PWA maps both to its
**Open indexing** action. API clients should use `category`, `code`,
`recovery`, and `retryable` rather than matching localized message text.

## Device pairing

Create codes only from a real loopback peer. Admin credentials from LAN do not qualify:

```http
POST /v1/pairing/start
{"scopes":["chat","read_private"],"ttl_seconds":300,"device_ttl_days":null}
```

The clear code is returned once. A LAN/VPN client claims it with
`POST /v1/pairing/claim {"code":"ABCD-EFGH","device_name":"Phone"}`.
Claim attempts are limited to five per client per five minutes. The returned
response sets an `HttpOnly; SameSite=Strict` cookie scoped to `/api/rag` and
contains device metadata but no bearer. Only keyed hashes are persisted. Codes
expire after 60–900 seconds and are single-use.

The PWA sends that cookie automatically and does not persist newly claimed
device tokens in `localStorage` or `sessionStorage`. The CLI continues to use
an older bearer only in the `X-TrinaxAI-Device-Token` header (for example via
`TRINAXAI_DEVICE_TOKEN`); `GET /v1/pairing/me` never copies that header into a
response cookie. The registry and hashing secret are separate atomic
mode-0600 files. Pairing authenticates a device/capability; it is not a
multi-user account or authorization delegation system.

`GET /v1/pairing/me` and `DELETE /v1/pairing/me` accept the cookie; the legacy
header remains supported for CLI clients only. `GET /v1/pairing/devices`
and `DELETE /v1/pairing/devices/{id}` are loopback-only operations. Revocation
takes effect for FastAPI and the Ollama gateway.

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
  "think": true,
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`messages` accepts 1–100 `system`, `user`, or `assistant` objects, requires a
user message, limits each message to 100,000 characters and the conversation to
200,000 characters. A null/empty model enables routing. Up to 50 collection IDs
are accepted. `mode` is one of:

- `auto`: classify whether indexed evidence is needed;
- `knowledge`: always retrieve and answer only from retrieved evidence, or return
  an explicit no-index/no-relevant-evidence response;
- `model`: do not retrieve, even when the wording resembles a document query.

In automatic conversational routing, the client selects the capability before calling its endpoint: a direct public lookup such as `Search who TrinaxCode is` uses web search; a question about the user's own projects such as `What Python programs have I made?` uses `knowledge`; and complex multi-source research uses `/v1/research`. Agent execution is never inferred from wording: enter Agent mode explicitly before calling `/v1/agent`. `route_model()` only selects the model and does not select web, RAG, research, or Agent.

`think` is an explicit client preference. `false` disables provider reasoning;
`true` permits it only for analytical or complex tasks; omitted uses
`TRINAXAI_THINKING_MODE`. Simple turns never need the reasoning channel.

With `stream=false`, the result is an OpenAI-shaped `chat.completion` plus
`trinaxai` metadata (`mode`, `rag_used`, `abstained`, collections, result count,
request ID and sources) and an explicitly estimated `usage`. `abstained` is
`true` for deterministic no-index, empty-collection, or no-relevant-evidence
responses, and for a clear model refusal to answer from the supplied context.
With `stream=true`, SSE emits
the plan, content deltas, sources, retrieval metadata, estimated usage, timing,
post-stream **quality heuristics**, and finally `[DONE]`. These heuristics detect
likely omissions or malformed output; they are not a compiler, type checker,
browser test or proof of correctness. A missing index produces an informative
response rather than an HTTP failure.

## Research

### Web-search settings

`GET|PUT|DELETE /v1/settings/web-search` reads, updates or resets host-local search settings. `POST /v1/settings/web-search/test` tests the selected provider from the backend, and `DELETE /v1/settings/web-search/credentials/brave` explicitly removes the managed Brave key. Every route is host-only and requires verified loopback provenance. Secret values are write-only and never serialized.

```json
{
  "query": "Compare persistence mechanisms",
  "collections": ["default"],
  "depth": 2,
  "think": true,
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

`POST /v1/research/preflight` accepts the same request shape and checks Ollama,
the selected model, local collections, and web-provider readiness without
running the full research task.

If a web provider is unavailable, the research response is degraded rather than
an empty error: it explains the classified reason, returns no fabricated web
sources, and labels any fallback answer as general local-model knowledge.

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
rate limited. `POST /attachments/{attachment_id}/open` asks the host OS to open
the stored file with its default application and is also authorized/rate limited.
Unknown response types are downloads with `nosniff`. Defaults are 512 MiB per
file, 4 GiB total, and 1,000 retained files. Chat history stores the attachment
reference, not a second persistent copy of the full extracted text.

## Agent

`POST /v1/agent` streams tool-use events over SSE; dangerous calls pause at an
`approval_request` until `POST /v1/agent/approve` accepts or denies it.
The model decides whether to answer directly or call one or more tools, orders
dependent calls, and synthesizes their results. Web search, deep research,
memory, indexed-document search, and collection discovery are available by
default. The `web_search`, `deep_research`, and `knowledge_search` request
booleans can restrict availability; setting one never forces its execution.
`POST /v1/agent/cancel` stops a running session owned by the same identity. Approvals
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
| `POST /system/stop-all` | Stop all services; only loopback recovery remains at `https://localhost:3334` and LAN access stays closed until local start. |
| `POST /system/reload` | Reload the persisted index in memory. |
| `POST /system/self-test` | Check Ollama, embeddings, and RAG/index state. |
| `GET /health` | Models, active/detected profile, hardware, recommendations, collections, index state, and feature flags. |
| `GET /ready` | Same status payload; returns `503` until Ollama responds. |
| `GET /resources` | RAM and detected VRAM values in bytes, plus the hardware snapshot. |

FastAPI errors use `{"detail": {...}, "error": {...}, "request_id": "..."}`.
`detail` may also include a safe legacy code or field hint for client
compatibility; it never contains raw exception text. Retryable responses include
`Retry-After: 1`. Common statuses are `400`, `403`, `404`, `409`, `413`, `422`,
`429`, `500`, `501`, and `503`. See [Troubleshooting](TROUBLESHOOTING.md) and
[configuration](CONFIGURATION.md) for recovery, limits, and network settings.
