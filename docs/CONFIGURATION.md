<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · ⚙️ Configuration
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.4.0"><img src="https://img.shields.io/badge/version-1.4.0-006bbd" alt="Stable release: 1.4.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="CONFIGURATION.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

TrinaxAI reads environment variables and the repository-root `.env` file. Start with:

```bash
cp .env.example .env
```

Never commit `.env`, certificates, or tokens. [`.env.example`](../.env.example) is the executable template and source of current example values. If a setting change causes a failure, start with the [troubleshooting and recovery guide](TROUBLESHOOTING.md) before changing more variables.
The [environment variable inventory](ENVIRONMENT_VARIABLES.md) is the single
canonical list of every supported `TRINAXAI_*` and `VITE_TRINAXAI_*` setting.

## Loading and precedence

- The backend loads the root `.env`.
- `service_manager.py` passes the environment to the API, Ollama, and the PWA.
- `VITE_*` values are compiled into the frontend by `npm run build`; rebuild after changing them.
- PWA `tc-*` preferences can override frontend model choices without changing `.env`.
- The CLI uses a separate TOML file; see [CLI_REFERENCE.md](CLI_REFERENCE.md).

## Main groups

| Group | Variables |
|---|---|
| Hardware | `TRINAXAI_PROFILE` (`8gb`, `16gb`, `32gb`, `64gb`; auto-detected from CPU/RAM/GPU), `TRINAXAI_PERFORMANCE_MODE` (`fast`, `balanced`, `quality`) |
| Thinking | `TRINAXAI_THINKING_MODE` (backend fallback when a client omits `think`; depth-1 web research defaults to off unless `think` is explicit) |
| Models | `TRINAXAI_MODEL_GENERAL`, `TRINAXAI_MODEL_CODE`, `TRINAXAI_MODEL_DEEP`, `TRINAXAI_MODEL_FAST`, `TRINAXAI_AUTO_ROUTE` |
| Ollama | `OLLAMA_BASE_URL`, `TRINAXAI_NUM_CTX`, `TRINAXAI_NUM_THREAD`, `TRINAXAI_KEEP_ALIVE`, `TRINAXAI_TIMEOUT` |
| Embeddings | `TRINAXAI_EMBED_PRESET`, `TRINAXAI_EMBED`, `TRINAXAI_EMBED_DIMS`, `TRINAXAI_EMBED_WORKERS`, `TRINAXAI_EMBED_BATCH`, `TRINAXAI_EMBED_KEEP_ALIVE` |
| Retrieval | `TRINAXAI_SIMILARITY_TOP_K`, fusion/rerank settings, retrieval TTL and the bounded retriever-combination LRU |
| Indexing | `TRINAXAI_INDEX_DIR`, `TRINAXAI_SOURCE_ID`, `TRINAXAI_INDEX_APPEND`, lock/timeout, chunk and upload limits |
| Network | `TRINAXAI_HOST`, `TRINAXAI_PORT`, `TRINAXAI_RAG_HTTPS`, `TRINAXAI_CORS_ORIGINS` |
| Security | Admin/device credentials, pairing registry/secret, gateway HMAC, agent roots/isolation, rate limits and unsafe escape hatches |
| PWA proxy | Loopback targets, Ollama allowlist/rate limit, shared inference lock/queue, `VITE_TRINAXAI_*` bases and models |
| Voice | `TRINAXAI_VOICE_STT_MODEL`, faster-whisper device/compute type, TTS engine, audio/text limits |

## Profile and performance

| Variable | Default | Values / effect |
|---|---:|---|
| `TRINAXAI_PROFILE` | auto-detected | `8gb`, `16gb`, `32gb`, `64gb`; derived from CPU/RAM/GPU and can be overridden. |
| `TRINAXAI_PERFORMANCE_MODE` | `fast` | `fast`, `balanced`, `quality`; changes retrieval and chunking. |
| `TRINAXAI_THINKING_MODE` | `1` | Backend default when a client omits `think`; `0` disables reasoning. Depth-1 web research disables it by default so the model output is reserved for the answer; an explicit `think` wins. |
| `TRINAXAI_NUM_CTX` | profile-derived | LLM context window. |
| `TRINAXAI_NUM_THREAD` | `min(8, CPU cores)` | CPU threads per request. Never default above the cores you have: oversubscribing makes answers several times slower. |
| `TRINAXAI_KEEP_ALIVE` | profile/mode-derived | How long the chat model stays loaded (`0s`, `15m`, etc.). |
| `TRINAXAI_TIMEOUT` | `300` | Timeout of requests to Ollama, in seconds. |
| `TRINAXAI_AGGRESSIVE_QUANT` | `0` | Enables the aggressive quantization profile. |

The backend detects CPU model/cores, RAM, GPU, and VRAM, and stores the snapshot in `storage/hardware_profile.json`. Leave `TRINAXAI_PROFILE` unset to use the automatic profile. Model recommendations also consider VRAM: a dedicated GPU receives models that fit in it, while a weak GPU with plenty of RAM keeps a CPU/RAM-oriented model.

## Models and Ollama

| Variable | Example value | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL used by the backend. |
| `TRINAXAI_MODEL_GENERAL` | `qwen3.5:4b` | General conversation for the `16gb` profile; best conversational quality on CPU. |
| `TRINAXAI_MODEL_CODE` | `qwen3.5:4b` | Code and technical tasks. |
| `TRINAXAI_MODEL_DEEP` | `qwen3.5:4b` | Complex queries for the `16gb` profile. |
| `TRINAXAI_MODEL_FAST` | `qwen3.5:2b` | Short queries for the `16gb` profile. |
| `TRINAXAI_AUTO_ROUTE` | `1` | Heuristic selection among the models above. |
| `TRINAXAI_LLM` / `TRINAXAI_LLM_HEAVY` | profile-derived | Fallback when the auto-router is disabled. |

Names must match `ollama list`. Download a model manually with `ollama pull NAME`.

## Important operational rules

- Changing the embedding model/dimensions or chunking strategy requires a full reindex. Back up `storage/` first. A plain index reload only refreshes a published generation in memory; it does not rebuild vectors.
- Each synchronized root receives a stable `source_id`. Normal sync only deletes
  missing files from that root; another root in the collection remains intact.
  `TRINAXAI_INDEX_APPEND=1` keeps missing entries even in the selected root.
- Reranking requires `requirements-rerank.txt` and significantly more RAM.
- OCR is optional. Rasterized-PDF OCR also needs compatible Python and system dependencies; PDF extraction still works without OCR.
- CORS is not authentication. Managed FastAPI and Ollama bind to loopback; the
  PWA gateway is the only LAN-facing boundary. Leave
  `TRINAXAI_UNSAFE_BIND_BACKEND=0`, block direct ports 3333/11434, and use a VPN.
- Same-origin `/api/rag` forwards a peer identity signed with the installation
  HMAC secret. `/api/ollama` is a narrow method/path facade, not a generic proxy;
  remote use requires the configured credential and joins the cross-process
  inference lock.
- Protected non-loopback reads require a paired-device token with the exact
  `chat`, `read_private`, or `web` scope, or an administrator credential.
  Indexing, Agent and data-modifying routes need a device the host granted the
  `index`, `agent` or `modify` scope to (an admin credential over the network
  does not count). Model/device management, lifecycle controls and Agent
  auto-approve require verified original loopback regardless of credentials.
- Generate a single-use code with `trinaxai pair start`, inspect devices with
  `trinaxai pair list`, and revoke them from the host. A new PWA claim receives
  the device bearer only in an `HttpOnly; SameSite=Strict` cookie scoped to
  `/api`; the claim JSON contains device metadata, not a bearer. The PWA
  does not persist new device tokens in browser storage. A legacy bearer
  stored in the browser is read only for the explicit `GET /v1/pairing/me`
  migration and removed after a successful response. Legacy CLI bearers
  remain header-only through `X-TrinaxAI-Device-Token`; pairing is device
  capability management, not a multi-user account system.
- File tools remain under registered agent roots. Linux terminal calls require
  networkless bubblewrap; unsupported hosts fail closed unless the operator
  explicitly opts into full user-level host access.
- Web search is opt-in. `TRINAXAI_WEB_SEARCH_PROVIDER=auto` prefers a configured Brave key (`TRINAXAI_BRAVE_SEARCH_API_KEY`), then a SearXNG URL (`TRINAXAI_SEARXNG_URL`), and otherwise uses DuckDuckGo without credentials. Tune `TRINAXAI_WEB_SEARCH_TIMEOUT` and `TRINAXAI_WEB_SEARCH_MAX_RESULTS` when needed.
- The same providers can be managed under **PWA → Settings → Web search**. Managed values are stored only by the backend in `storage/web_search_settings.json` with mode `0600`; GET responses expose readiness booleans, never API keys. Precedence is environment variables, then managed settings, then defaults. Empty key fields preserve an existing key; deletion and reset are explicit actions. SearXNG URLs entered in the PWA must resolve to public HTTP(S) endpoints or the documented local loopback endpoint `http://127.0.0.1:8080`, and cannot contain credentials.

## PWA sounds

**Settings → General → Sound effects** controls every non-speech UI cue. The
choice is stored locally, applies immediately, and survives restarts. When it is
off, the centralized audio manager neither creates an `AudioContext` nor loads
or plays cue audio. Speech recognition and spoken answers remain independent.

**Settings → General → Thinking mode** is allowed by default, but activates
adaptively only for analytical or complex tasks. Greetings and simple questions
skip that phase and answer directly. When Ollama exposes provider-supported
reasoning, TrinaxAI sends it separately from the final answer, shows it in an
accessible disclosure, and stores the message's reasoning and duration in
synced chat history. Models that do not expose a thinking channel continue as
normal and do not show an empty panel. The `tc-thinking-mode` preference is
shared through the existing PWA app-state sync; it is not an environment secret.
The reported duration runs from the first provider thinking delta to the first
final-answer token, or to stream end when no final token arrives.

## Long answers and stream state

Every chat provider reports `stop`, `length`, `cancelled`, or `error` through
the completion metadata. A `length` result, or an unclosed Markdown code fence,
is shown as pending instead of complete; the PWA can continue it and will make
at most `TRINAXAI_MAX_CONTINUATIONS` automatic turns (default `2`). The visible
**Continue** action remains available when that ceiling is reached. Set
`TRINAXAI_MAX_CONTINUATIONS=0` to require manual continuation.

`TRINAXAI_GEN_NUM_CTX_MAX` (default `16384`) is the hard generation-context
ceiling. `TRINAXAI_GEN_NUM_CTX` and `TRINAXAI_GEN_NUM_PREDICT` are calibration
knobs; impossible prompt/output reservations are rejected instead of silently
overflowing the model window. The backend timeout applies to an Ollama read
stall, not to the total time needed for a long stream. The PWA uses a generous
first-token guard, while Search Mode allows up to 15 minutes for dependency,
retrieval, and synthesis work.

## Auto-router and default model

With `TRINAXAI_AUTO_ROUTE=1`, a deterministic local classifier selects the
configured general, code, deep, or fast model from task intent and required
capabilities; it does not make an extra model request. An explicit compatible
model remains authoritative, while unavailable or tool-incompatible choices
fall back to an installed capable model. For the normal `16gb` CPU profile,
`qwen3.5:4b` is the general, code, and deep default; `qwen3.5:2b` is the fast
route. The checked-in benchmark records the measured latency tradeoff.

## Embeddings, retrieval, and indexing

| Variable | Default | Purpose |
|---|---:|---|
| `TRINAXAI_EMBED_PRESET` | profile-derived | `balanced` (0.6B), `quality` (4B), `lite` (`nomic-embed-text`), or `fast` (`all-minilm`). Legacy `max` values migrate to `quality`. |
| `TRINAXAI_EMBED` | preset-derived | Embedding model. |
| `TRINAXAI_EMBED_DIMS` | preset-derived | Dimensions; changing them requires rebuilding the index. |
| `TRINAXAI_EMBED_WORKERS` | profile-derived | Concurrent embedding requests. Lower it when memory is tight. |
| `TRINAXAI_EMBED_BATCH` | profile-derived | Nodes per batch. |
| `TRINAXAI_EMBED_KEEP_ALIVE` | profile-derived | Keeps the embedder warm. |
| `TRINAXAI_CHUNK_SIZE` | mode-derived | Prose chunk size. |
| `TRINAXAI_CHUNK_OVERLAP` | mode-derived | Overlap between chunks. |
| `TRINAXAI_CODE_CHUNK_LINES` | `60` | Target lines for code chunks. AST boundaries remain authoritative when available. |
| `TRINAXAI_SIMILARITY_TOP_K` | profile-derived | Final chunks delivered to the LLM. |
| `TRINAXAI_FUSION_CANDIDATES` | profile-derived | Candidates per retriever before fusion. |
| `TRINAXAI_RETRIEVER_CACHE_MAX_COMBINATIONS` | `32` | LRU limit of active collection combinations. |
| `TRINAXAI_RERANK` | `0` | Enables reranking; requires `requirements-rerank.txt` and significantly more RAM. |
| `TRINAXAI_PERSIST_DIR` | `storage/` | Directory for the persisted index and runtime state. Useful for isolated or disposable backend instances. |
| `TRINAXAI_INDEX_DIR` | repository `local_sources/` | Root scanned by `index.py`; browser imports use managed `local_sources/` roots. Leave it empty to use that local folder. |
| `TRINAXAI_INDEX_APPEND` | `0` | When `1`, files missing from the selected root are not removed from the index. |
| `TRINAXAI_INDEX_BATCH_SIZE` | `100` | Files processed per batch. |
| `TRINAXAI_SOURCE_ID` | root-derived | Stable identity of an independent synchronized root. |
| `TRINAXAI_INDEX_LOCK_TIMEOUT` | `60` | Seconds to wait for the cross-process writer lock. |
| `TRINAXAI_INDEX_TIMEOUT` | `3600` | Timeout of the indexer process launched by the CLI. |
| `TRINAXAI_WATCH_INDEX_TIMEOUT` | `1800` | Timeout of each indexer queued by the watcher. |
| `TRINAXAI_WATCH_RELOAD_TIMEOUT` | `30` | How long the watcher waits for the backend to reload engines after a successful index. |
| `TRINAXAI_WATCH_OUTPUT_MAX_BYTES` | `16384` | Maximum stdout/stderr tail kept per watcher job. |

Changing embeddings, dimensions, or chunking requires a full reindex. A plain index reload only refreshes a published generation in memory; it does not rebuild vectors. Back up `storage/` first. The manifest uses a content hash and a pipeline version; each root has a `source_id`, so synchronizing a second root into the collection does not remove the first. Reindexing one root does not remove a same-named path from another root in the collection. The index and manifest are published as a complete generation with a journal and rollback after an interruption; interrupted or failed jobs do not replace a working generation.

## Web search

| Variable | Default | Effect |
|---|---:|---|
| `TRINAXAI_WEB_SEARCH_PROVIDER` | `auto` | `auto`, `duckduckgo`, `brave`, `searxng`, or `disabled`. |
| `TRINAXAI_BRAVE_SEARCH_API_KEY` | empty | Brave credential; it stays in the backend and is never returned to the browser. |
| `TRINAXAI_SEARXNG_URL` | empty | SearXNG endpoint with JSON search enabled; public HTTP(S) endpoints or the documented local `http://127.0.0.1:8080` loopback endpoint are accepted. |
| `TRINAXAI_WEB_SEARCH_TIMEOUT` | `15` | Search timeout in seconds. |
| `TRINAXAI_WEB_SEARCH_MAX_RESULTS` | `6` | Maximum results, from 1 to 10. |

In `auto`, Brave wins when a key exists, then SearXNG when a URL exists, and
DuckDuckGo is the no-key fallback. Search is explicit: local chat and local RAG
do not send queries to the Internet. SearXNG may use the documented local
`http://127.0.0.1:8080` endpoint (or another validated HTTP loopback endpoint on
port `8080`); this exception applies only to the configured SearXNG provider.
General web page reads still reject credentials and private destinations,
validate redirects, and enforce byte, text, and time limits.

## Files and extraction limits

| Variable | Default |
|---|---:|
| `TRINAXAI_MAX_FILE_BYTES` | 3 MiB |
| `TRINAXAI_DOCUMENT_MAX_FILE_BYTES` | 512 MiB |
| `TRINAXAI_UPLOAD_MAX_FILES` | `2500` |
| `TRINAXAI_UPLOAD_MAX_BYTES` | 2 GiB |
| `TRINAXAI_DOC_EXTRACT_MAX_BYTES` | 128 MiB |
| `TRINAXAI_DOC_EXTRACT_MAX_CHARS` | `120000` |
| `TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES` | 512 MiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES` | 4 GiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES` | `1000` |
| `TRINAXAI_OCR` | `0` |

Large uploads are validated and staged before a background job is returned.
`TRINAXAI_INDEX_STAGE_TIMEOUT` limits silence in one stage and
`TRINAXAI_INDEX_TIMEOUT` limits the whole index job. Cancelled or failed jobs
discard unpublished data and may be retried when their staged source remains.

## Network, TLS, and security

| Variable | Default / example | Notes |
|---|---|---|
| `TRINAXAI_HOST` | `127.0.0.1` | Keeps FastAPI behind the local gateway. |
| `TRINAXAI_UNSAFE_BIND_BACKEND` | `0` | Dangerous escape hatch that allows a non-loopback bind; do not enable it on a shared LAN or the Internet. |
| `TRINAXAI_PORT` | `3333` | FastAPI port. |
| `TRINAXAI_RAG_HTTPS` | `1` | HTTPS for the managed API. |
| `TRINAXAI_CA_FILE` | auto-detected | Explicit CA bundle for verified HTTPS from the CLI; it also detects local mkcert/self-signed roots. |
| `TRINAXAI_CORS_ORIGINS` | local PWA origins | Comma-separated list; avoid `*`. |
| `TRINAXAI_ALLOW_LAN_SYSTEM` | `0` | Obsolete legacy variable; it does not grant host administration over the LAN. |
| `TRINAXAI_ADMIN_TOKEN` | empty | Credential for protected operations; it does not bypass the loopback requirement for host administration. |
| `TRINAXAI_DEVICE_REGISTRY` | `storage/device_pairing.json` | Atomic `0600` registry with devices/scopes and keyed hashes. |
| `TRINAXAI_DEVICE_SECRET_FILE` | `storage/.device_secret` | `0600` key used to hash pairing codes and tokens. |
| `TRINAXAI_DEVICE_TOKEN` | empty | Bearer of a paired CLI; sent as `X-TrinaxAI-Device-Token`. |
| `TRINAXAI_PROXY_SECRET_FILE` | `storage/.proxy_secret` | Private gateway/backend HMAC key, created with mode `0600`. |
| `TRINAXAI_PROXY_TRUSTED_PEERS` | empty | Comma-separated IPs/CIDRs allowed to carry signed HMAC assertions. Leave it empty in native mode; Docker Compose configures its dedicated private subnet. |
| `TRINAXAI_RATE_LIMIT_PER_MINUTE` | `30` | Token-bucket capacity per verified IP/bucket. |
| `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Seconds for an empty bucket to refill to capacity. |
| `TRINAXAI_TLS_VERIFY` | `0` | TLS validation of outbound backend connections. |

CORS is not authentication. Managed FastAPI and Ollama bind to loopback; the PWA gateway is the LAN boundary. Block ports 3333/11434 and use a VPN. Remote private reads require `read_private` or an admin credential; indexing, Agent, and data changes require a device the host granted `index`, `agent`, or `modify`; host administration requires verified loopback origin.

Run `trinaxai pair start` on the host to issue a single-use code. It grants `chat,read_private` by default and can add `web` and, per device, `index`, `agent`, and `modify` (`--scopes chat,read_private,agent`); change them later with `trinaxai pair set ID --scopes ...`. Lifecycle, model/device administration, and Agent auto-approve require loopback even when a token exists. `trinaxai pair list` shows the inventory and `trinaxai pair revoke ID` invalidates a device. A new PWA claim receives the bearer only in an `HttpOnly; SameSite=Strict` cookie scoped to `/api`; the claim JSON contains device metadata, not a bearer. The PWA does not persist new tokens in browser storage. A legacy bearer stored in the browser is read only for the explicit `GET /v1/pairing/me` migration and removed after a successful response; the CLI remains compatible through the `X-TrinaxAI-Device-Token` header. Pairing manages device capabilities, not accounts.

## PWA and proxy

| Variable | Use |
|---|---|
| `TRINAXAI_FRONTEND_MODE` | `serve` uses the production Node gateway; `dev` uses Vite with HMR. |
| `TRINAXAI_FRONTEND_URL` | URL reported/opened by the tools. |
| `TRINAXAI_RAG_TARGET` | Target of the `/api/rag` proxy. |
| `TRINAXAI_OLLAMA_TARGET` | Target of the `/api/ollama` proxy. |
| `TRINAXAI_OLLAMA_PROXY_RATE_LIMIT` | Requests/minute per peer on the Ollama facade. |
| `TRINAXAI_INFERENCE_LOCK_FILE` | Shared gateway/backend scheduler lock. |
| `TRINAXAI_INFERENCE_QUEUE_TIMEOUT` | Maximum wait in the inference queue. |
| `VITE_TRINAXAI_RAG_BASE` | Production RAG base in the browser. |
| `VITE_TRINAXAI_OLLAMA_BASE` | Production Ollama base. |
| `VITE_TRINAXAI_DEV_RAG_BASE` | RAG base during development. |
| `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Ollama base during development. |
| `VITE_TRINAXAI_VISION_MODEL` | Vision model; defaults to `qwen3.5:4b` on 16GB and is downloaded on the first image analysis. |

`/api/rag` signs peer/method/path with the HMAC key and `/api/ollama` publishes a reduced allowlist: it is not a generic proxy. The processes share a lock so chat, RAG, and the agent cannot bypass the queue. Restart after runtime changes and rebuild for `VITE_*` variables.

## Agent

| Variable | Default | Use |
|---|---:|---|
| `TRINAXAI_AGENT_WORKSPACE_ROOTS` | indexed roots + repo | Allowlist of HTTP roots, separated by the OS path separator. |
| `TRINAXAI_AGENT_HTTP_YOLO` | `0` | HTTP auto-approval only on true loopback, if enabled. |
| `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` | `0` | High-risk escape hatch: shell with the user's full permissions. |

File tools resolve symlinks and reject escapes. On Linux the shell requires networkless bubblewrap and leaves only the workspace writable. Without a compatible sandbox it fails closed unless the explicit opt-in above is set.

## Voice

| Variable | Default | Use |
|---|---:|---|
| `TRINAXAI_VOICE_STT_MODEL` | `base` | Local Whisper model. |
| `TRINAXAI_VOICE_DEVICE` | `auto` | `faster-whisper` device, for example `cpu`/`cuda`. |
| `TRINAXAI_VOICE_COMPUTE_TYPE` | `default` | Compute type compatible with the device. |
| `TRINAXAI_VOICE_TTS_ENGINE` | auto-detected | Forces an available TTS backend. |
| `TRINAXAI_VOICE_MAX_AUDIO_BYTES` | 30 MiB | Maximum STT audio. |
| `TRINAXAI_VOICE_TTS_MAX_CHARS` | `1200` | Maximum TTS text. |
| `TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE` | `30` | Reserved by the voice configuration. |
| `TRINAXAI_PIPER_MODEL` | empty | Explicit path to a Piper model. |

The browser Web Speech API remains the preferred path when available.

## Common values

| Setting | Default or template value |
|---|---|
| API / PWA / Ollama ports | `3333` / `3334` / `11434` |
| Profile / performance mode | `16gb` / `fast` |
| Rate limit | token-bucket capacity 30, refilled over 60 seconds, per verified IP/bucket |
| Normal max indexed file | 3 MiB |
| Document/upload limits | 512 MiB per document; 2 GiB upload batch |
| Host-backed chat attachment limit | 512 MiB per file; 4 GiB retained total |
| Temporary extracted text | 120,000 characters |
| Backend / Ollama bind | loopback-only |
| Protected LAN access | matching device scope (`chat`, `read_private`, `web`, and host-granted `index`, `agent`, `modify`); admin token for reads only; host administration remains loopback-only |

## Large-file processing and recoverable failures

Uploads return a job identifier after validation and staging; the HTTP request
does not remain open for extraction and embedding. PDF pages, chunks, and
embeddings are processed in bounded batches. The UI reports persisted stage,
elapsed time, recent activity, pages, chunks, and batches; stages without an
exact denominator are explicitly indeterminate. Stage and total timeouts are
configurable with `TRINAXAI_INDEX_STAGE_TIMEOUT` and
`TRINAXAI_INDEX_TIMEOUT`. Cancellation and failures discard unpublished
index generations and temporary files; eligible jobs can be retried.

Search Mode failures (provider disabled/blocked, timeout, or ungrounded result)
and RAG failures (missing index/model, interrupted SSE, or first-token timeout)
are recoverable: the UI exits its waiting state and keeps the conversation
available for retry. They are not silently replaced with fabricated results.

## Validate the effective setup

```bash
trinaxai config
trinaxai doctor --strict --json
curl -k https://localhost:3333/health
```

If a setting appears ignored, determine whether it is gateway runtime or Vite build-time configuration, restart the managed services, and verify that the expected installation root supplied the `.env` file.
