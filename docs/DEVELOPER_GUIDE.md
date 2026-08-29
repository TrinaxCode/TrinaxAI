# TrinaxAI Developer Guide

[Versión en español](DEVELOPER_GUIDE.es.md)

Use the [documentation hub](README.md) to choose the right reference. When a
user-facing behavior changes, update the English guide, its `.es.md` counterpart,
the relevant in-app Docs section, and `CHANGELOG.md`. For user-facing failures,
keep the action map aligned with [Troubleshooting](TROUBLESHOOTING.md).

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
├── service_manager.py     # Cross-platform service supervisor
├── test_system.py         # Automated health checks
│
├── chat-pwa/              # React PWA frontend
│   ├── src/components/    # React UI components
│   ├── src/lib/           # API domains/facade, config, shared state, profile
│   ├── src/hooks/         # chat/Agent controllers and stream lifecycle
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
5. If the PWA needs it, add the fetch function to the relevant
   `chat-pwa/src/lib/api_*.ts` domain; update `api.ts` only when its public
   export surface changes.

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
Checks: required files, public-path and secret hygiene, i18n coverage, Python
tests/compile, frontend type checking, and the production PWA build.

### CI
`.github/workflows/ci.yml` runs on push/PR:
- Python syntax check (`python -m compileall`)
- TypeScript type check (`npx tsc --noEmit`)
- Frontend build (`npm run build`)

---

## Debugging Tips

Start with the [troubleshooting and recovery guide](TROUBLESHOOTING.md). It
explains when to retry, start AI, open indexing, reload a published index, or
perform a full reindex.

### RAG API not starting
```bash
# Check port
lsof -i :3333

# Run directly with verbose output
python -c "import uvicorn; uvicorn.run('rag_api:app', host='127.0.0.1', port=3333, reload=True)"
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

Use `--host 127.0.0.1` for local-only debugging. Keep `0.0.0.0` for a
trusted private-network device test only, and never expose the development
server or backend ports to the public Internet.

### Indexing issues

Prefer the PWA's **Retry** action or `trinaxai index PATH`. The following is a
destructive developer-only reset: back up `storage/`, stop the services, and
confirm that a complete rebuild is actually required before running it.

```bash
# Full reindex (destructive developer reset)
rm -rf storage/docstore.json storage/index_store.json storage/manifest.json
python index.py
curl --cacert PATH_TO_PUBLIC_CA.pem -X POST https://localhost:3333/system/reload
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
npm run serve     # Serves the production build and same-origin API gateway
```

### Debugging the Frontend
- **React DevTools**: Install the browser extension for component inspection.
- **Network tab**: All API calls go through the same-origin gateway — check `/api/rag/*` and `/api/ollama/*`.
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

This removes local indexes and built frontend output. Back up `storage/` and
`.env` first; use the guided backup if the data matters.

```bash
./shutdown_ai.sh
rm -rf storage/ chat-pwa/dist/
python index.py
./startup_ai.sh
```

### Update dependencies
```bash
./update.sh  # backup, archive update, pip install, npm ci, rebuild PWA
```

### Add a new language
1. Create `chat-pwa/src/i18n/translations.ts` entry for the new locale
2. Update `I18nContext.tsx` to include the new language
3. Add language option in `OnboardingWizard.tsx`

### Update documentation

Keep these layers aligned:

1. The root README for the user-facing overview and quick start.
2. `docs/` for complete operational and technical references.
3. `chat-pwa/README.md` for frontend runtime/development details.
4. `chat-pwa/src/components/Docs.tsx` for short, bilingual in-app guidance.
5. `docs/TROUBLESHOOTING.md` and `.es.md` for recovery decisions and support data.

Check commands against `trinaxai_cli/app.py`, routes against
`app/routes/`/`/openapi.json`, environment names against `.env.example`,
frontend scripts against `chat-pwa/package.json`, and visible error actions
against `chat-pwa/src/lib/api_errors.ts`. Never include real tokens, private
paths, or generated files from `storage/` in examples.

### Connect VSCode (Continue.dev)
```bash
cp continue-config.yaml ~/.continue/config.yaml
# Restart VSCode — models appear in Continue's picker
```

---

## Release Checklist

Before tagging a release, run:
```bash
make check
git diff --check  # verify no trailing whitespace
```

Use a semantic tag such as `v1.0.0` and keep it equal to the versions in
`pyproject.toml`, `chat-pwa/package.json`, `chat-pwa/package-lock.json`, and
`trinaxai_cli/app.py`. The tag workflow reruns the release gates and publishes
the source archives, shell and PowerShell installers, checksums, and provenance.
