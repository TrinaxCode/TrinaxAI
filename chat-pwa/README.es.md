# PWA de Chat de TrinaxAI

Frontend de TrinaxAI construido con React 19, TypeScript y Vite 6. Incluye chat directo con Ollama, chat RAG con citas, visión, documentos adjuntos, voz local, explorador de conocimiento y comportamiento instalable como PWA.

[English](README.md) · [Índice de documentación](../docs/README.es.md) · [Referencia de API](../docs/API_REFERENCE.es.md)

## Modelo de ejecución

```text
Navegador / PWA instalada :3334
  ├── /api/rag/*    ── proxy de Vite ──> FastAPI :3333
  ├── /api/ollama/* ── proxy de Vite ──> Ollama  :11434
  └── /api/system/* ── middleware local ──> service_manager.py
```

El navegador usa rutas `/api/*` del mismo origen. FastAPI atiende RAG, colecciones, memoria, indexación, extracción, voz de respaldo y estado compartido; el chat directo y la visión llegan a Ollama mediante el proxy.

## Desarrollo rápido

Necesitas Node.js 20 o superior, npm, Ollama para inferencia y el backend Python para las funciones RAG.

```bash
cd chat-pwa
npm install
npm run dev
```

| Comando | Resultado |
|---|---|
| `npm run dev` | Servidor Vite con HMR en `0.0.0.0:3334`. |
| `npm run build` | Verificación TypeScript y build en `dist/`. |
| `npm run preview` | Sirve `dist/` con proxies y middleware de sistema. |
| `npm test` | Ejecuta Vitest una vez. |
| `npx tsc --noEmit` | Verifica tipos sin construir. |

No existe un script `npm run lint`; las comprobaciones usan TypeScript directamente.

## Organización del código

```text
src/
├── main.tsx                 providers y registro del service worker
├── App.tsx                  páginas, navegación, onboarding e historial
├── components/
│   ├── ChatInterface.tsx    chat, adjuntos, voz e investigación
│   ├── ChatSidebar.tsx      sesiones, carpetas, búsqueda y exportación
│   ├── Settings.tsx         modelos, índice, prompts, memoria y métricas
│   ├── KnowledgeBrowser.tsx fuentes y chunks indexados
│   └── Docs.tsx             ayuda integrada
├── hooks/                   historial, streaming y modo voz
├── lib/
│   ├── api.ts               cliente HTTP y parsers SSE/NDJSON
│   ├── config.ts            resolución de URLs same-origin
│   ├── sharedState.ts       sincronización entre dispositivos
│   └── chatAttachments.ts   adjuntos en IndexedDB
├── services/voice.ts        adaptadores de voz navegador/backend
├── i18n/                    traducciones español/inglés
└── theme/                   tema claro/oscuro
```

`Settings`, `OnboardingWizard`, `Docs` y `KnowledgeBrowser` se cargan bajo demanda.

## Flujos principales

- **Ollama:** `streamOllama()` usa `/api/ollama/api/chat`, compacta historial y procesa NDJSON. Un router heurístico selecciona modelos general, código, profundo o rápido.
- **RAG:** `streamRag()` usa `/api/rag/v1/chat/completions`, procesa SSE y conserva metadatos y citas `trinaxai_sources`.
- **Visión:** las imágenes se reducen a un lado máximo de 768 px y se convierten a JPEG antes de la inferencia.
- **Documentos:** PDF, DOCX, PPTX y texto pueden extraerse temporalmente con `/documents/extract`; esto no los indexa.
- **Indexación:** el navegador filtra extensiones, sube una carpeta a `/system/index-upload` y consulta el progreso del trabajo.
- **Voz:** se usan capacidades del navegador cuando existen; el respaldo local consulta `/v1/voice/capabilities`, `/stt` y `/tts`.

## Estado y persistencia

| Capa | Contenido |
|---|---|
| Estado React | Vista, composer y stream actuales. |
| `localStorage` | Sesiones, carpetas, modelos, tema, idioma y preferencias `tc-*`. |
| FastAPI `chat_attachments/` | Adjuntos compartidos por el host; destino preferido. |
| IndexedDB | Fallback offline de adjuntos en `trinaxai-chat-files`. |
| `storage/app_state.json` | Selección de estado `tc-*` compartido mediante FastAPI. |
| Almacenamiento RAG | Colecciones, chunks, memoria y métricas; pertenece al backend. |

`sharedState.ts` usa ETags, fusiona sesiones y registros de eliminación, y sincroniza en segundo plano sin bloquear el arranque. Es sincronización para un host/LAN de confianza, no un sistema de cuentas multiusuario.

Al adjuntar un archivo, la PWA intenta guardarlo primero en FastAPI para que una conversación sincronizada pueda abrirlo desde otro dispositivo. Si el backend no está disponible o es antiguo, conserva una copia solo en IndexedDB.

## Comportamiento PWA y offline

`vite-plugin-pwa` genera manifest y service worker Workbox:

- `CacheFirst` para JS, CSS e imágenes locales.
- `StaleWhileRevalidate`/`CacheFirst` para Google Fonts.
- `NetworkFirst` con timeout de cinco segundos para algunas lecturas de API.
- Fallback de navegación a `/index.html`, excepto rutas `/api/*`.
- Comprobación de actualizaciones cada hora y aviso mediante `PwaUpdater`.

“Offline” significa que puede abrir el shell y recursos ya cacheados. Generar respuestas, indexar, usar voz del backend o consultar datos no cacheados necesita que los servicios locales estén disponibles.

## Configuración, HTTPS y seguridad

Consulta la [referencia completa de configuración](../docs/CONFIGURATION.es.md). Las variables `VITE_TRINAXAI_*` se fijan al construir; los destinos `TRINAXAI_RAG_TARGET` y `TRINAXAI_OLLAMA_TARGET` se leen al ejecutar Vite.

Vite usa `certs/trinaxai-local.pfx` o el par `certs/localhost-key.pem`/`certs/localhost.pem`. Sin esos archivos sirve HTTP. Nunca confirmes certificados o claves.

El middleware `/api/system/*` acepta loopback, un token administrador válido o una LAN privada habilitada explícitamente. FastAPI aplica además su propia autorización. No publiques Vite ni Ollama directamente en Internet; usa VPN o proxy autenticado.

## Validación

```bash
cd chat-pwa
npm test
npx tsc --noEmit
npm run build

cd ..
make test
make readiness
```

Al añadir texto de interfaz, incorpora claves equivalentes en español e inglés en `src/i18n/translations.ts`. Si cambia un contrato HTTP, actualiza `src/lib/api.ts`, sus pruebas de parser y la referencia de API.

## Problemas comunes

- **Backend offline:** abre `/api/rag/health` desde el origen de la PWA y ejecuta `trinaxai doctor`.
- **Ollama offline:** comprueba `ollama list` y `/api/ollama/api/tags`.
- **Interfaz antigua:** aplica el aviso de actualización o elimina service worker y datos del sitio.
- **El teléfono no controla servicios:** es el valor seguro; habilita control LAN solo en una red confiable.
- **Micrófono:** revisa permiso, contexto seguro y `/api/rag/v1/voice/capabilities`.
- **Vite sirve HTTP:** instala/genera los certificados locales esperados.
