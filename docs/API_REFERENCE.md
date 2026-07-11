# TrinaxAI API Reference

The FastAPI service connects the PWA and CLI to RAG, memory, voice, and local administration. Its default managed URL is `https://localhost:3333`. Live schema endpoints are `/docs`, `/redoc`, and `/openapi.json`.

## Authorization

Protected endpoints allow a request when the TCP peer is loopback, `X-Admin-Token` is valid, or the peer is private and LAN system control is explicitly enabled. A supplied invalid token returns `403`; `X-Forwarded-For` is not trusted.

Chat, STT, and TTS use separate per-IP rate-limit buckets. General defaults are 30 requests per 60 seconds.

```bash
curl -k https://localhost:3333/health
curl -k -H "X-Admin-Token: $TOKEN" https://localhost:3333/v1/memory
```

## Endpoint map

| Method and path | Access | Purpose |
|---|---|---|
| `POST /v1/chat/completions` | Rate limited | JSON or SSE RAG chat. |
| `POST /v1/research` | Protected | Multi-pass RAG research; JSON response. |
| `GET /v1/voice/capabilities` | Public | Available local voice engines. |
| `POST /v1/voice/stt`, `POST /v1/voice/tts` | Rate limited | Local speech recognition/synthesis. |
| `GET/DELETE /v1/sources/*` | Protected | Browse or remove indexed sources/chunks. |
| `/v1/memory/*`, `/v1/watch/*` | Protected | Memory and filesystem watcher. |
| `POST /v1/usage`, `GET /v1/stats` | Protected | Local-only usage data. |
| `GET /health`, `GET /resources` | Public | Service health and RAM data. |
| `GET /app-state` | Public | Shared PWA state with ETag support. |
| `PUT/DELETE /app-state` | Protected | Synchronize or reset PWA state. |
| `POST /attachments`, `GET /attachments/{attachment_id}` | Public | Store/retrieve host-backed chat attachments. |
| `POST /documents/extract` | Public | Temporary document text extraction. |
| `GET /collections` | Public | Collection metadata. |
| `POST/PATCH/DELETE /collections/*` | Protected | Collection administration. |
| `/system/*` | Protected | Services, indexing, reload, and self-test. |

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
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`messages` accepts 1–100 `system`, `user`, or `assistant` objects, requires a user message, and allows up to 2,000,000 total characters. A null/empty model enables routing. Up to 50 collection IDs are accepted.

With `stream=false`, the result is an OpenAI-shaped `chat.completion` plus `trinaxai` source metadata. With `stream=true`, SSE events contain `trinaxai` metadata, `choices[].delta.content`, `trinaxai_sources`, and finally `[DONE]`. A missing index produces an informative response rather than an HTTP failure.

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

`POST /v1/research` clamps depth to 1–3 and returns JSON fields `answer`, `sub_questions`, `sources`, `passes`, and `model`.

## Sources and collections

```http
GET    /v1/sources?collection=default
GET    /v1/sources/{collection}/{file}/chunks?limit=50&offset=0&q=text
DELETE /v1/sources/{collection}/{file}
DELETE /v1/sources/{collection}
```

File paths may contain slashes and must be URL-encoded. Chunk limits are clamped to 1–500. Deleting all sources from the default collection is rejected.

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
DELETE /system/index-imports  {"path":"...","collection_id":"..."}
```

The delete operation only accepts safe paths inside managed local imports.

## Memory, watcher, and usage

```http
GET    /v1/memory
POST   /v1/memory             {"text":"...","tags":["preference"]}
DELETE /v1/memory/{memory_id}
POST   /v1/memory/refresh     {"scope":null}
GET    /v1/memory/summary

POST /v1/watch/start          {"paths":["/path"],"collection":"default"}
POST /v1/watch/stop
GET  /v1/watch/status

POST /v1/usage               {"engine":"ollama","model":"...","est_tokens":100}
GET  /v1/stats
```

The watcher requires `watchdog` and existing directories. Usage data never leaves local storage.

## Shared state

- `GET /app-state` returns `{ok, values}` with an `ETag`, supports `If-None-Match`, and may return `304`.
- `PUT /app-state` accepts `{"values":{"tc-key":"string-value"}}`; only string `tc-*` entries are retained.
- `DELETE /app-state` additionally requires `X-TrinaxAI-Confirm: reset-app-state` and resets local runtime data.

The default state limit is 6 MiB (`TRINAXAI_APP_STATE_MAX_BYTES`).

## Attachments, documents, and voice

`POST /attachments` accepts one multipart file and stores it under `storage/chat_attachments/` so synchronized conversations can open it in another browser. It returns the ID, name, size, MIME type, and a `server:` storage key. `GET /attachments/{attachment_id}` returns safe image, PDF, and text types inline; unknown types are downloaded with `nosniff`. `DELETE /attachments/{attachment_id}` is protected like other system operations. Defaults are 250 MiB per file, 1 GiB total, and 1,000 retained files. Uploads and downloads are rate limited. These routes remain public within the configured network boundary; do not expose the API to untrusted clients.

`POST /documents/extract` accepts one multipart file and returns `{ok, name, text, chars, truncated}`. PDF, DOCX, and PPTX have specialized extraction; text formats are decoded directly. Extraction does not index the document.

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
