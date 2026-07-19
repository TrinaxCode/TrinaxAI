# PWA de Chat de TrinaxAI

Frontend 1.2.0 de TrinaxAI construido con React 19, TypeScript y Vite 6, bajo licencia AGPL-3.0-or-later. Incluye chat directo con Ollama, RAG con citas, búsqueda web opcional, investigación profunda, agente con herramientas, visión, documentos, voz local, memoria y una PWA instalable.

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

Necesitas Node.js 18 o superior y npm; se recomienda una versión LTS activa. Ollama aporta la inferencia y el backend Python las funciones RAG.

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
├── hooks/                   historial y ciclo de streaming
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
- **Internet:** consulta DuckDuckGo, Brave Search o SearXNG, muestra fuentes y realiza lecturas acotadas de páginas públicas protegidas contra SSRF.
- **Investigación:** descompone consultas, combina web y conocimiento local autorizado y sintetiza respuestas con fuentes.
- **Agente:** comparte motor con la CLI, confina archivos al workspace y pide aprobación antes de escribir, editar o ejecutar comandos.
- **Visión:** las imágenes se reducen a un lado máximo de 768 px y se convierten a JPEG antes de la inferencia.
- **Documentos:** PDF, DOCX, PPTX y texto pueden extraerse temporalmente con `/documents/extract`; esto no los indexa.
- **Indexación:** el navegador filtra extensiones, sube una carpeta a `/system/index-upload` y consulta el progreso del trabajo.
- **Voz:** los controles de `ChatInterface` usan capacidades del navegador cuando existen; el respaldo local consulta `/v1/voice/capabilities`, `/stt` y `/tts`.

## Emparejar un navegador

Un navegador LAN puede usar el chat Ollama sin emparejarse, pero no puede leer
datos privados ni usar RAG, memoria, archivos, indexación, agente o controles
del sistema hasta consumir un código corto de un solo uso.

1. En la PWA host, abre **Configuración → Dispositivo emparejado → Generar
   código de emparejamiento**.
2. En el otro equipo abre `https://IP-LOCAL-DEL-HOST:3334`, elige la opción de
   instalación existente, introduce el código, nombra el dispositivo y confirma.
3. Vuelve a la PWA host para revisar o revocar el equipo. Si quieres, instala la
   PWA desde el menú del navegador.

La PWA host solicita `chat,read_private,index,system,agent` para que el navegador
emparejado use la interfaz completa. Para un equipo con privilegio mínimo,
genera el código con `trinaxai pair start --scopes ...`; el valor inicial de la
CLI es `chat,read_private`.

La PWA conserva el bearer en `localStorage`, lo envía como
`X-TrinaxAI-Device-Token`, muestra dispositivo/scopes y permite autorrevocación.
Así mantiene la identidad entre reinicios del navegador/PWA; una revocación o
borrado remoto elimina el token local. El host puede revisar/revocar con
`trinaxai pair list` y `trinaxai pair revoke ID`. Pairing identifica un
dispositivo, no una cuenta de usuario.

La memoria persistente se recupera por consulta. Antes del turno, la PWA pide a
`POST /v1/memory/context` solo entradas activas relevantes y las envuelve como
datos explícitamente no confiables. Nunca inyecta el resumen global ni el
scratchpad local `tc-project-memory`. El panel muestra tipo, provenance,
expiración y edición, y exige confirmación antes de borrar.

## Estado y persistencia

| Capa | Contenido |
|---|---|
| Estado React | Vista, composer y stream actuales. |
| `localStorage` | Sesiones, carpetas, modelos, tema, idioma y preferencias `tc-*`. |
| FastAPI `chat_attachments/` | Adjuntos compartidos por el host; destino preferido. |
| IndexedDB | Fallback offline de adjuntos en `trinaxai-chat-files`. |
| `storage/app_state.json` | Selección de estado `tc-*` compartido mediante FastAPI. |
| Almacenamiento RAG | Colecciones, chunks, memoria y métricas; pertenece al backend. |

`sharedState.ts` usa una revisión monótona del servidor y ETags. Las mutaciones del navegador se persisten como operaciones incrementales `set`/`delete` con un ID estable de dispositivo; ante un `409`, las operaciones pendientes se rebasan sobre la revisión canónica y se reintentan. El sondeo periódico recibe `304` cuando no cambia nada y ya no vuelve a hashear ni subir un snapshot completo. Las sesiones y sus registros de eliminación conservan la fusión estructurada. La sincronización no bloquea el arranque y exige `read_private` (o privilegio local/admin); sigue siendo sincronización entre dispositivos, no un sistema de cuentas multiusuario.

Al adjuntar un archivo, la PWA intenta guardarlo primero en FastAPI para que una conversación sincronizada pueda abrirlo desde otro dispositivo. Si el backend no está disponible o es antiguo, conserva una copia solo en IndexedDB.

## Comportamiento PWA y offline

`vite-plugin-pwa` genera manifest y service worker Workbox:

- `CacheFirst` para JS/CSS e imágenes locales.
- `NetworkFirst` solo para salud pública; datos privados de API no entran en el runtime cache.
- Fallback de navegación a `/index.html`, excepto rutas `/api/*`.
- Comprobación de actualizaciones cada hora y aviso mediante `PwaUpdater`.

“Offline” significa que puede abrir el shell y recursos ya cacheados. Generar respuestas, indexar, usar voz del backend o consultar datos no cacheados necesita que los servicios locales estén disponibles.

## Configuración, HTTPS y seguridad

Consulta la [referencia completa de configuración](../docs/CONFIGURATION.es.md). Las variables `VITE_TRINAXAI_*` se fijan al construir; los destinos `TRINAXAI_RAG_TARGET` y `TRINAXAI_OLLAMA_TARGET` se leen al ejecutar Vite.

Vite usa `chat-pwa/certs/trinaxai-local.pfx` o el par `chat-pwa/certs/localhost-key.pem`/`chat-pwa/certs/localhost.pem`. Sin esos archivos sirve HTTP. Nunca confirmes certificados o claves.

El gateway valida capability admin/de dispositivo, elimina identidad de proxy
aportada por cliente y firma el peer original para `/api/rag`; FastAPI solo
acepta esa identidad desde loopback. `/api/ollama` exige `chat`, tiene allowlist fija, rate limit acotado y
lock de inferencia cross-process: no permite pull/create/delete de modelos.
Lecturas privadas y mutaciones de FastAPI exigen autorización. `/api/system/*`
aplica la misma frontera de credencial/capability antes de acciones fijas.
No publiques el gateway en Internet; usa VPN/TLS autenticado y conserva FastAPI
y Ollama en loopback.

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
- **El teléfono no usa una función protegida:** empareja desde el host y concede
  el scope exacto. Otorga `system` solo si debe controlar servicios; no repartas
  el token admin como atajo.
- **Micrófono:** revisa permiso, contexto seguro y `/api/rag/v1/voice/capabilities`.
- **Vite sirve HTTP:** instala/genera los certificados locales esperados.
