<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 💬 PWA de Chat
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="../docs/README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="../docs/CHANGELOG.es.md">Cambios</a></sub></p>

Frontend 1.2.1 de TrinaxAI construido con React 19, TypeScript y Vite 6, bajo licencia AGPL-3.0-or-later. Incluye chat directo con Ollama, RAG con citas, búsqueda web opcional, investigación profunda, agente con herramientas, visión, documentos, voz local, memoria y una PWA instalable.

[Índice de documentación](../docs/README.es.md) · [Referencia de API](../docs/API_REFERENCE.es.md) · [Solución de problemas](../docs/TROUBLESHOOTING.es.md)

## Modelo de ejecución

```text
Navegador / PWA instalada :3334
  ├── /api/rag/*    ── gateway de producción ──> FastAPI :3333
  ├── /api/ollama/* ── gateway de producción ──> Ollama  :11434
  └── /api/system/* ── gateway de producción ──> service_manager.py
```

El navegador usa rutas `/api/*` del mismo origen. FastAPI atiende RAG, colecciones, memoria, indexación, extracción, voz de respaldo y estado compartido; el chat directo y la visión llegan a Ollama mediante el proxy.

## Desarrollo rápido

Necesitas Node.js 22 o superior y npm; se recomienda una versión LTS activa. Ollama aporta la inferencia y el backend Python las funciones RAG.

```bash
cd chat-pwa
npm install
npm run dev
```

| Comando | Resultado |
|---|---|
| `npm run dev` | Servidor Vite con HMR en `127.0.0.1:3334`. Usa `TRINAXAI_PWA_HOST=0.0.0.0` solo para una prueba LAN HTTPS intencional. |
| `npm run build` | Verificación TypeScript, build de Vite en `dist/` y bundle del gateway de producción. |
| `npm run serve` | Sirve `dist/` con el gateway Node de producción. |
| `npm run preview` | Alias de compatibilidad de `npm run serve`. |
| `npm test` | Ejecuta Vitest y las pruebas de integración del gateway de producción. |
| `npm run check:bundle` | Comprueba el presupuesto del bundle frontend generado. |
| `npm run lint` | Ejecuta ESLint. |
| `npx tsc --noEmit` | Verifica tipos sin construir. |

El servidor de desarrollo escucha en loopback por defecto. Para una prueba LAN
intencional, establece `TRINAXAI_PWA_HOST=0.0.0.0`, usa HTTPS y vincula cada
navegador remoto; nunca expongas el servidor de desarrollo ni los puertos del
backend a Internet.

## Organización del código

```text
src/
├── main.tsx                 providers y registro del service worker
├── App.tsx                  páginas, navegación, onboarding e historial
├── components/
│   ├── ChatInterface.tsx    frontera estable del componente de chat
│   ├── chat/ChatInterfaceView.tsx renderizado y layout del chat
│   ├── agent/                vista y contratos compartidos de Agent
│   ├── ChatSidebar.tsx      sesiones, carpetas, búsqueda y exportación
│   ├── Settings.tsx         modelos, índice, prompts, memoria y métricas
│   ├── KnowledgeBrowser.tsx fuentes y chunks indexados
│   └── Docs.tsx             ayuda integrada
├── hooks/
│   ├── useChatTurn.ts       enrutamiento y contexto de turnos
│   ├── useChatDocuments.ts  extracción y jobs de indexación
│   ├── useChatAttachments.ts ciclo de vida de adjuntos
│   ├── useChatVoice.ts      voz y respuestas habladas
│   ├── useChatHistory.ts    persistencia de sesiones y carpetas
│   ├── useChatController.ts estado y composición de la UI del chat
│   ├── useChatSend.ts       envío de mensajes y routing
│   ├── useChatMessageActions.ts edición, regeneración y continuación
│   ├── useAgentController.ts ejecución, aprobaciones e historial de Agent
│   ├── useAgentVoice.ts     ciclo de dictado de Agent
│   └── useStreamChat.ts     ciclo de streaming y cancelación
├── lib/
│   ├── api.ts               fachada pública estable
│   ├── api_*.ts             dominios HTTP, modelos, streams y documentos
│   ├── config.ts            resolución de URLs same-origin
│   ├── sharedState.ts       sincronización entre dispositivos
│   └── chatAttachments.ts   adjuntos en IndexedDB
├── services/voice.ts        adaptadores de voz navegador/backend
├── i18n/                    traducciones español/inglés
└── theme/                   tema claro/oscuro
```

`Settings`, `OnboardingWizard`, `Docs` y `KnowledgeBrowser` se cargan bajo demanda.

## Flujos principales

### Ollama directo

`streamOllama()` usa `/api/ollama/api/chat`, compacta el historial y procesa
NDJSON. Un router heurístico selecciona los modelos general, código, profundo
o rápido configurados.

### RAG e indexación

`streamRag()` usa `/api/rag/v1/chat/completions`, procesa SSE y conserva
metadatos y citas `trinaxai_sources`. La indexación del navegador filtra
extensiones, sube una carpeta a `/system/index-upload` y consulta el progreso
del job. Adjuntar un archivo como contexto temporal no lo indexa. Si la
colección seleccionada está vacía, el aviso ofrece **Abrir indexación** para
llevarte directamente a **Configuración → Indexación**; indexa la fuente, espera
el estado `completed`, selecciona la colección y reintenta.

### Internet e investigación

Internet consulta DuckDuckGo, Brave Search o SearXNG, muestra fuentes y realiza
lecturas acotadas de páginas públicas protegidas contra SSRF. Investigación
descompone consultas, combina web y conocimiento local autorizado y sintetiza
respuestas con fuentes.

### Agent

Comparte motor con la CLI, confina archivos al workspace seleccionado y pide
aprobación antes de escribir, editar o ejecutar comandos.

### Adjuntos y visión

Las imágenes se reducen a un lado máximo de 768 px y se convierten a JPEG antes
de la inferencia. PDF, DOCX, PPTX y texto pueden extraerse temporalmente con
`/documents/extract`; esto no los indexa.

### Voz

Los controles de `ChatInterface` usan capacidades del navegador cuando existen;
el respaldo local consulta `/api/rag/v1/voice/capabilities`,
`/api/rag/v1/voice/stt` y `/api/rag/v1/voice/tts`.

## Emparejar un navegador

Un navegador LAN debe vincularse antes de usar el chat Ollama o las APIs
privadas. Un código corto de un solo uso puede conceder `chat`, `read_private`
y `web`; las lecturas privadas incluyen RAG autorizado, historial sincronizado,
contexto de memoria y archivos del host.

1. En la PWA host, abre **Configuración → Dispositivo emparejado → Generar
   código de emparejamiento**.
2. En el otro equipo abre `https://IP-LOCAL-DEL-HOST:3334`, elige la opción de
   instalación existente, introduce el código, nombra el dispositivo y confirma.
3. Vuelve a la PWA host para revisar o revocar el equipo. Si quieres, instala la
   PWA desde el menú del navegador.

Antes de abrir la URL LAN, confía en el certificado público que muestra
`trinaxai network`. El instalador puede confiar en él en el anfitrión, pero los
teléfonos y tablets necesitan una CA/perfil de confianza separado. Consulta la
[guía de pairing LAN y confianza HTTPS](../docs/NETWORK_PAIRING.es.md).

El pairing nunca concede `index`, `system`, `agent` ni `agent_yolo`. Las
mutaciones de índice, memoria/configuración, el workspace del Agente, la gestión
de modelos, servicios y dispositivos, y la restauración total exigen abrir
`https://localhost:3334` en el host. Ni credenciales admin ni tokens antiguos
con scopes retirados evitan esta frontera. La CLI usa `chat,read_private` por defecto.

La PWA conserva las credenciales nuevas del dispositivo en una cookie
`HttpOnly; SameSite=Strict` con alcance `/api/rag`, muestra dispositivo/scopes y
permite autorrevocación. Un bearer legacy guardado en el navegador solo se envía
durante la migración explícita de `/v1/pairing/me` y después se elimina. El host
puede revisar/revocar con `trinaxai pair list` y `trinaxai pair revoke ID`.
Pairing identifica un dispositivo, no una cuenta de usuario.

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

- Manifests localizados: `/manifest.en.webmanifest` y `/manifest.es.webmanifest` mantienen los metadatos y accesos directos en el idioma elegido; el shell React cambia el manifest cuando cambia `tc-lang`.
- La pantalla offline es un HTML bilingüe independiente que usa `tc-lang` o el idioma del navegador sin cargar React.
- `CacheFirst` para JS/CSS e imágenes locales.
- `NetworkFirst` solo para salud pública; datos privados de API no entran en el runtime cache.
- Fallback de navegación a `/index.html`, excepto rutas `/api/*`.
- Comprobación de actualizaciones cada hora y aviso mediante `PwaUpdater`.

“Offline” significa que puede abrir el shell y recursos ya cacheados. Generar respuestas, indexar, usar voz del backend o consultar datos no cacheados necesita que los servicios locales estén disponibles.

## Documentación integrada

Abre **Configuración → Documentación** para consultar la guía bilingüe sin salir de la PWA. Incluye introducción, instalación, configuración, modelos, indexación, workspaces del Agente, Internet e investigación, archivos y colecciones, seguridad, nociones de API, instalación como PWA, solución de problemas y contribución.

La guía integrada está pensada para tareas rápidas y pantallas pequeñas. Cuando un aviso ofrezca **Abrir indexación**, **Reintentar**, **Encender IA** o **Abrir configuración**, usa esa acción primero. La documentación del repositorio sigue siendo la fuente completa para contratos y valores exactos: consulta la [guía de solución de problemas](../docs/TROUBLESHOOTING.es.md), la [referencia de API](../docs/API_REFERENCE.es.md), la [referencia de configuración](../docs/CONFIGURATION.es.md) y el [hub documental](../docs/README.es.md) cuando integres u operes el backend.

## Configuración, HTTPS y seguridad

Consulta la [referencia completa de configuración](../docs/CONFIGURATION.es.md). Las variables `VITE_TRINAXAI_*` se fijan al construir; los destinos `TRINAXAI_RAG_TARGET` y `TRINAXAI_OLLAMA_TARGET` se leen al ejecutar el gateway.

El gateway usa `chat-pwa/certs/trinaxai-local.pfx` o el par `chat-pwa/certs/localhost-key.pem`/`chat-pwa/certs/localhost.pem`. Sin esos archivos solo sirve HTTP en loopback; una interfaz no loopback falla de forma segura salvo que se establezca explícitamente `TRINAXAI_ALLOW_INSECURE_HTTP=1` para una red de pruebas confiable. Para LAN instala en cada dispositivo la CA pública que muestra `trinaxai network`; no desactives la verificación del certificado. Nunca confirmes certificados o claves.

El gateway valida capability admin/de dispositivo, elimina identidad de proxy
aportada por cliente y firma el peer original para `/api/rag`; FastAPI solo
acepta esa identidad desde loopback. `/api/ollama` tiene allowlist fija, rate limit acotado y
lock de inferencia cross-process. Chat/generación exige `chat`; pull y borrado
de modelos exigen un peer loopback real. Las lecturas privadas de FastAPI exigen
autorización y las mutaciones del host procedencia loopback verificada.
`/api/system/*` también es loopback-only antes de ejecutar acciones fijas.
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

Al añadir texto de interfaz, incorpora claves equivalentes en español e inglés en `src/i18n/translations.ts`. Si cambia un contrato HTTP, actualiza el dominio `src/lib/api_*.ts` correspondiente (y la fachada `api.ts` si cambia su exportación pública), sus pruebas de parser y la referencia de API.

## Problemas comunes

- **Backend offline:** abre `/api/rag/health` desde el origen de la PWA y ejecuta `trinaxai doctor`. Consulta la [guía completa de solución de problemas](../docs/TROUBLESHOOTING.es.md).
- **Ollama offline:** comprueba `ollama list` y `/api/ollama/api/tags`.
- **Interfaz antigua:** aplica el aviso de actualización o elimina service worker y datos del sitio.
- **El teléfono no usa una función protegida:** empareja desde el host para
  `chat`, `read_private` o `web`. Indexación, Agente, modelos, dispositivos y
  administración del sistema se realizan desde `https://localhost:3334` en el host.
- **Micrófono:** revisa permiso, contexto seguro y `/api/rag/v1/voice/capabilities`.
- **El gateway sirve HTTP:** instala/genera los certificados locales esperados; HTTP es fallback solo para loopback.
