<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · ⚙️ Configuration
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
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
| Thinking | `TRINAXAI_THINKING_MODE` (backend fallback when a client omits `think`) |
| Models | `TRINAXAI_MODEL_GENERAL`, `TRINAXAI_MODEL_CODE`, `TRINAXAI_MODEL_DEEP`, `TRINAXAI_MODEL_FAST`, `TRINAXAI_AUTO_ROUTE` |
| Ollama | `OLLAMA_BASE_URL`, `TRINAXAI_NUM_CTX`, `TRINAXAI_NUM_THREAD`, `TRINAXAI_KEEP_ALIVE`, `TRINAXAI_TIMEOUT` |
| Embeddings | `TRINAXAI_EMBED_PRESET`, `TRINAXAI_EMBED`, `TRINAXAI_EMBED_DIMS`, `TRINAXAI_EMBED_WORKERS`, `TRINAXAI_EMBED_BATCH`, `TRINAXAI_EMBED_KEEP_ALIVE` |
| Retrieval | `TRINAXAI_SIMILARITY_TOP_K`, fusion/rerank settings, retrieval TTL and the bounded retriever-combination LRU |
| Indexing | `TRINAXAI_INDEX_DIR`, `TRINAXAI_SOURCE_ID`, `TRINAXAI_INDEX_APPEND`, lock/timeout, chunk and upload limits |
| Network | `TRINAXAI_HOST`, `TRINAXAI_PORT`, `TRINAXAI_RAG_HTTPS`, `TRINAXAI_CORS_ORIGINS` |
| Security | Admin/device credentials, pairing registry/secret, gateway HMAC, agent roots/isolation, rate limits and unsafe escape hatches |
| PWA proxy | Loopback targets, Ollama allowlist/rate limit, shared inference lock/queue, `VITE_TRINAXAI_*` bases and models |
| Voice | `TRINAXAI_VOICE_STT_MODEL`, faster-whisper device/compute type, TTS engine, audio/text limits |

## Important operational rules

- The backend detects CPU model/cores, RAM, GPU vendor/VRAM, and persists the result in `storage/hardware_profile.json`. Leave `TRINAXAI_PROFILE` unset for automatic selection; use it only as an explicit override.
- Model recommendations also consider GPU VRAM: dedicated GPU memory gets GPU-fit models, while large-RAM/weak-GPU systems stay CPU/RAM-oriented.
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
  `chat`, `read_private`, or `web` scope, or an administrator credential. Host
  mutations, indexing, Agent routes, model/device management, and lifecycle
  controls require verified original loopback regardless of credentials.
- Generate a single-use code with `trinaxai pair start`, inspect devices with
  `trinaxai pair list`, and revoke them from the host. A new PWA claim receives
  the device bearer only in an `HttpOnly; SameSite=Strict` cookie scoped to
  `/api/rag`; the claim JSON contains device metadata, not a bearer. The PWA
  does not persist new device tokens in browser storage. Legacy CLI bearers
  remain header-only through `X-TrinaxAI-Device-Token`; pairing is device
  capability management,
  not a multi-user account system.
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

| Variable | Default | Effect |
|---|---:|---|
| `TRINAXAI_EMBED_PRESET` | profile-derived | Selects the `balanced`, `quality`, `lite`, or `fast` embedding preset. Legacy `max` values migrate to `quality`. |
| `TRINAXAI_EMBED` / `TRINAXAI_EMBED_DIMS` | preset-derived | Embedding model and vector dimension; changing either requires a full reindex. |
| `TRINAXAI_EMBED_WORKERS` / `TRINAXAI_EMBED_BATCH` | profile-derived | Concurrency and batch size for embedding requests. Lower them when memory is tight. |
| `TRINAXAI_EMBED_KEEP_ALIVE` | profile-derived | How long Ollama keeps the embedder loaded between batches. |
| `TRINAXAI_CHUNK_SIZE` / `TRINAXAI_CHUNK_OVERLAP` | mode-derived | Prose chunk size and overlap. |
| `TRINAXAI_CODE_CHUNK_LINES` | `60` | Target lines for code chunks. AST boundaries remain authoritative when available. |
| `TRINAXAI_SIMILARITY_TOP_K` / `TRINAXAI_FUSION_CANDIDATES` | profile-derived | Final results and candidate pool for hybrid retrieval. |
| `TRINAXAI_RERANK` | `0` | Enables the optional cross-encoder; install `requirements-rerank.txt` first. |
| `TRINAXAI_PERSIST_DIR` | `storage/` | Directory for the persisted index and runtime state. Useful for isolated or disposable backend instances. |
| `TRINAXAI_INDEX_DIR` | repository `local_sources/` | Root scanned by `index.py`; browser imports use managed `local_sources/` roots. |
| `TRINAXAI_INDEX_APPEND` | `0` | Keeps entries for files missing from the selected root when set to `1`. |

Each synchronized root has a stable `source_id`. Reindexing one root does not
remove a same-named path from another root in the collection. The index is
published as a complete generation; interrupted or failed jobs do not replace a
working generation.

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

| Setting | Default |
|---|---:|
| Normal indexed file | 3 MiB (`TRINAXAI_MAX_FILE_BYTES`) |
| Large document container | 512 MiB (`TRINAXAI_DOCUMENT_MAX_FILE_BYTES`) |
| Browser upload batch | 2 GiB / 2,500 files |
| Temporary document extraction | 128 MiB / 120,000 characters |
| Host-backed chat attachment | 512 MiB per file / 4 GiB total / 1,000 files |
| OCR | Disabled (`TRINAXAI_OCR=0`) |

Large uploads are validated and staged before a background job is returned.
`TRINAXAI_INDEX_STAGE_TIMEOUT` limits silence in one stage and
`TRINAXAI_INDEX_TIMEOUT` limits the whole index job. Cancelled or failed jobs
discard unpublished data and may be retried when their staged source remains.

## Network, PWA proxy, agent, and voice

- Keep `TRINAXAI_HOST=127.0.0.1`, `TRINAXAI_UNSAFE_BIND_BACKEND=0`, and
  Ollama on loopback. Expose the gateway on port `3334`; do not open `3333` or
  `11434` to the LAN. CORS is not authentication.
- `TRINAXAI_RAG_TARGET` and `TRINAXAI_OLLAMA_TARGET` are server-side gateway
  targets. `VITE_TRINAXAI_*` values are build-time browser bases, so rebuild
  after changing them. `/api/ollama` is a fixed allowlist, not a generic proxy.
- `TRINAXAI_AGENT_WORKSPACE_ROOTS` limits HTTP workspaces. File tools reject
  symlink/path escapes, Linux terminal tools require networkless bubblewrap,
  and `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1` is an explicit high-risk
  escape hatch.
- `TRINAXAI_VOICE_STT_MODEL`, `TRINAXAI_VOICE_DEVICE`,
  `TRINAXAI_VOICE_COMPUTE_TYPE`, `TRINAXAI_VOICE_TTS_ENGINE`, and the audio/text
  limits configure the optional local voice backend. The browser Web Speech API
  remains the preferred path when available.

Use `trinaxai pair start` for a device token. It grants `chat,read_private` by
default and can add only `web`; indexing, Agent, lifecycle, and host
administration still require verified loopback.

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
| Protected LAN reads | matching `chat`, `read_private`, or `web` device scope, or admin token; host administration remains loopback-only |

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
