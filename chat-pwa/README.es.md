<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 💬 PWA de Chat
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.3.0"><img src="https://img.shields.io/badge/version-1.3.0-006bbd" alt="Stable release: 1.3.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="../docs/README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="../docs/CHANGELOG.es.md">Cambios</a></sub></p>

Frontend 1.3.0 de TrinaxAI construido con React 19, TypeScript, Tailwind CSS 4 y Vite 6, bajo licencia AGPL-3.0-or-later. Incluye chat directo con Ollama, RAG con citas, búsqueda web opcional, investigación profunda, agente con herramientas, análisis de imágenes, documentos, voz local, memoria y comportamiento de PWA instalable.

[Índice de documentación](../docs/README.es.md) · [Referencia de API](../docs/API_REFERENCE.es.md) · [Solución de problemas](../docs/TROUBLESHOOTING.es.md)

## Modelo de ejecución

```text
Navegador / PWA instalada :3334
  ├── /api/rag/*    ── gateway de producción ──> FastAPI :3333
  ├── /api/ollama/* ── gateway de producción ──> Ollama  :11434
  └── /api/system/* ── gateway de producción ──> service_manager.py
```

El navegador usa normalmente rutas `/api/*` del mismo origen. Así se evitan los problemas de contenido mixto y la mayoría de los de CORS, y Ollama no queda expuesto en la LAN. FastAPI atiende RAG, colecciones, memoria, indexación, extracción de documentos, voz de respaldo y estado compartido. El chat directo y la visión llegan a Ollama en streaming a través del proxy.

## Requisitos previos

- Node.js 22 o superior y npm; se recomienda una versión LTS activa.
- Chrome 111+, Safari 16.4+ o Firefox 128+ para los estilos de Tailwind CSS 4.
- Una instancia de Ollama en ejecución para chat/visión.
- El backend Python para RAG, indexación, memoria, estado compartido y voz del servidor.
- Modelos configurados en el asistente de bienvenida o en el entorno.

Para una instalación completa usa el instalador de la raíz del repositorio. Para desarrollar solo el frontend:

```bash
cd chat-pwa
npm install
npm run dev
```

Abre `https://localhost:3334` cuando existan certificados locales; sin ellos, el gateway recurre a HTTP solo en loopback. Un host no loopback falla de forma segura salvo que se establezca explícitamente `TRINAXAI_ALLOW_INSECURE_HTTP=1` para una red de pruebas confiable. Para acceder por LAN, instala en cada dispositivo la CA pública que muestra `trinaxai network`; no desactives la verificación del certificado. Consulta la [guía de pairing LAN y confianza HTTPS](../docs/NETWORK_PAIRING.es.md).

## Scripts

| Comando | Resultado |
|---|---|
| `npm run dev` | Servidor de desarrollo Vite con HMR en `127.0.0.1:3334`. Usa `TRINAXAI_PWA_HOST=0.0.0.0` solo para una prueba LAN HTTPS intencional. |
| `npm run build` | Verificación TypeScript, build de producción de Vite en `dist/` y bundle del gateway de producción. |
| `npm run serve` | Sirve `dist/` en el puerto 3334 con el gateway Node de producción. |
| `npm run preview` | Alias de compatibilidad de `npm run serve`. |
| `npm test` | Ejecuta Vitest y las pruebas de integración del gateway de producción. |
| `npm run check:bundle` | Comprueba el presupuesto del bundle frontend generado. |
| `npm run lint` | Ejecuta ESLint. |
| `npx tsc --noEmit` | Verifica tipos sin construir. |

Los límites del bundle son 350 KiB por archivo JavaScript, 1536 KiB de
JavaScript total, 140 KiB de CSS y 4096 KiB para todos los archivos del build.

El servidor de desarrollo escucha en loopback por defecto. Para una prueba LAN
intencional, establece `TRINAXAI_PWA_HOST=0.0.0.0`, usa HTTPS y vincula cada
navegador remoto; nunca expongas el servidor de desarrollo ni los puertos del
backend a Internet.

## Organización del código

```text
src/
├── main.tsx                 providers y registro del service worker
├── App.tsx                  estado de página, navegación, onboarding e historial de chat
├── components/
│   ├── ChatInterface.tsx    frontera estable del componente de chat
│   ├── chat/ChatInterfaceView.tsx renderizado y layout del chat
│   ├── agent/                vista y contratos compartidos de Agent
│   ├── ChatSidebar.tsx      sesiones, carpetas, búsqueda y exportación
│   ├── Settings.tsx         general, búsqueda, índice, prompts, memoria, métricas y controles avanzados
│   ├── KnowledgeBrowser.tsx fuentes y chunks indexados
│   ├── Docs.tsx             guía de usuario integrada
│   └── PwaUpdater.tsx       aviso de actualización
├── hooks/
│   ├── useChatHistory.ts    persistencia de sesiones y carpetas
│   ├── useChatTurn.ts       enrutamiento de turnos y armado de contexto
│   ├── useChatDocuments.ts  extracción de documentos y jobs de indexación
│   ├── useChatAttachments.ts ciclo de vida de adjuntos de imagen/archivo
│   ├── useChatVoice.ts      ciclo de voz y respuestas habladas
│   ├── useChatController.ts estado del chat y composición de la UI
│   ├── useChatSend.ts       envío de mensajes y despacho de rutas
│   ├── useChatMessageActions.ts edición, regeneración y continuación
│   ├── useAgentController.ts ejecución, aprobaciones e historial de Agent
│   ├── useAgentVoice.ts     ciclo de dictado de Agent
│   └── useStreamChat.ts     ciclo de streaming y cancelación
├── lib/
│   ├── api.ts               fachada pública estable de la API
│   ├── api_*.ts             dominios HTTP, llamadas a modelos, streams y documentos
│   ├── config.ts            resolución de URLs same-origin
│   ├── sharedState.ts       sincronización de estado entre dispositivos respaldada por el host
│   ├── chatAttachments.ts   almacenamiento de adjuntos en IndexedDB
│   └── userProfile.ts       perfil local y utilidades de memoria de conversación
├── services/voice.ts        adaptadores de voz Web Speech y FastAPI
├── i18n/                    traducciones español/inglés y provider
└── theme/                   provider de tema claro/oscuro
```

`Settings`, `OnboardingWizard`, `Docs` y `KnowledgeBrowser` se cargan bajo demanda. Rollup genera chunks separados para React, motion, Markdown e iconos.

## Flujos principales

### Ollama directo

`streamOllama()` envía a `/api/ollama/api/chat` y procesa JSON delimitado por saltos de línea. Antes de enviar, el cliente compacta el historial largo y elige un modelo de forma heurística entre los modelos general, de código, profundo y rápido configurados. Los modelos ausentes pueden descargarse mediante Ollama.

### RAG

`streamRag()` envía mensajes con forma OpenAI a `/api/rag/v1/chat/completions`. Procesa Server-Sent Events, incluidos los metadatos `trinaxai` y las citas `trinaxai_sources`. Los IDs de las colecciones activas viajan con la solicitud. Si la colección seleccionada está vacía o no existe, la PWA ofrece **Abrir indexación**; indexa una fuente desde **Configuración → Indexación**, espera el estado `completed` y reintenta.

### Búsqueda web, investigación y agente

- El modo Internet consulta DuckDuckGo, Brave Search o SearXNG, muestra las fuentes y realiza lecturas acotadas de páginas públicas protegidas contra SSRF.
- La investigación profunda descompone una pregunta, combina la web con conocimiento local autorizado y sintetiza una respuesta con fuentes.
- La vista Agent comparte motor con la CLI, confina el acceso a archivos al workspace seleccionado y pide aprobación antes de escribir, editar o ejecutar comandos.

### Adjuntos y visión

- Las imágenes se reducen a un lado máximo de 768 px y se codifican como JPEG antes de la inferencia de visión en Ollama.
- Los documentos de texto, Markdown, PDF, DOCX y PPTX pueden extraerse temporalmente con `/documents/extract`; la extracción temporal no los agrega al índice RAG.
- Los adjuntos se suben primero al host para que los chats sincronizados puedan abrirlos en otro dispositivo. IndexedDB es el respaldo offline o para backends antiguos; los mensajes del chat conservan metadatos y claves de almacenamiento.
- La importación de carpetas filtra en el navegador las extensiones admitidas, las sube a `/system/index-upload` y luego consulta el endpoint del job.

### Voz

Los controles de voz de `ChatInterface` prefieren las capacidades de voz del navegador cuando existen y recurren a:

- `GET /api/rag/v1/voice/capabilities`
- `POST /api/rag/v1/voice/stt` para la transcripción local con Whisper
- `POST /api/rag/v1/voice/tts` para un backend TTS disponible localmente

La disponibilidad de voz varía según el sistema operativo, los permisos del navegador, los extras de Python instalados y el soporte de audio local. Consulta la respuesta de la API en lugar de asumir que existe un motor TTS concreto.

## Emparejar un navegador

Un navegador LAN puede elegir **Configurar como dispositivo nuevo** para recibir
una sesión limitada a chat/búsqueda web sin importar estado privado, o vincularse
antes de usar APIs privadas. Un código corto de un solo uso puede conceder
`chat`, `read_private` y `web`; las lecturas privadas incluyen RAG autorizado,
historial sincronizado, contexto de memoria y archivos del host.

1. En la PWA host, abre **Configuración → Avanzado → Dispositivo emparejado → Generar
   código de emparejamiento**.
2. En el otro equipo abre `https://IP-LAN-DEL-HOST:3334`, elige la opción de
   instalación existente, introduce el código, nombra el dispositivo y vincúlalo.
3. Vuelve a la PWA host para revisar o revocar el equipo. Si quieres, instala la
   PWA desde el menú del navegador.

La opción de dispositivo nuevo permite chatear y usar búsqueda web, pero a propósito
no puede restaurar historial, memoria, conocimiento RAG ni archivos del host hasta
que se vincule.

Antes de abrir la URL LAN, confía en el certificado público que muestra
`trinaxai network`. El instalador puede confiar en él en el anfitrión, pero los
teléfonos y tablets necesitan una CA/perfil de confianza separado. Sigue la
[guía de pairing LAN y confianza HTTPS](../docs/NETWORK_PAIRING.es.md).

El pairing nunca concede `index`, `system`, `agent` ni `agent_yolo`. Las
mutaciones de índice, memoria/configuración, el workspace del Agente, la gestión
de modelos, los controles de ciclo de vida, la restauración total y la gestión de
otros dispositivos exigen abrir `https://localhost:3334` en el host. Ni las
credenciales admin ni los tokens de dispositivo antiguos con scopes retirados
evitan esta frontera. La CLI usa `chat,read_private` por defecto al emparejar.

La PWA conserva las credenciales nuevas del dispositivo en una cookie
`HttpOnly; SameSite=Strict` con alcance `/api`, muestra el dispositivo y sus
scopes, y permite autorrevocación. Un bearer legacy guardado en el navegador solo
se envía durante la migración explícita de `/v1/pairing/me` y después se elimina.
El host puede revisar o revocar cualquier dispositivo con `trinaxai pair list` y
`trinaxai pair revoke ID`. El pairing identifica un dispositivo, no una cuenta de
usuario.

La memoria persistente se recupera por consulta. Antes de cada turno, la PWA pide a
`POST /v1/memory/context` las entradas activas relevantes y envuelve el resultado
en un bloque explícito de datos no confiables. Nunca inyecta el resumen global de
memoria ni el scratchpad local `tc-project-memory`. El panel de memoria muestra
tipo, provenance, expiración y edición, y exige confirmación antes de borrar.

## Estado y propiedad de los datos

El frontend usa varias capas de almacenamiento a propósito:

| Capa | Datos | Notas |
|---|---|---|
| Estado de React | Página actual, composer, stream activo | Efímero. |
| `localStorage` | Sesiones, carpetas, modelos, tema, idioma, prompts, onboarding | Estado principal del navegador bajo claves `tc-*`. |
| FastAPI `chat_attachments/` | Blobs de adjuntos compartidos por el host | Almacenamiento preferido para adjuntos nuevos. |
| IndexedDB | Respaldo offline de adjuntos | Base de datos `trinaxai-chat-files`. |
| FastAPI `app_state.json` | Valores `tc-*` seleccionados | Permite sincronizar navegadores del mismo host. |
| Almacenamiento RAG de FastAPI | Colecciones, chunks, memoria, métricas | No pertenece al frontend. |

`sharedState.ts` usa una revisión monótona del servidor y ETag. Las mutaciones del navegador se persisten como operaciones incrementales `set`/`delete` con un ID estable de dispositivo; ante un `409`, las operaciones pendientes se rebasan sobre la revisión canónica antes de reintentar. El sondeo periódico recibe `304` cuando no cambia nada y no vuelve a hashear ni a subir un snapshot completo. Las sesiones y sus registros de eliminación conservan la fusión estructurada. La sincronización empieza en segundo plano para que un backend RAG no disponible no bloquee el arranque. El acceso exige `read_private` (o privilegio admin/local); sigue siendo sincronización entre dispositivos, no un sistema de cuentas multiusuario.

## Comportamiento PWA

`vite-plugin-pwa` genera el manifest y el service worker Workbox.

- Modos de visualización: `standalone`, con preferencia por `window-controls-overlay` cuando esté disponible.
- Manifests localizados: `/manifest.en.webmanifest` y `/manifest.es.webmanifest` mantienen los metadatos y accesos directos en el idioma elegido; el shell React cambia el manifest cuando cambia `tc-lang`.
- Accesos directos: Nuevo chat y Configuración (localizados en cada manifest).
- La pantalla offline es un HTML bilingüe independiente que usa `tc-lang` o el idioma del navegador sin cargar React.
- Precaché: JS/CSS/HTML construidos más iconos, fuentes e imágenes que coinciden con los patrones configurados.
- Caché en ejecución: `CacheFirst` para JS/CSS construidos e imágenes locales, y
  `NetworkFirst` solo para la respuesta pública de salud. Los datos privados de la API
  no se guardan en los runtime caches de Workbox.
- Fallback de navegación: `/index.html`, excepto `/api/*`.
- Actualizaciones: la app comprueba el service worker cada hora y muestra `PwaUpdater` cuando hace falta recargar.

“Offline” significa que el shell de la aplicación y las respuestas de solo lectura ya cacheadas pueden cargarse. Las respuestas nuevas de IA, la indexación, la voz de respaldo y las operaciones de conocimiento no cacheadas siguen necesitando que los servicios locales estén disponibles.

## Documentación integrada

Abre **Configuración → Documentación** para consultar la guía bilingüe sin salir de la PWA. Incluye introducción, instalación, configuración, modelos, indexación, workspaces del Agente, Internet e investigación, archivos y colecciones, seguridad, nociones de API, instalación como PWA, solución de problemas y contribución.

La guía integrada está pensada para tareas rápidas y es cómoda de leer desde un teléfono. Cuando un aviso ofrezca **Abrir indexación**, **Reintentar**, **Encender IA** o **Abrir configuración**, usa esa acción primero. La documentación del repositorio sigue siendo la fuente completa para contratos y valores exactos: consulta la [guía de solución de problemas](../docs/TROUBLESHOOTING.es.md), la [referencia de API](../docs/API_REFERENCE.es.md), la [referencia de configuración](../docs/CONFIGURATION.es.md) y el [hub documental](../docs/README.es.md) cuando integres u operes el backend.

## Entorno y certificados

La resolución de URLs del frontend vive en `src/lib/config.ts`. Consulta la [referencia completa de configuración](../docs/CONFIGURATION.es.md).

| Variable | Propósito |
|---|---|
| `VITE_TRINAXAI_RAG_BASE` / `VITE_TRINAXAI_OLLAMA_BASE` | Bases del navegador en producción. |
| `VITE_TRINAXAI_DEV_RAG_BASE` / `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Bases del navegador en desarrollo. |
| `TRINAXAI_RAG_TARGET` / `TRINAXAI_OLLAMA_TARGET` | Destinos del gateway de producción, del lado del servidor. |
| `VITE_TRINAXAI_VISION_MODEL` | Modelo de visión rápido. |
| `VITE_TRINAXAI_KEEP_ALIVE` | Keep-alive predeterminado del chat directo (opcional; el cliente usa `10m` por defecto). |

Las variables `VITE_TRINAXAI_*` se fijan al construir; los destinos `TRINAXAI_RAG_TARGET` y `TRINAXAI_OLLAMA_TARGET` se leen al ejecutar el gateway.

El gateway carga primero `chat-pwa/certs/trinaxai-local.pfx`, o `chat-pwa/certs/localhost-key.pem` junto con `chat-pwa/certs/localhost.pem`. Los archivos de certificado son secretos/artefactos locales y no deben confirmarse. Sin esos archivos, HTTP solo se permite en loopback; un host no loopback falla de forma segura salvo que se establezca explícitamente `TRINAXAI_ALLOW_INSECURE_HTTP=1` para una red de pruebas confiable. Si el host cambia de red LAN o recibe una IP nueva, ejecuta `trinaxai network refresh` antes de usar la PWA desde otro dispositivo.

## Frontera de control del sistema

El gateway personalizado valida la capability admin o de dispositivo emparejado,
elimina las cabeceras de identidad de proxy aportadas por el cliente y adjunta a
`/api/rag` un peer original fresco firmado con HMAC. FastAPI solo acepta esa
identidad desde loopback. `/api/ollama` tiene una allowlist fija de métodos/rutas,
su propia ventana de límite de tasa y un lock de inferencia entre procesos. El
chat y la generación exigen `chat`; la descarga y el borrado de modelos exigen un
peer loopback real. Las lecturas privadas de FastAPI exigen autorización, mientras
que las mutaciones del host exigen procedencia loopback verificada.
`/api/system/*` también es solo loopback antes de invocar acciones fijas de ciclo de vida.

No expongas el gateway directamente a Internet. Usa una VPN o un terminador TLS
autenticado, y mantén tanto FastAPI como Ollama enlazados a loopback.

## Pruebas y contribución

```bash
cd chat-pwa
npm test
npx tsc --noEmit
npm run build
```

Las pruebas cubren los helpers de API, el parseo SSE/NDJSON, las cadenas de texto y el hook de streaming. Para un cambio que abarque todo el stack, ejecuta también desde la raíz del repositorio:

```bash
make test
make readiness
```

Al cambiar texto de la interfaz, añade las claves equivalentes en español e inglés en `src/i18n/translations.ts`. Al cambiar la forma de una respuesta, actualiza juntos el dominio `src/lib/api_*.ts` correspondiente (y la fachada `api.ts` si cambia su exportación pública), sus pruebas de parser y la referencia de API del repositorio.

## Solución de problemas

- **El backend aparece offline:** abre `/api/rag/health` desde el origen de la PWA y revisa `trinaxai doctor`.
- **Ollama aparece offline:** revisa `ollama list` y `/api/ollama/api/tags` desde el origen de la PWA.
- **Interfaz antigua tras un build:** usa el aviso de actualización o desregistra el service worker y borra los datos del sitio en las herramientas de desarrollo del navegador.
- **Un dispositivo LAN no puede usar una función protegida:** elige la configuración
  de dispositivo nuevo para `chat`/`web`, o empareja desde el host para
  `read_private` y el estado sincronizado. Realiza la administración de
  indexación, Agente, modelos, dispositivos y sistema desde
  `https://localhost:3334` en el host.
- **Falla el micrófono:** verifica el permiso del navegador y el contexto seguro, y luego inspecciona `/api/rag/v1/voice/capabilities`.
- **HTTPS pasa a HTTP:** genera/instala certificados locales; el gateway solo habilita HTTPS cuando existen los archivos de certificado.
