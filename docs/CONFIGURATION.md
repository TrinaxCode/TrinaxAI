# TrinaxAI Configuration Reference

TrinaxAI reads environment variables and the repository-root `.env` file. Start with:

```bash
cp .env.example .env
```

Never commit `.env`, certificates, or tokens. [`.env.example`](../.env.example) is the executable template and source of current example values.

## Loading and precedence

- The backend loads the root `.env`.
- `service_manager.py` passes the environment to the API, Ollama, and the PWA.
- `VITE_*` values are compiled into the frontend by `npm run build`; rebuild after changing them.
- PWA `tc-*` preferences can override frontend model choices without changing `.env`.
- The CLI uses a separate TOML file; see [CLI_REFERENCE.md](CLI_REFERENCE.md).

## Main groups

| Group | Variables |
|---|---|
| Hardware | `TRINAXAI_PROFILE` (`4gb`, `8gb`, `16gb`, `max`, `ultra`), `TRINAXAI_PERFORMANCE_MODE` (`fast`, `balanced`, `quality`) |
| Models | `TRINAXAI_MODEL_GENERAL`, `TRINAXAI_MODEL_CODE`, `TRINAXAI_MODEL_DEEP`, `TRINAXAI_MODEL_FAST`, `TRINAXAI_AUTO_ROUTE` |
| Ollama | `OLLAMA_BASE_URL`, `TRINAXAI_NUM_CTX`, `TRINAXAI_NUM_THREAD`, `TRINAXAI_KEEP_ALIVE`, `TRINAXAI_TIMEOUT` |
| Embeddings | `TRINAXAI_EMBED_PRESET`, `TRINAXAI_EMBED`, `TRINAXAI_EMBED_DIMS`, `TRINAXAI_EMBED_WORKERS`, `TRINAXAI_EMBED_BATCH`, `TRINAXAI_EMBED_KEEP_ALIVE` |
| Retrieval | `TRINAXAI_SIMILARITY_TOP_K`, `TRINAXAI_FUSION_CANDIDATES`, `TRINAXAI_RERANK`, `TRINAXAI_RERANK_MODEL`, `TRINAXAI_RERANK_TOP_N` |
| Indexing | `TRINAXAI_INDEX_DIR`, `TRINAXAI_INDEX_APPEND`, `TRINAXAI_INDEX_BATCH_SIZE`, chunk and upload limits |
| Network | `TRINAXAI_HOST`, `TRINAXAI_PORT`, `TRINAXAI_RAG_HTTPS`, `TRINAXAI_CORS_ORIGINS` |
| Security | `TRINAXAI_ALLOW_LAN_SYSTEM`, `TRINAXAI_ADMIN_TOKEN`, rate-limit settings |
| PWA proxy | `TRINAXAI_RAG_TARGET`, `TRINAXAI_OLLAMA_TARGET`, `VITE_TRINAXAI_*` bases and models |
| Voice | `TRINAXAI_VOICE_STT_MODEL`, `TRINAXAI_VOICE_TTS_ENGINE`, audio/text limits, `TRINAXAI_PIPER_MODEL` |

## Important operational rules

- Choose profiles by available memory, not installed memory. Reduce model size, context, and embedding concurrency if the OS starts swapping.
- Changing the embedding model/dimensions or chunking strategy requires a full reindex. Back up `storage/` first.
- `TRINAXAI_INDEX_APPEND=1` keeps entries for deleted source files; leave it off for source/index parity.
- Reranking requires `requirements-rerank.txt` and significantly more RAM.
- OCR is optional and requires Tesseract plus its Python/PDF conversion dependencies.
- CORS is not authentication. Keep ports `3333`, `3334`, and `11434` off the public Internet; use a VPN or authenticated reverse proxy.
- Same-origin browser paths (`/api/rag`, `/api/ollama`) are the normal deployment. The Vite server proxies them to the local services.

## Common values

| Setting | Default or template value |
|---|---|
| API / PWA / Ollama ports | `3333` / `3334` / `11434` |
| Profile / performance mode | `16gb` / `fast` |
| Rate limit | 30 requests per 60 seconds, per IP and bucket |
| Normal max indexed file | 3 MiB |
| Document/upload limits | 250 MiB per document; 512 MiB upload batch |
| Host-backed chat attachment limit | 250 MiB per file |
| Temporary extracted text | 120,000 characters |
| LAN system control | disabled |

## Validate the effective setup

```bash
trinaxai config
trinaxai doctor
curl -k https://localhost:3333/health
```

If a setting appears ignored, determine whether it is runtime or Vite build-time configuration, restart the managed services, and verify that the expected installation root supplied the `.env` file.
