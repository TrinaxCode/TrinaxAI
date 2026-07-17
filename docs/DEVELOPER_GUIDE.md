# TrinaxAI Developer Guide

## Setup

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh           # or install.ps1 on Windows
source .venv/bin/activate
pip install -r requirements.txt
cd chat-pwa && npm install && cd ..
```

For the reranker (optional but recommended for accuracy):
```bash
pip install -r requirements-rerank.txt
```

Copy `.env.example` to `.env` and edit as needed:
```bash
cp .env.example .env
```

---

## Project Structure

```
.
├── config.py              # Central configuration (models, profiles, chunking)
├── rag_api.py             # Backward-compatible API entry point
├── index.py               # Document indexer (AST-aware, incremental)
├── app/
│   ├── main.py            # Canonical FastAPI application factory
│   ├── routes/            # Small HTTP routers grouped by domain
│   ├── schemas/           # Shared Pydantic request/response contracts
│   ├── services/          # Chat, sources, memory, indexing, system, etc.
│   └── security/          # Authorization and rate limiting
├── trinaxai_cli/          # Terminal interface (modular, subcommands)
├── trinaxai_cli.py        # Legacy standalone CLI (deprecated)
├── service_manager.py     # Cross-platform service supervisor
├── test_system.py         # Automated health checks
│
├── chat-pwa/              # React PWA frontend
│   ├── src/components/    # React UI components
│   ├── src/lib/           # API layer, config, shared state, user profile
│   ├── src/hooks/         # useChatHistory and useStreamChat
│   ├── src/i18n/          # Spanish/English translations
│   └── vite.config.ts     # Build config, PWA plugin, API proxy
│
├── scripts/               # Release tooling (public_readiness.py)
├── docs/                  # Documentation (API ref, architecture, dev guide)
├── storage/               # Persisted indexes, manifest, collections
├── chat-pwa/certs/        # Local HTTPS certificates (generated locally)
└── .github/               # CI, PR template, issue templates
```

---

## Coding Conventions

### Python

- Use `pathlib.Path` for new code (existing `os.path` code may remain)
- Docstrings in Google or NumPy style, either Spanish or English (project convention: bilingual)
- Import order: stdlib → third-party → local
- Type hints encouraged but not strictly enforced
- Avoid bare `except Exception: pass` — at minimum log the exception

### TypeScript (chat-pwa)

- Strict TypeScript (`strict: true` in tsconfig.json)
- Use `const` for non-reassigned bindings
- Components are functional with hooks, no class components (except `ErrorBoundary`)
- i18n: add new strings to `translations.ts` in both `es` and `en`
- CSS: Tailwind utilities plus component-local CSS next to complex components

### Shell Scripts

- Use `#!/usr/bin/env bash` shebang
- Include `set -euo pipefail` 
- Add `usage()` function and `--help` flag
- Document environment variables used

---

## Adding a New Model

1. Add the model constant in `config.py`:
   ```python
   MODEL_MY_NEW = os.getenv("TRINAXAI_MODEL_MY_NEW", "my-model:latest")
   ```
2. Add to `MODEL_FLEET` list
3. Update `route_model()` if the model needs special routing heuristics
4. Pull the model: `ollama pull my-model:latest`
5. Add to the auto-routing table in `Docs.tsx` models section

---

## Adding a New API Endpoint

1. Add business logic to the matching module in `app/services/`.
2. Register it in the matching `app/routes/*.py` router:
   ```python
   @router.get("/v1/my-feature")
   async def my_feature(request: Request):
       # Classify the data explicitly. Private reads need authorize_system
       # (prefer a router dependency); only intentionally public telemetry such
       # as health/resources should omit authorization.
       return {"ok": True}
   ```

   For system endpoints that modify state:
   ```python
   @router.post("/system/my-action")
   async def my_action(request: Request):
       authorize_system(request)
       # ...
       return {"ok": True}
   ```

3. Add or update the Pydantic contract in `app/schemas/`.
4. Add a route-contract test and update `docs/API_REFERENCE.md`.
5. If the PWA needs it, add the fetch function in `chat-pwa/src/lib/api.ts`.

---

## Adding i18n Strings

1. Open `chat-pwa/src/i18n/translations.ts`
2. Add keys to both `es` and `en` objects
3. Use `const { t, lang } = useI18n()` in components
4. Call `t('myKey')` or `isEs ? 'Texto' : 'Text'` for inline

---

## Testing

### Health Check
```bash
python test_system.py --verbose
```
Verifies: Ollama running, embedding works, RAG query works.

### Pre-Release Audit
```bash
python scripts/public_readiness.py
```
Checks: required files, hardcoded paths, i18n coverage, Python compile.

### CI
`.github/workflows/ci.yml` runs on push/PR:
- Python syntax check (`python -m compileall`)
- TypeScript type check (`npx tsc --noEmit`)
- Frontend build (`npm run build`)

---

## Debugging Tips

### RAG API not starting
```bash
# Check port
lsof -i :3333

# Run directly with verbose output
python -c "import uvicorn; uvicorn.run('rag_api:app', host='0.0.0.0', port=3333, reload=True)"
```

### Ollama not responding
```bash
# Check if running
curl http://localhost:11434/api/tags

# Check logs
journalctl -u ollama -f  # Linux
```

### PWA not loading
```bash
cd chat-pwa
npx vite --host 0.0.0.0 --port 3334
# Check console for errors, CORS issues, or cert problems
```

### Indexing issues
```bash
# Full reindex (nuclear option)
rm -rf storage/docstore.json storage/index_store.json storage/manifest.json
python index.py
curl -k -X POST http://localhost:3333/system/reload
```

---

## PWA Development

### Dev Server
The Vite dev server runs on `https://localhost:3334` with hot module replacement. It proxies `/api/rag` → `localhost:3333` and `/api/ollama` → `localhost:11434`.

```bash
cd chat-pwa
npm run dev
```

### Service Worker Caching
The PWA uses `vite-plugin-pwa` with `registerType: 'prompt'`, so an update waits
for the user instead of interrupting a stream or draft. During development, the
service worker is **not** registered to avoid caching issues. To test PWA features:

```bash
npm run build
npm run preview   # Serves production build with service worker
```

### Debugging the Frontend
- **React DevTools**: Install the browser extension for component inspection.
- **Network tab**: All API calls go through the Vite proxy — check the Network tab for `/api/rag/*` and `/api/ollama/*`.
- **IndexedDB**: File attachments are stored in `trinaxai-chat-files` — inspect via DevTools > Application > IndexedDB.
- **localStorage**: Chat history, settings, and shared state are in localStorage — check Application > Local Storage.
- **Service Worker**: Use Application > Service Workers to unregister or update.
- **Streaming SSE**: Events appear in the Network tab as `text/event-stream` responses.

### Code Splitting
Heavy dependencies are split into separate chunks (configured in `vite.config.ts`):
- `vendor-react` — React + ReactDOM
- `vendor-framer` — Framer Motion
- `vendor-markdown` — react-markdown + rehype-sanitize
- `vendor-icons` — react-icons

Lazy-loaded pages (`React.lazy`) load on demand: `Settings`, `OnboardingWizard`, `Docs`, `KnowledgeBrowser`.

---

## Common Tasks

### Reset everything
```bash
./shutdown_ai.sh
rm -rf storage/ chat-pwa/dist/
python index.py
./startup_ai.sh
```

### Update dependencies
```bash
./update.sh  # backup, git pull, pip install, npm ci, rebuild PWA
```

### Add a new language
1. Create `chat-pwa/src/i18n/translations.ts` entry for the new locale
2. Update `I18nContext.tsx` to include the new language
3. Add language option in `OnboardingWizard.tsx`

### Connect VSCode (Continue.dev)
```bash
cp continue-config.yaml ~/.continue/config.yaml
# Restart VSCode — models appear in Continue's picker
```

---

## Release Checklist

Before tagging a release, run:
```bash
python scripts/public_readiness.py
python test_system.py --verbose
cd chat-pwa && npx tsc --noEmit && npm run build && cd ..
git diff --check  # verify no trailing whitespace
```
