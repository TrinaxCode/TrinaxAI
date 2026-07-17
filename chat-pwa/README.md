# TrinaxAI Chat PWA

TrinaxAI 1.1.0 frontend built with React 19, TypeScript, and Vite 6 under AGPL-3.0-or-later. It provides direct Ollama chat, cited RAG, optional web search, deep research, a tool-using agent, image analysis, documents, local voice, memory, and installable PWA behavior.

[Versión en español](README.es.md) · [Project documentation](../docs/README.md) · [API reference](../docs/API_REFERENCE.md)

## Runtime model

```text
Browser / installed PWA :3334
  ├── /api/rag/*    ── Vite proxy ──> FastAPI :3333
  ├── /api/ollama/* ── Vite proxy ──> Ollama  :11434
  └── /api/system/* ── local Vite middleware ──> service_manager.py
```

The browser normally uses same-origin `/api/*` URLs. This avoids mixed-content and most CORS issues and keeps Ollama off the LAN. FastAPI handles RAG, collections, memory, indexing, document extraction, voice fallback, and shared app state. Direct chat and vision stream from Ollama through the proxy.

## Prerequisites

- Node.js 20 or newer and npm.
- A running Ollama instance for chat/vision.
- The Python backend for RAG, indexing, memory, shared state, and server voice.
- Models configured in the onboarding wizard or environment.

For a full installation, use the repository-level installer. For frontend-only development:

```bash
cd chat-pwa
npm install
npm run dev
```

Open `https://localhost:3334` when local certificates exist; Vite falls back to HTTP when none are available. A browser warning is expected for a self-signed certificate.

## Scripts

| Command | Result |
|---|---|
| `npm run dev` | Vite development server on `0.0.0.0:3334` with HMR. |
| `npm run build` | TypeScript check followed by a production build in `dist/`. |
| `npm run preview` | Serve `dist/` on port 3334 using the production proxy/middleware. |
| `npm test` | Run the Vitest suite once. |
| `npx tsc --noEmit` | Type-check without building. |

There is currently no `npm run lint` script; repository checks use `npx tsc --noEmit`.

## Source map

```text
src/
├── main.tsx                 providers and service-worker registration
├── App.tsx                  page state, navigation, onboarding, chat history
├── components/
│   ├── ChatInterface.tsx    composer, rendering, files, voice, research
│   ├── ChatSidebar.tsx      sessions, folders, search and export
│   ├── Settings.tsx         models, index, prompts, memory and statistics
│   ├── KnowledgeBrowser.tsx indexed sources and chunks
│   ├── Docs.tsx             in-app user guide
│   └── PwaUpdater.tsx       update notification
├── hooks/
│   ├── useChatHistory.ts    session/folder persistence
│   └── useStreamChat.ts     stream lifecycle and cancellation
├── lib/
│   ├── api.ts               backend/Ollama client and stream parsers
│   ├── config.ts            same-origin URL resolution
│   ├── sharedState.ts       host-backed cross-device state synchronization
│   ├── chatAttachments.ts   IndexedDB attachment storage
│   └── userProfile.ts       local profile and conversation memory helpers
├── services/voice.ts        Web Speech and FastAPI voice adapters
├── i18n/                    Spanish/English translations and provider
└── theme/                   light/dark theme provider
```

`Settings`, `OnboardingWizard`, `Docs`, and `KnowledgeBrowser` are lazy-loaded. Rollup creates separate React, motion, Markdown, and icon chunks.

## Chat flows

### Direct Ollama

`streamOllama()` posts to `/api/ollama/api/chat` and parses newline-delimited JSON. Before sending, the client compacts long history and selects a model heuristically from the configured general, code, deep, and fast models. Missing models can be pulled through Ollama.

### RAG

`streamRag()` posts OpenAI-shaped messages to `/api/rag/v1/chat/completions`. It parses Server-Sent Events, including `trinaxai` metadata and `trinaxai_sources` citations. Active collection IDs are included with the request.

### Web search, research, and agent

- Internet mode queries DuckDuckGo, Brave Search, or SearXNG, displays sources, and performs bounded SSRF-protected reads of public pages.
- Deep research decomposes a question, combines the web with authorized local knowledge, and synthesizes a sourced answer.
- The Agent view shares its engine with the CLI, confines file access to the selected workspace, and requests approval before writes, edits, or commands.

### Attachments and vision

- Images are resized to a maximum side of 768 px and encoded as JPEG before Ollama vision inference.
- Text, Markdown, PDF, DOCX, and PPTX documents can be extracted temporarily by `/documents/extract`; temporary extraction does not add them to the RAG index.
- Attachments are uploaded to the host first so synchronized chats can open them on another device. IndexedDB is the offline/older-backend fallback; chat messages retain metadata and storage keys.
- Folder import filters supported extensions in the browser, uploads them to `/system/index-upload`, then polls the job endpoint.

### Voice

Voice controls in `ChatInterface` prefer browser speech capabilities where available and fall back to:

- `GET /v1/voice/capabilities`
- `POST /v1/voice/stt` for local Whisper transcription
- `POST /v1/voice/tts` for a locally available TTS backend

Voice availability varies by OS, browser permissions, installed Python extras, and local audio support. See the API response instead of assuming a particular TTS engine exists.

## Pairing a browser

A LAN browser may use Ollama chat without pairing, but it cannot read private
data or use RAG, memory, files, indexing, the agent, or system controls until it
claims a short, single-use code.

1. In the host PWA, open **Settings → Paired device → Generate pairing code**.
2. On the other device, open `https://HOST-LAN-IP:3334`, choose the existing
   installation option, enter the code, name the device, and pair it.
3. Return to the host PWA to review or revoke the device. Install the PWA from
   the browser menu if desired.

The default token grants `chat,read_private`. Elevated `index`, `system`, or
`agent` scopes must be granted deliberately for a device that needs them; the
host CLI remains available for explicit scope selection and administration.

The PWA keeps the bearer in `sessionStorage`, attaches it as
`X-TrinaxAI-Device-Token`, shows the active device/scopes, and can revoke itself.
Closing the browser session removes the local clear token. The host can review
or revoke any device with `trinaxai pair list` and `trinaxai pair revoke ID`.
Pairing identifies a device, not a user account.

Persistent memory is query-scoped. Before a turn, the PWA asks
`POST /v1/memory/context` for active relevant entries and wraps the result in an
explicit untrusted-data block. It never injects the global memory summary or the
local `tc-project-memory` scratchpad. The memory panel exposes kind, provenance,
expiry and editing, and requires confirmation before deletion.

## State and data ownership

The frontend deliberately uses several storage layers:

| Layer | Data | Notes |
|---|---|---|
| React state | Current page, composer, active stream | Ephemeral. |
| `localStorage` | Sessions, folders, models, theme, language, prompts, onboarding | Primary browser state under `tc-*` keys. |
| FastAPI `chat_attachments/` | Attachment blobs shared by the host | Preferred storage for new attachments. |
| IndexedDB | Offline attachment fallback | Database `trinaxai-chat-files`. |
| FastAPI `app_state.json` | Selected `tc-*` values | Enables synchronization between browsers on the same host. |
| FastAPI RAG storage | Collections, chunks, memory, usage | Not owned by the frontend. |

`sharedState.ts` uses a server-side monotonic revision and ETag. Browser mutations are persisted as incremental `set`/`delete` operations with a stable device ID; a `409` response rebases pending operations on the authoritative revision before retrying. The periodic poll receives `304` when unchanged and does not re-hash or upload a complete snapshot. Session and deletion records keep their structured merge behavior. Sync begins in the background so an unavailable RAG backend does not block startup. Access requires `read_private` (or admin/local privilege); this remains device synchronization, not a multi-user account system.

## PWA behavior

`vite-plugin-pwa` generates the manifest and Workbox service worker.

- Display modes: `standalone`, with `window-controls-overlay` preferred when supported.
- Shortcuts: New Chat and Settings.
- Precaching: built JS/CSS/HTML plus icons, fonts, and images matching the configured patterns.
- Runtime cache: `StaleWhileRevalidate` for built JS/CSS, `CacheFirst` for local
  images, and `NetworkFirst` only for the public health response. Private API
  data is not stored in Workbox runtime caches.
- Navigation fallback: `/index.html`, excluding `/api/*`.
- Updates: the app checks the service worker hourly and shows `PwaUpdater` when a refresh is needed.

Offline support means the application shell and previously cached read-only responses can load. New AI responses, indexing, voice fallback, and uncached knowledge operations still require the local services to be reachable.

## Environment and certificates

Frontend URL resolution lives in `src/lib/config.ts`. See the full [configuration reference](../docs/CONFIGURATION.md).

| Variable | Purpose |
|---|---|
| `VITE_TRINAXAI_RAG_BASE` / `VITE_TRINAXAI_OLLAMA_BASE` | Browser production bases. |
| `VITE_TRINAXAI_DEV_RAG_BASE` / `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Browser development bases. |
| `TRINAXAI_RAG_TARGET` / `TRINAXAI_OLLAMA_TARGET` | Server-side Vite proxy targets. |
| `VITE_TRINAXAI_VISION_MODEL` | Fast vision model. |
| `VITE_TRINAXAI_KEEP_ALIVE` | Direct-chat keep-alive default (optional; defaults to `10m` in the client). |

Vite loads `chat-pwa/certs/trinaxai-local.pfx` first, or `chat-pwa/certs/localhost-key.pem` plus `chat-pwa/certs/localhost.pem`. Certificate files are local secrets/artifacts and must not be committed.

## System-control boundary

The custom gateway validates paired-device/admin capability, strips
client-supplied proxy-identity headers and attaches a fresh HMAC-signed original
peer to `/api/rag`. FastAPI only accepts that identity from loopback.
`/api/ollama` requires `chat`, has a fixed method/path allowlist, its own bounded
rate window, and a cross-process inference lock;
it cannot administer model pull/create/delete. Private FastAPI reads as well as
mutations require authorization. `/api/system/*` applies the same remote
credential/capability boundary before invoking fixed lifecycle actions.

Do not expose the gateway directly to the public Internet. Use a VPN or an
authenticated TLS terminator, and keep both FastAPI and Ollama bound to loopback.

## Testing and contribution

```bash
cd chat-pwa
npm test
npx tsc --noEmit
npm run build
```

Tests cover API helpers, SSE/NDJSON parsing, strings, and the streaming hook. For a cross-stack change, also run from the repository root:

```bash
make test
make readiness
```

When changing UI text, add matching Spanish and English keys in `src/i18n/translations.ts`. When changing a response shape, update `src/lib/api.ts`, its parser tests, and the repository API reference together.

## Troubleshooting

- **Backend appears offline:** open `/api/rag/health` through the PWA origin, then check `trinaxai doctor`.
- **Ollama appears offline:** check `ollama list` and `/api/ollama/api/tags` through the PWA origin.
- **Old UI after a build:** use the update prompt or unregister the service worker and clear site data in browser development tools.
- **LAN device cannot use a protected feature:** pair it from the host and grant
  the exact scope. Grant `system` only to a device that should control services;
  do not distribute the admin token as a convenience workaround.
- **Microphone fails:** verify browser permission and secure context, then inspect `/api/rag/v1/voice/capabilities`.
- **HTTPS becomes HTTP:** generate/install local certificates; Vite only enables HTTPS when certificate files exist.
