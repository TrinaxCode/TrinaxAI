# Environment variable inventory

This is the canonical inventory of environment variables understood by TrinaxAI.
Use [`.env.example`](../.env.example) as a starting template and keep only the
overrides that your installation needs. Values in the process environment take
precedence over the repository-root `.env` when services are launched by
`service_manager.py`.

Boolean values generally accept `1`/`0`; security and service settings also
accept `true`/`false`, `yes`/`no`, and `on`/`off` where noted in code. Byte limits
are integer bytes. Variables marked **internal** are set by TrinaxAI scripts for
child processes and normally should not be added to `.env`.

## Runtime, paths, and networking

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_HOME` | auto-detected | Installation root used by the CLI, Vite, and lifecycle scripts. |
| `TRINAXAI_PYTHON` | current Python | Python executable used by service and maintenance scripts. |
| `TRINAXAI_PROFILE` | `16gb` | Hardware preset. Canonical accepted values and aliases live in `trinaxai_core.VALID_PROFILES`. |
| `TRINAXAI_PERFORMANCE_MODE` | `fast` | Runtime tuning: `fast`, `balanced`, or `quality`. |
| `TRINAXAI_HOST` | `127.0.0.1` in the hardened template | API bind address. Keep FastAPI behind the same-host gateway; do not publish it directly. |
| `TRINAXAI_UNSAFE_BIND_BACKEND` | `0` | Explicit high-risk escape hatch that lets the backend honor a non-loopback `TRINAXAI_HOST`. Leave disabled; LAN clients should enter through the authenticated gateway. |
| `TRINAXAI_PORT` | `3333` | API TCP port. |
| `TRINAXAI_RAG_HTTPS` | `1` | Enables managed API TLS when local certificate files exist. |
| `TRINAXAI_CA_FILE` | auto-detected | Explicit CA bundle for verified CLI HTTPS; local mkcert/self-signed roots are discovered automatically. |
| `TRINAXAI_HEALTH_URL` | derived from port/TLS | Health URL used by installers and diagnostics. |
| `TRINAXAI_FRONTEND_URL` | `https://localhost:3334` | Public/local URL reported for the PWA. |
| `TRINAXAI_FRONTEND_MODE` | `preview` | Vite script used by the service manager; `dev` selects HMR. |
| `TRINAXAI_RAG_HOST` | `localhost` | Host used by the legacy standalone CLI client. |
| `TRINAXAI_RAG_URL` | derived from host/port | Full RAG URL override for the legacy standalone CLI client. |
| `TRINAXAI_TLS_VERIFY` | `0` for the legacy standalone client | Verify TLS certificates for supported legacy/backend requests. The packaged CLI TOML defaults `api.verify_tls` to `true`; `--insecure` is explicit. |
| `TRINAXAI_CORS_ORIGINS` | safe local origins | Comma-separated exact browser origins. CORS is not authentication. |
| `TRINAXAI_CORS_ORIGIN_REGEX` | private-LAN regex | Additional FastAPI origin regular expression. Review carefully before widening it. |
| `TRINAXAI_ALLOW_LAN_SYSTEM` | `0` | Enables the legacy private-LAN fallback for system control only when no admin token exists. Prefer scoped device pairing. |
| `TRINAXAI_ADMIN_TOKEN` | empty | Administrator super-credential for protected remote operations. Prefer least-privilege device tokens in browsers and ordinary clients. |
| `TRINAXAI_DEVICE_REGISTRY` | `storage/device_pairing.json` | Atomic mode-0600 registry containing keyed hashes, device metadata/scopes, and short-lived pairing-code hashes. It never stores clear device tokens. |
| `TRINAXAI_DEVICE_SECRET_FILE` | `storage/.device_secret` | Mode-0600 key used to hash pairing codes and device bearer tokens. FastAPI and the PWA gateway must share the same file. |
| `TRINAXAI_DEVICE_TOKEN` | empty | Packaged CLI credential for a paired device, sent as `X-TrinaxAI-Device-Token`. Prefer process-secret storage over shell history or committed config. |
| `TRINAXAI_PROXY_SECRET_FILE` | `storage/.proxy_secret` | Mode-0600 gateway/backend HMAC key shared only by the local processes. It is created automatically when possible. |
| `TRINAXAI_PROXY_SECRET` | empty | Direct HMAC secret override. Prefer the secret file so the value is not copied into service definitions or shell history. |
| `TRINAXAI_PROXY_TRUSTED_PEERS` | empty | Comma-separated IPs/CIDRs allowed as transport peers for signed gateway assertions. Keep empty for native loopback mode; Docker Compose supplies its dedicated private subnet. |
| `TRINAXAI_RATE_LIMIT_PER_MINUTE` | `30` | Capacity of each monotonic token bucket, keyed by verified IP and endpoint bucket. |
| `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Seconds over which an empty backend bucket refills to capacity. |
| `TRINAXAI_OLLAMA_PROXY_RATE_LIMIT` | `30` | Requests per minute and verified peer through the gateway's allowlisted Ollama facade. |
| `TRINAXAI_CERT_PASSPHRASE` | `trinaxai-local` | Passphrase used by Vite for the local PFX certificate. |
| `TRINAXAI_APP_STATE_MAX_BYTES` | `6291456` | Maximum persisted shared PWA state size. |
| `TRINAXAI_CONFIG` | platform config path | Explicit TOML path for the packaged CLI. |
| `TRINAXAI_NO_COLOR` | unset | Disables ANSI color in CLI output when set. |

## Models, generation, and embeddings

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_MODEL_GENERAL` | profile-derived | General conversation model. |
| `TRINAXAI_MODEL_CODE` | profile-derived | Normal code model. |
| `TRINAXAI_MODEL_DEEP` | profile-derived | Complex code/reasoning model. |
| `TRINAXAI_MODEL_FAST` | profile-derived | Low-latency model. |
| `TRINAXAI_LLM` | code model | Model used when automatic routing is disabled. |
| `TRINAXAI_LLM_HEAVY` | deep model | Heavy fallback used when automatic routing is disabled. |
| `TRINAXAI_AUTO_ROUTE` | `1` | Enables task-based model routing. |
| `TRINAXAI_NUM_CTX` | profile-derived | RAG/model context window. |
| `TRINAXAI_AGENT_NUM_CTX` | derived from `TRINAXAI_NUM_CTX` | Context window for TrinaxAI Agent tool-use. Larger than chat so file reads and command output don't overflow and degrade small models; capped for CPU-only boxes. |
| `TRINAXAI_AGENT_TIMEOUT` | `600` | Maximum wall-clock seconds for one HTTP Agent run before cancellation. |
| `TRINAXAI_AGENT_STALL_TIMEOUT` | `120` | Maximum seconds without tokens, tool activity, or pending approval before a run is cancelled as stalled. |
| `TRINAXAI_NUM_THREAD` | `8` | CPU threads requested per Ollama generation. |
| `TRINAXAI_KEEP_ALIVE` | profile-derived | Ollama chat-model residency duration, such as `0s` or `10m`. |
| `TRINAXAI_TIMEOUT` | `300` | Ollama request timeout in seconds. |
| `TRINAXAI_MODEL_MAX_CONCURRENCY` | `1` | Concurrent model tasks; keep low to avoid RAM/VRAM thrashing. |
| `TRINAXAI_INFERENCE_QUEUE_TIMEOUT` | `600` | Seconds FastAPI and the PWA gateway wait for the shared cross-process inference lock. |
| `TRINAXAI_INFERENCE_LOCK_FILE` | `storage/.inference.lock` | Shared atomic lock-directory path used by the gateway. It must match the backend's storage lock when overridden. |
| `TRINAXAI_GEN_NUM_CTX` | task/profile-derived | Context window for the free-form generation pipeline. |
| `TRINAXAI_GEN_NUM_CTX_MAX` | `16384` | Hard cap when generation context grows automatically. |
| `TRINAXAI_GEN_NUM_PREDICT` | task-derived | Fixed generation output-token budget override. |
| `TRINAXAI_GEN_MAX_FIX` | task-derived | Maximum generate/validate/fix passes. |
| `TRINAXAI_GEN_TEMPERATURE_CODE_GEN` | `0.15` | Temperature override for code generation. |
| `TRINAXAI_GEN_TEMPERATURE_CREATIVE` | `0.5` | Temperature override for creative generation. |
| `TRINAXAI_GEN_TEMPERATURE_EXPLAIN` | `0.4` | Temperature override for explanations. |
| `TRINAXAI_GEN_TEMPERATURE_GROUNDED_QA` | `0.0` | Temperature override for grounded RAG answers. |
| `TRINAXAI_GEN_TEMPERATURE_<REGIME>` | regime-derived | General form consumed by the generation preset loader. |
| `TRINAXAI_EMBED_PRESET` | `balanced` | Embedding preset: `balanced`, `lite`, or `fast`. |
| `TRINAXAI_EMBED` | preset-derived | Ollama embedding model. Changing it requires reindexing. |
| `TRINAXAI_EMBED_DIMS` | preset-derived | Embedding vector dimensions. Changing it requires reindexing. |
| `TRINAXAI_EMBED_WORKERS` | profile-derived | Concurrent embedding requests. |
| `TRINAXAI_EMBED_BATCH` | profile-derived | Nodes sent per embedding batch. |
| `TRINAXAI_EMBED_KEEP_ALIVE` | profile-derived | Ollama embedding-model residency duration. |
| `TRINAXAI_AGGRESSIVE_QUANT` | `0` | Enables aggressive quantization/runtime hints. |

Ollama also consumes `OLLAMA_BASE_URL` (backend endpoint), `OLLAMA_HOST`
(server bind address), and `OLLAMA_NUM_GPU` (GPU offload hint).

## Web search

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_WEB_SEARCH_PROVIDER` | `auto` | Search provider: automatic selection, Brave, SearXNG, or disabled. |
| `TRINAXAI_BRAVE_SEARCH_API_KEY` | empty | API key used by the Brave Search provider. |
| `TRINAXAI_SEARXNG_URL` | empty | Base URL of a local or remote SearXNG instance. |
| `TRINAXAI_WEB_SEARCH_TIMEOUT` | `15` | Search request timeout in seconds. |
| `TRINAXAI_WEB_SEARCH_MAX_RESULTS` | `6` | Maximum results returned per search. |
| `TRINAXAI_WEB_SEARCH_CACHE_SECONDS` | `300` | In-memory result-cache lifetime. |

## Retrieval, indexing, and persisted files

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_INDEX_DIR` | parent of repository | Directory indexed recursively. |
| `TRINAXAI_COLLECTION_ID` | `default` | Collection identifier passed to the indexer. |
| `TRINAXAI_COLLECTION_NAME` | `General` | Human-readable collection name passed to the indexer. |
| `TRINAXAI_DEFAULT_COLLECTION_ID` | `default` | Default collection accepted by the pure runtime validator. |
| `TRINAXAI_INDEX_APPEND` | `0` | Keeps entries whose source files disappeared when enabled. |
| `TRINAXAI_INDEX_BATCH_SIZE` | `100` | Files loaded per indexing batch. |
| `TRINAXAI_INDEX_NODE_BATCH_SIZE` | `32` | Nodes embedded per bounded index-construction batch. |
| `TRINAXAI_INDEX_STAGE_TIMEOUT` | `900` | Maximum seconds an index stage may run without structured progress before cancellation. |
| `TRINAXAI_PROGRESS` | structured stdout marker | **Internal:** prefix emitted by the indexer and parsed by its supervisor; it is not a user setting. |
| `TRINAXAI_INDEX_LOAD_WORKERS` | up to `8` | Concurrent source-file loaders. |
| `TRINAXAI_INDEX_LOCK_TIMEOUT` | `3600` | Seconds to wait for the cross-process index writer lock. |
| `TRINAXAI_INDEX_TIMEOUT` | `3600` | Seconds the packaged CLI waits for its spawned indexer process before terminating the process group. |
| `TRINAXAI_WATCH_INDEX_TIMEOUT` | `1800` | Seconds the watcher allows one queued indexer subprocess before terminating its process group and reporting the failure. |
| `TRINAXAI_WATCH_RELOAD_TIMEOUT` | `30` | Seconds the watcher waits for the RAG backend to reload engines after a successful index job before treating the reload as timed out. |
| `TRINAXAI_WATCH_OUTPUT_MAX_BYTES` | `16384` | Maximum trailing stdout/stderr bytes retained for one watcher index job. |
| `TRINAXAI_PROJECT_ROOT` | CLI-selected path | **Internal:** project root passed from `trinaxai index` to the indexer. |
| `TRINAXAI_SOURCE_ID` | canonical-root-derived | Stable identity for one independently synchronized source root. Set explicitly only when identity must survive a root-path move. |
| `TRINAXAI_CHUNK_SIZE` | mode/profile-derived | Prose chunk size in tokens. |
| `TRINAXAI_CHUNK_OVERLAP` | mode/profile-derived | Prose overlap in tokens. |
| `TRINAXAI_CODE_CHUNK_LINES` | `60` | Target lines per code chunk. |
| `TRINAXAI_CODE_CHUNK_LINES_OVERLAP` | mode-derived | Overlap between code chunks. |
| `TRINAXAI_CODE_MAX_CHARS` | `2000` | Maximum preferred code-chunk characters. |
| `TRINAXAI_SIMILARITY_TOP_K` | profile-derived | Final retrieved chunks supplied to the model. |
| `TRINAXAI_FUSION_CANDIDATES` | profile-derived | Candidate count per retriever before fusion. |
| `TRINAXAI_RETRIEVAL_CACHE_SECONDS` | mode-derived | In-memory retrieval-cache lifetime. `0` disables it. |
| `TRINAXAI_RAG_MIN_SCORE` | `0.05` | Minimum top retrieval score accepted by explicit Knowledge mode; lower-only results return the deterministic no-relevant-information response. |
| `TRINAXAI_SOURCES_CACHE_SECONDS` | mode-derived | Knowledge-source listing cache lifetime. `0` disables it. |
| `TRINAXAI_RETRIEVER_CACHE_MAX_COMBINATIONS` | `32` | LRU bound for distinct active-collection retriever combinations; prevents unbounded combination growth. |
| `TRINAXAI_RERANK` | `0` | Enables optional cross-encoder reranking. |
| `TRINAXAI_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model used for reranking. |
| `TRINAXAI_RERANK_TOP_N` | top-k value | Results retained by the reranker. |
| `TRINAXAI_MAX_FILE_BYTES` | `3145728` | Normal indexed-file size limit. |
| `TRINAXAI_DOCUMENT_MAX_FILE_BYTES` | `536870912` | Size limit for supported large document containers. |
| `TRINAXAI_UPLOAD_MAX_FILES` | `2500` | Maximum files in one upload/import operation. |
| `TRINAXAI_UPLOAD_MAX_BYTES` | `2147483648` | Maximum total bytes in one upload/import operation. |
| `TRINAXAI_DOCUMENT_MAX_CONCURRENCY` | `1` | Concurrent document extraction tasks. |
| `TRINAXAI_DOC_EXTRACT_MAX_BYTES` | `134217728` | Maximum document size accepted by text extraction. |
| `TRINAXAI_DOC_EXTRACT_MAX_CHARS` | `120000` | Maximum extracted characters returned/stored per document. |
| `TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES` | `536870912` | Maximum retained chat attachment size. |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES` | `4294967296` | Total retained chat-attachment quota. |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES` | `1000` | Retained chat-attachment count quota. |
| `TRINAXAI_OCR` | `0` | Enables optional OCR for low-text scanned PDFs. |

The indexer recognizes source code, common prose/data formats, PDF and Office
documents, HTML, EPUB, email, subtitles, calendars, contacts, and notebooks.
Files with uncommon extensions are also indexed when their bytes are safely
detectable as text; opaque binary/media files are skipped instead of embedded as
garbage.

## Persistent memory

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_MEMORY_MAX_ENTRIES` | `1000` | Maximum saved memory entries. |
| `TRINAXAI_MEMORY_MAX_FILE_BYTES` | `4194304` | Maximum serialized memory-store size. |
| `TRINAXAI_MEMORY_TEXT_MAX_CHARS` | `20000` | Maximum characters in one memory entry. |
| `TRINAXAI_MEMORY_MAX_TAGS` | `50` | Maximum tags on one memory entry. |
| `TRINAXAI_MEMORY_TAG_MAX_CHARS` | `100` | Maximum characters in one memory tag. |
| `TRINAXAI_MEMORY_SUMMARY_MAX_CHARS` | `50000` | Maximum input used to refresh the human-facing memory overview. The global overview is not injected into turns. |

## Voice

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_VOICE_STT_MODEL` | `base` | Whisper model used for local speech-to-text. |
| `TRINAXAI_VOICE_DEVICE` | `auto` | `faster-whisper` execution device, for example `cpu` or `cuda`. |
| `TRINAXAI_VOICE_COMPUTE_TYPE` | `default` | `faster-whisper` compute type. Use only a value supported by the selected device/runtime. |
| `TRINAXAI_VOICE_TTS_ENGINE` | auto-detected | Forces a supported local text-to-speech backend. |
| `TRINAXAI_VOICE_MAX_AUDIO_BYTES` | `31457280` | Maximum uploaded STT audio size. |
| `TRINAXAI_VOICE_TTS_MAX_CHARS` | `1200` | Maximum text accepted by one TTS request. |
| `TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE` | `30` | Voice rate-limit configuration. |
| `TRINAXAI_VOICE_MAX_CONCURRENCY` | `1` | Concurrent voice jobs. |
| `TRINAXAI_PIPER_MODEL` | auto-detected | Explicit Piper model path. |
| `TRINAXAI_COQUI_MODEL` | `tts_models/es/mai/tacotron2-DDC` | Coqui model identifier. |

## Agent isolation

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_AGENT_WORKSPACE_ROOTS` | configured indexing roots, then repository | Platform-path-separator-delimited allowlist for HTTP-agent workspaces. Filesystem roots are rejected. |
| `TRINAXAI_AGENT_HTTP_YOLO` | `0` | Enables HTTP auto-approval after the caller also proves `agent_yolo`; with the normal remote gate disabled, this remains loopback-only. |
| `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` | `0` | Explicit high-risk compatibility escape hatch when an OS command sandbox is unavailable. With the default `0`, terminal execution fails closed. |

File tools resolve symlinks and reject paths outside the selected workspace.
On Linux, terminal commands require bubblewrap, run without network access, and
see the workspace as the only writable host tree. On hosts without supported
isolation, terminal execution is disabled unless the operator explicitly opts
into full user-level host access with the variable above.

## PWA and Vite

`VITE_*` variables are embedded at frontend build time; rebuild the PWA after
changing them. Non-`VITE_*` proxy targets are read by the Vite server at runtime.

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_RAG_TARGET` | `http://127.0.0.1:3333` | Server-side target for `/api/rag`. |
| `TRINAXAI_OLLAMA_TARGET` | `http://127.0.0.1:11434` | Server-side target for `/api/ollama`. |
| `VITE_TRINAXAI_RAG_TARGET` | RAG target fallback | Legacy/build-time RAG proxy target fallback. |
| `VITE_TRINAXAI_RAG_BASE` | `/api/rag` | Production browser RAG base. |
| `VITE_TRINAXAI_OLLAMA_BASE` | `/api/ollama` | Production browser Ollama base. |
| `VITE_TRINAXAI_DEV_RAG_BASE` | `/api/rag` | Development browser RAG base. |
| `VITE_TRINAXAI_DEV_OLLAMA_BASE` | `/api/ollama` | Development browser Ollama base. |
| `VITE_TRINAXAI_INDEX_DIR` | empty (server-selected project root) | Optional initial index-directory hint displayed by the PWA. |
| `VITE_TRINAXAI_REPO_URL` | project repository | Repository link displayed by the PWA. |
| `VITE_TRINAXAI_DOCS_URL` | repository README | Documentation link displayed by the PWA. |
| `VITE_TRINAXAI_VISION_MODEL` | `qwen3.5:4b` | Model used for OCR, screenshots, documents, and general image analysis; downloaded on first image analysis if missing. |
| `VITE_TRINAXAI_KEEP_ALIVE` | `10m` | Direct-chat Ollama keep-alive sent by the browser. |

## Install, update, backup, and lifecycle controls

These variables are command-scoped automation switches. Set them only for the
installer or maintenance command that consumes them; they do not tune the RAG
runtime.

| Variable | Default | Purpose |
|---|---|---|
| `TRINAXAI_INTERACTIVE` | `1` | Allows optional prompts in POSIX install/update/uninstall scripts. |
| `TRINAXAI_NONINTERACTIVE` | `0` | Suppresses optional prompts when enabled. |
| `TRINAXAI_INSTALL_MODELS` | `1` | Downloads configured models during installation. |
| `TRINAXAI_INSTALL_VISION` | `1` | Compatibility switch; vision models now download on first image analysis instead of during installation. |
| `TRINAXAI_ENABLE_AUTOSTART` | `1` | Enables boot/login autostart during installation. |
| `TRINAXAI_ENABLE_AUTO_UPDATE` | `1` | Installs the scheduled **check-only** release-availability task; it does not modify the installation. |
| `TRINAXAI_START_NOW` | `1` | Starts TrinaxAI when installation completes. |
| `TRINAXAI_BACKUP_DIR` | `./backups` | Destination used by backup/update scripts. |
| `TRINAXAI_BACKUP_QUIESCE` | `1` | Pauses the API while creating a backup; the archive also takes the shared index lock. Disable only for an externally quiesced snapshot. |
| `TRINAXAI_UPDATE_BACKUP` | `1` | Creates a pre-update backup. |
| `TRINAXAI_UPDATE_PULL` | `1` | Pulls Git changes during update. |
| `TRINAXAI_UPDATE_MODELS` | auto/prompted | Pulls configured Ollama models when enabled. |
| `TRINAXAI_UPDATE_REMOVE_MODELS` | `0` | Removes configured models before pulling replacements. |
| `TRINAXAI_UPDATE_REPAIR_OLLAMA` | `0` | Reinstalls or repairs Ollama during update. |
| `TRINAXAI_UPDATE_RESTART` | auto/prompted | Restarts services after update when enabled. |
| `TRINAXAI_UPDATE_AUDIT` | `1` | Runs the post-update readiness audit. |
| `TRINAXAI_UPDATE_ROOT` | script directory | **Internal:** installation root passed to the automatic updater. |
| `TRINAXAI_PRIVILEGED_WRAPPER` | unset | **Internal:** prevents recursion when a sudoers lifecycle wrapper invokes the manager. |

## Validation

```bash
trinaxai config
trinaxai doctor
curl -k https://localhost:3333/health
```

Changing embedding model/dimensions or chunking behavior requires a full
reindex. Never commit `.env`, tokens, local certificates, `storage/`, or
`local_sources/`.
