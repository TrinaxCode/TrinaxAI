<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 💬 Chat PWA
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="README.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="../docs/README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="../docs/CHANGELOG.md">Changelog</a></sub></p>

TrinaxAI 1.2.0 frontend built with React 19, TypeScript, and Vite 6 under AGPL-3.0-or-later. It provides direct Ollama chat, cited RAG, optional web search, deep research, a tool-using agent, image analysis, documents, local voice, memory, and installable PWA behavior.

[Project documentation](../docs/README.md) · [API reference](../docs/API_REFERENCE.md) · [Troubleshooting](../docs/TROUBLESHOOTING.md)

## Runtime model

```text
Browser / installed PWA :3334
  ├── /api/rag/*    ── production gateway ──> FastAPI :3333
  ├── /api/ollama/* ── production gateway ──> Ollama  :11434
  └── /api/system/* ── production gateway ──> service_manager.py
```

The browser normally uses same-origin `/api/*` URLs. This avoids mixed-content and most CORS issues and keeps Ollama off the LAN. FastAPI handles RAG, collections, memory, indexing, document extraction, voice fallback, and shared app state. Direct chat and vision stream from Ollama through the proxy.

## Prerequisites

- Node.js 22 or newer and npm; an active LTS release is recommended.
- A running Ollama instance for chat/vision.
- The Python backend for RAG, indexing, memory, shared state, and server voice.
- Models configured in the onboarding wizard or environment.

For a full installation, use the repository-level installer. For frontend-only development:

```bash
cd chat-pwa
npm install
npm run dev
```

Open `https://localhost:3334` when local certificates exist; without them the gateway falls back to HTTP only on loopback. A non-loopback host fails closed unless `TRINAXAI_ALLOW_INSECURE_HTTP=1` is explicitly set for a trusted test network. For LAN access, install the public CA shown by `trinaxai network` on each device; do not bypass certificate verification. See the [LAN pairing and HTTPS trust guide](../docs/NETWORK_PAIRING.md).

## Scripts

| Command | Result |
|---|---|
| `npm run dev` | Vite development server on `127.0.0.1:3334` with HMR. Set `TRINAXAI_PWA_HOST=0.0.0.0` only for an intentional HTTPS LAN test. |
| `npm run build` | TypeScript check, Vite production build in `dist/`, and the production gateway bundle. |
| `npm run serve` | Serve `dist/` on port 3334 using the production Node gateway. |
| `npm run preview` | Compatibility alias for `npm run serve`. |
| `npm test` | Run Vitest and the production gateway integration tests. |
| `npm run check:bundle` | Check the generated frontend bundle budget. |
| `npm run lint` | Run ESLint. |
| `npx tsc --noEmit` | Type-check without building. |

The dev server binds to loopback by default. For an intentional LAN test, set
`TRINAXAI_PWA_HOST=0.0.0.0`, use HTTPS, and pair every remote browser; never
expose the development server or backend ports to the public Internet.

## Source map

```text
src/
├── main.tsx                 providers and service-worker registration
├── App.tsx                  page state, navigation, onboarding, chat history
├── components/
│   ├── ChatInterface.tsx    stable chat component boundary
│   ├── chat/ChatInterfaceView.tsx chat rendering and layout
│   ├── agent/                Agent view and shared contracts
│   ├── ChatSidebar.tsx      sessions, folders, search and export
│   ├── Settings.tsx         models, index, prompts, memory and statistics
│   ├── KnowledgeBrowser.tsx indexed sources and chunks
│   ├── Docs.tsx             in-app user guide
│   └── PwaUpdater.tsx       update notification
├── hooks/
│   ├── useChatHistory.ts    session/folder persistence
│   ├── useChatTurn.ts       turn routing and context assembly
│   ├── useChatDocuments.ts  document extraction and indexing jobs
│   ├── useChatAttachments.ts image/file attachment lifecycle
│   ├── useChatVoice.ts      speech and spoken response lifecycle
│   ├── useChatController.ts chat state and UI composition
│   ├── useChatSend.ts       message sending and route dispatch
│   ├── useChatMessageActions.ts edit, regenerate and continuation actions
│   ├── useAgentController.ts Agent execution, approvals and history
│   ├── useAgentVoice.ts     Agent dictation lifecycle
│   └── useStreamChat.ts     stream lifecycle and cancellation
├── lib/
│   ├── api.ts               stable public API facade
│   ├── api_*.ts             HTTP domains, model calls, streams and documents
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

`streamRag()` posts OpenAI-shaped messages to `/api/rag/v1/chat/completions`. It parses Server-Sent Events, including `trinaxai` metadata and `trinaxai_sources` citations. Active collection IDs are included with the request. If the selected collection is empty or missing, the PWA offers **Open indexing**; index a source from **Settings → Indexing**, wait for `completed`, and retry.

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

- `GET /api/rag/v1/voice/capabilities`
- `POST /api/rag/v1/voice/stt` for local Whisper transcription
- `POST /api/rag/v1/voice/tts` for a locally available TTS backend

Voice availability varies by OS, browser permissions, installed Python extras, and local audio support. See the API response instead of assuming a particular TTS engine exists.

## Pairing a browser

A LAN browser must pair before it can use Ollama chat or private APIs. A short,
single-use code can grant `chat`, `read_private`, and `web`; private reads
include authorized RAG, synchronized history, memory context, and host-backed
files.

1. In the host PWA, open **Settings → Paired device → Generate pairing code**.
2. On the other device, open `https://HOST-LAN-IP:3334`, choose the existing
   installation option, enter the code, name the device, and pair it.
3. Return to the host PWA to review or revoke the device. Install the PWA from
   the browser menu if desired.

Before opening the LAN URL, trust the public certificate shown by `trinaxai
network`. The host installer can trust itself, but phones and tablets need a
separate user-trusted CA/profile. Follow the [LAN pairing and HTTPS trust guide](../docs/NETWORK_PAIRING.md).

Pairing never grants `index`, `system`, `agent`, or `agent_yolo`. Index and
memory/configuration mutations, Agent workspace access, model management,
lifecycle actions, factory reset, and management of other devices require
opening `https://localhost:3334` on the host. Admin credentials and old device
tokens containing retired scopes do not override this boundary. The CLI pairing
default is `chat,read_private`.

The PWA keeps new device credentials in an `HttpOnly; SameSite=Strict` cookie
scoped to `/api/rag`, shows the active device/scopes, and can revoke itself. A
legacy browser-stored bearer is sent only during the explicit `/v1/pairing/me`
migration, then removed. The host can review or revoke any device with
`trinaxai pair list` and `trinaxai pair revoke ID`. Pairing identifies a device,
not a user account.

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
- Localized manifests: `/manifest.en.webmanifest` and `/manifest.es.webmanifest` keep app metadata and shortcuts in the selected language; the React shell switches the manifest when `tc-lang` changes.
- Shortcuts: New Chat and Settings (localized in each manifest).
- The offline page is a standalone bilingual HTML screen that uses `tc-lang` or the browser language without loading React.
- Precaching: built JS/CSS/HTML plus icons, fonts, and images matching the configured patterns.
- Runtime cache: `CacheFirst` for built JS/CSS and local images, and
  `NetworkFirst` only for the public health response. Private API
  data is not stored in Workbox runtime caches.
- Navigation fallback: `/index.html`, excluding `/api/*`.
- Updates: the app checks the service worker hourly and shows `PwaUpdater` when a refresh is needed.

Offline support means the application shell and previously cached read-only responses can load. New AI responses, indexing, voice fallback, and uncached knowledge operations still require the local services to be reachable.

## In-app documentation

Open **Settings → Documentation** to read the bilingual guide without leaving the PWA. It covers the product overview, installation, configuration, models, indexing, Agent workspaces, Internet and research, files and collections, security, API basics, PWA installation, troubleshooting, and contributing.

The in-app guide is intentionally task-oriented and safe to read from a phone. When an error offers **Open indexing**, **Retry**, **Start AI**, or **Open settings**, use that action first. The repository references remain authoritative for complete contracts and exact defaults: use the [troubleshooting guide](../docs/TROUBLESHOOTING.md), [API reference](../docs/API_REFERENCE.md), [configuration reference](../docs/CONFIGURATION.md), and [documentation hub](../docs/README.md) when integrating or operating the backend.

## Environment and certificates

Frontend URL resolution lives in `src/lib/config.ts`. See the full [configuration reference](../docs/CONFIGURATION.md).

| Variable | Purpose |
|---|---|
| `VITE_TRINAXAI_RAG_BASE` / `VITE_TRINAXAI_OLLAMA_BASE` | Browser production bases. |
| `VITE_TRINAXAI_DEV_RAG_BASE` / `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Browser development bases. |
| `TRINAXAI_RAG_TARGET` / `TRINAXAI_OLLAMA_TARGET` | Server-side production gateway targets. |
| `VITE_TRINAXAI_VISION_MODEL` | Fast vision model. |
| `VITE_TRINAXAI_KEEP_ALIVE` | Direct-chat keep-alive default (optional; defaults to `10m` in the client). |

The gateway loads `chat-pwa/certs/trinaxai-local.pfx` first, or `chat-pwa/certs/localhost-key.pem` plus `chat-pwa/certs/localhost.pem`. Certificate files are local secrets/artifacts and must not be committed. Without those files, HTTP is allowed only on loopback; a non-loopback host fails closed unless `TRINAXAI_ALLOW_INSECURE_HTTP=1` is explicitly set for a trusted test network. If the host changes LAN networks or receives a new IP, run `trinaxai network refresh` before using the PWA from another device.

## System-control boundary

The custom gateway validates paired-device/admin capability, strips
client-supplied proxy-identity headers and attaches a fresh HMAC-signed original
peer to `/api/rag`. FastAPI only accepts that identity from loopback.
`/api/ollama` has a fixed method/path allowlist, its own bounded rate window,
and a cross-process inference lock. Chat/generation require `chat`; model pull
and deletion require a real loopback peer. Private FastAPI reads require
authorization, while host mutations require verified loopback provenance.
`/api/system/*` is also loopback-only before invoking fixed lifecycle actions.

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

When changing UI text, add matching Spanish and English keys in `src/i18n/translations.ts`. When changing a response shape, update the relevant `src/lib/api_*.ts` domain (and the `api.ts` facade if its public export changes), its parser tests, and the repository API reference together.

## Troubleshooting

- **Backend appears offline:** open `/api/rag/health` through the PWA origin, then check `trinaxai doctor`.
- **Ollama appears offline:** check `ollama list` and `/api/ollama/api/tags` through the PWA origin.
- **Old UI after a build:** use the update prompt or unregister the service worker and clear site data in browser development tools.
- **LAN device cannot use a protected feature:** pair it from the host for
  `chat`, `read_private`, or `web`. Perform indexing, Agent, model, device, and
  system administration from `https://localhost:3334` on the host.
- **Microphone fails:** verify browser permission and secure context, then inspect `/api/rag/v1/voice/capabilities`.
- **HTTPS becomes HTTP:** generate/install local certificates; the gateway only enables HTTPS when certificate files exist.
