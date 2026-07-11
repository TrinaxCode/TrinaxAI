# TrinaxAI Chat PWA

React 19, TypeScript, and Vite 6 frontend for TrinaxAI. It provides direct Ollama chat, RAG chat with citations, image analysis, document attachments, local voice mode, knowledge browsing, settings, and installable PWA behavior.

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
│   ├── useStreamChat.ts     stream lifecycle and cancellation
│   └── useVoiceMode.ts      browser/server voice orchestration
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

### Attachments and vision

- Images are resized to a maximum side of 768 px and encoded as JPEG before Ollama vision inference.
- Text, Markdown, PDF, DOCX, and PPTX documents can be extracted temporarily by `/documents/extract`; temporary extraction does not add them to the RAG index.
- Attachments are uploaded to the host first so synchronized chats can open them on another device. IndexedDB is the offline/older-backend fallback; chat messages retain metadata and storage keys.
- Folder import filters supported extensions in the browser, uploads them to `/system/index-upload`, then polls the job endpoint.

### Voice

`useVoiceMode` prefers browser speech capabilities where available and falls back to:

- `GET /v1/voice/capabilities`
- `POST /v1/voice/stt` for local Whisper transcription
- `POST /v1/voice/tts` for a locally available TTS backend

Voice availability varies by OS, browser permissions, installed Python extras, and local audio support. See the API response instead of assuming a particular TTS engine exists.

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

`sharedState.ts` performs conditional pulls using ETags, merges session/deletion metadata, and pushes changes. Sync begins in the background so an unavailable RAG backend does not block startup. Treat this as trusted-LAN synchronization, not multi-user account storage.

## PWA behavior

`vite-plugin-pwa` generates the manifest and Workbox service worker.

- Display modes: `standalone`, with `window-controls-overlay` preferred when supported.
- Shortcuts: New Chat and Settings.
- Precaching: built JS/CSS/HTML plus icons, fonts, and images matching the configured patterns.
- Runtime cache: `CacheFirst` for local static assets/images; Google Fonts use `StaleWhileRevalidate`/`CacheFirst`; selected read-only API URLs use `NetworkFirst` with a five-second timeout.
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
| `VITE_TRINAXAI_VISION_QUALITY_MODEL` | Quality vision model. |
| `VITE_TRINAXAI_KEEP_ALIVE` | Direct-chat keep-alive default. |

Vite loads `certs/trinaxai-local.pfx` first, or `certs/localhost-key.pem` plus `certs/localhost.pem`. Certificate files are local secrets/artifacts and must not be committed.

## System-control boundary

The custom Vite middleware handles `/api/system/{shutdown,startup,stop-all,index,reload}`. It accepts loopback clients, a valid `X-Admin-Token`, or private-LAN clients only when LAN system control is explicitly enabled. FastAPI independently protects sensitive RAG endpoints.

Do not expose the Vite server directly to the public Internet. Use a VPN or an authenticated, TLS-terminating reverse proxy, and keep Ollama bound to loopback.

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
- **LAN device cannot control services:** this is the secure default; configure LAN system control and a token only for a trusted network.
- **Microphone fails:** verify browser permission and secure context, then inspect `/api/rag/v1/voice/capabilities`.
- **HTTPS becomes HTTP:** generate/install local certificates; Vite only enables HTTPS when certificate files exist.
