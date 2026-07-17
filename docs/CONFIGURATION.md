# TrinaxAI Configuration Reference

TrinaxAI reads environment variables and the repository-root `.env` file. Start with:

```bash
cp .env.example .env
```

Never commit `.env`, certificates, or tokens. [`.env.example`](../.env.example) is the executable template and source of current example values.
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
| Hardware | `TRINAXAI_PROFILE` (`8gb`, `16gb`, `max`, `ultra` installers; `4gb` is a low-resource runtime alias), `TRINAXAI_PERFORMANCE_MODE` (`fast`, `balanced`, `quality`) |
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

- Choose profiles by available memory, not installed memory. Reduce model size, context, and embedding concurrency if the OS starts swapping.
- Changing the embedding model/dimensions or chunking strategy requires a full reindex. Back up `storage/` first.
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
- Protected non-loopback requests require either a paired-device token with the
  exact route scope or the administrator super-credential. Pairing defaults to
  `chat,read_private`; app state, attachments, sources, memory, collections,
  indexing/system and agent routes remain protected, including reads.
- Generate a single-use code with `trinaxai pair start`, inspect devices with
  `trinaxai pair list`, and revoke them from the host. The PWA stores the bearer
  only in `sessionStorage`; `storage/device_pairing.json` and
  `storage/.device_secret` must remain mode `0600`. Pairing is device capability
  management, not a multi-user account system.
- File tools remain under registered agent roots. Linux terminal calls require
  networkless bubblewrap; unsupported hosts fail closed unless the operator
  explicitly opts into full user-level host access.
- Web search is opt-in. `TRINAXAI_WEB_SEARCH_PROVIDER=auto` prefers a configured Brave key (`TRINAXAI_BRAVE_SEARCH_API_KEY`), then a SearXNG URL (`TRINAXAI_SEARXNG_URL`), and otherwise uses DuckDuckGo without credentials. Tune `TRINAXAI_WEB_SEARCH_TIMEOUT` and `TRINAXAI_WEB_SEARCH_MAX_RESULTS` when needed.

## PWA sounds

**Settings → General → Sound effects** controls every non-speech UI cue. The
choice is stored locally, applies immediately, and survives restarts. When it is
off, the centralized audio manager neither creates an `AudioContext` nor loads
or plays cue audio. Speech recognition and spoken answers remain independent.

## Auto-router and default model

With `TRINAXAI_AUTO_ROUTE=1`, a deterministic local classifier selects the
configured general, code, deep, or fast model from task intent and required
capabilities; it does not make an extra model request. An explicit compatible
model remains authoritative, while unavailable or tool-incompatible choices
fall back to an installed capable model. For the normal `16gb` profile,
`granite4:3b` is the general default because the checked-in benchmark shows the
best latency/quality balance; `qwen3.5:4b` remains the deeper reasoning model.

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
| Protected LAN use | requires a matching paired-device scope or admin token |

## Large-file processing and recoverable failures

Uploads return a job identifier after validation and staging; the HTTP request
does not remain open for extraction and embedding. PDF pages, chunks, and
embeddings are processed in bounded batches. The UI reports persisted stage,
elapsed time, recent activity, pages, chunks, and batches; stages without an
exact denominator are explicitly indeterminate. Stage and total timeouts are
configurable with `TRINAXAI_INDEX_STAGE_TIMEOUT` and
`TRINAXAI_INDEX_TOTAL_TIMEOUT`. Cancellation and failures discard unpublished
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

If a setting appears ignored, determine whether it is runtime or Vite build-time configuration, restart the managed services, and verify that the expected installation root supplied the `.env` file.
