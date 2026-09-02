<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🏗️ Arquitectura
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="ARCHITECTURE.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

## Visión General

```
Navegador LAN ── HTTPS ──► Gateway PWA :3334 ──► chat Ollama permitido
                           └─ token emparejado ─► RAG/capacidades privadas
                                                    │
                         HMAC peer/método/ruta firmada│ llamadas allowlist
                                                    ▼
CLI local ────────────────────────────────► FastAPI :3333 ──► Ollama :11434
                                             loopback          loopback
                                                │
                                                └──► LlamaIndex · vector + BM25
```

TrinaxAI es un **stack local de tres capas**:

1. **Frontend PWA** (React 19 + TypeScript, compilado con Vite) en el puerto 3334
2. **API RAG** (FastAPI + LlamaIndex) en loopback:3333
3. **Ollama** (entorno de ejecución de modelos) en loopback:11434

El gateway PWA de producción es el pequeño servidor Node de `chat-pwa/server.mjs`;
el proxy integrado de Vite se usa solo durante el desarrollo. El gateway en 3334
es la frontera orientada a LAN: reenvía a ambos servicios loopback, firma el
peer original verificado para FastAPI y solo publica las operaciones Ollama
necesarias. Inferencia/datos permanecen en el host por defecto; instalación,
modelos, investigación opt-in y endpoints externos usan red.

---

## Arquitectura de Componentes

### `config.py` — Centro de Configuración Central

La fuente única de verdad para todos los subsistemas. Define:

- **Flota de modelos** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP` y `MODEL_FAST`; los nombres concretos dependen del perfil activo y se pueden sobrescribir en `.env`.
- **Perfiles de hardware** — conscientes de CPU/RAM/GPU (`8gb`/`16gb`/`32gb`/`64gb`), guardados en `storage/hardware_profile.json`
- **Presets de embeddings** — Qwen3 Embedding 0.6B/4B/8B según perfil, nomic lite, all-minilm rápido
- **Funciones de fábrica** — `make_llm()`, `make_embed()`, `make_reranker()`
- **Enrutador automático** — clasificador heurístico `route_model()` (sin llamada al LLM)
- **Reglas de archivos** — qué indexar, qué omitir, tamaños de chunks por perfil

### `app/` — Backend FastAPI Modular

`app/main.py` es dueño de la aplicación, middleware, manejadores de errores e
inicialización por lifespan. `app/routes/` define HTTP, `app/schemas/` los
contratos y `app/services/` la lógica por dominio. El único estado mutable del
motor está en `app/services/engine_state.py`. `rag_api.py` queda como fachada
compatible.

La superficie RAG/runtime está separada por responsabilidad: `rag_service.py`
coordina la política de cada request y la recuperación, `rag_generation.py`
contiene las primitivas de respuesta del modelo, `rag_streaming.py` gestiona el
SSE sync/async y la cancelación, y `shared_runtime.py` conserva una fachada
legacy pequeña y compatible. `runtime_engine.py`, `runtime_index.py` y
`runtime_usage.py` aíslan motor, manifiestos y persistencia de uso.

Subsistemas clave:

| Característica | Implementación |
|---|---|
| **Hybrid retrieval** | Vectorial (Qwen3 Embedding) + BM25 (palabras clave) → fusión por rango recíproco |
| **Reranking** | Cross-encoder opcional (bge-reranker-v2-m3) cuando se activa |
| **Colecciones** | Espacios de nombres separados dentro del mismo almacén vectorial |
| **Detección de proyectos** | Heurística a partir de rutas de archivos y la consulta del usuario |
| **Memoria** | Hechos/preferencias/decisiones/notas con provenance y expiración; cada turno recupera solo entradas activas relevantes |
| **Investigación** | Retrieval local/web multipasada; páginas acotadas con provenance `full_page` o `snippet_only` |
| **Pairing de dispositivos** | Códigos de un uso emiten capabilities revocables con scopes; solo persisten hashes con clave |
| **Vigilante de archivos** | watchdog del sistema de archivos para re-indexación automática |
| **Límite de tasa** | Token bucket monotónico por IP verificada/bucket; capacidad 30 y recarga total en 60 s |
| **Estadísticas de uso** | Analítica local basada en JSONL |
| **Sincronización de estado** | Operaciones schema-v2, deletes explícitos, revisión server, ETag/CAS y merge de conflicto |

### `index.py` — Punto de Entrada del Indexador

`index.py` sigue siendo el punto de entrada CLI y la fachada compatible. Sus
responsabilidades están separadas en `trinaxai_index_documents.py` (descubrimiento
y extracción de formatos), `trinaxai_index_state.py` (manifiestos, fingerprints,
diffs y actualizaciones de nodos) y `trinaxai_index_storage.py` (publicación y
recuperación durable). Las funciones históricas siguen disponibles a través de
`index.py`, sin migración obligatoria para scripts o tests.

- **Recolección de archivos** — Poda agresiva de directorios que omite `node_modules`, `.git`, `venv`, etc.
- **Chunking con conciencia AST** — `CodeSplitter` para 16 lenguajes de código y `SentenceSplitter` como fallback de texto para formatos adicionales
- **Modo incremental** — Fingerprint BLAKE2b-256 más versiones de extractor/chunker/embedding
- **Colecciones multi-source** — Cada raíz sincronizada tiene `source_id` estable; varias raíces pueden repetir ruta relativa
- **Publicación recuperable** — Índice y manifest se preparan juntos, publican con journal/marker y revierten un commit interrumpido
- **Provenance** — Cada chunk incluye `collection_id`, `source_id`, ruta relativa y metadatos de origen

### `chat-pwa/` — Frontend PWA en React

Los componentes TypeScript construidos con Tailwind CSS y framer-motion incluyen:

| Componente | Propósito |
|---|---|
| `ChatInterface` | Frontera estable que delega estado y renderizado en módulos de chat enfocados |
| `ChatInterfaceView` | Layout y composición visual del chat |
| `useChatController` | Estado del chat, preferencias, voz y composición de UI |
| `useChatSend` | Envío de mensajes, comandos slash y enrutamiento |
| `useChatMessageActions` | Edición, regeneración y continuación de mensajes |
| `useChatTurn` | Enrutamiento del turno, contexto, investigación y continuaciones |
| `useChatDocuments` | Extracción, jobs de indexación y contexto de documentos adjuntos |
| `useChatAttachments` | Arrastrar/pegar, preview, descarga y ciclo de vida de adjuntos |
| `useChatVoice` | Reconocimiento, voz local y respuestas habladas |
| `AgentInterface` | Composición de Agent; controlador, vista y voz están separados |
| `useAgentController` | Ejecución del agente, aprobaciones, historial y acciones de mensajes |
| `AgentInterfaceView` | Renderizado del historial, controles, conversación y compositor |
| `ChatSidebar` | Historial, carpetas, búsqueda y flujos de exportación |
| `Settings` | Controles de modelos locales, indexación, prompts, memoria y estadísticas |
| `KnowledgeBrowser` | Explora chunks indexados por colección→archivo→chunk |
| `Sources` | Tarjetas de citación con archivo, proyecto, fragmento y puntuación |
| `OnboardingWizard` | Configuración inicial de perfil y modelos |
| `Docs` | Documentación bilingüe integrada en la app |

**Stack tecnológico**: React 19, Vite 6, TypeScript, Tailwind CSS, vite-plugin-pwa, react-markdown

### `trinaxai_cli/` — Interfaz de Terminal

Paquete Python con `chat`, `agent`, `index`, `browse`, `research`, `memory`,
`collections`, `watch`, `export`, `obsidian`, `pair` y `doctor`.

Usa `httpx` para las llamadas a la API y `rich` para el formato en terminal.

### `trinaxai_agent/` — Núcleo Compartido del Agente

El motor independiente de la interfaz, las herramientas sandbox y la
extracción de documentos viven en este paquete para que API y CLI compartan una
sola implementación. `trinaxai_cli.agent` permanece como superficie de
compatibilidad para integraciones existentes.

### `service_manager.py` — Supervisor Multiplataforma

Abstrae el ciclo de vida de los servicios en distintos sistemas operativos:
- **Linux**: systemd con fallback a subprocess
- **macOS**: launchctl con fallback a subprocess
- **Windows**: Subprocess directo + bucle de auto-reinicio con `--watch`

---

## Flujo de Datos del Chat

```
El usuario escribe una consulta en la PWA
  │
  ├─ ¿Slash command? → manejador integrado (ej., /index, /memory)
  ├─ ¿Imagen adjunta? → routeVisionModel() → streamOllamaVision()
  ├─ ¿Docs adjuntos? → guardar referencia; extraer texto acotado para este turno
  │
  └─ Texto normal:
       │
       ├─ Motor RAG:
       │    POST /v1/chat/completions → FastAPI
       │    │
       │    ├─ route_model(query) → selecciona el mejor modelo Ollama (heurística)
       │    ├─ prepare_query() → enriquece con el turno anterior del usuario
       │    ├─ _fusion_retriever.retrieve() → búsqueda híbrida vector+BM25
       │    ├─ detect_project() → filtra por proyecto mencionado
       │    ├─ filtro de colecciones → acota a las colecciones activas
       │    ├─ reranker → reordena por relevancia del cross-encoder
       │    ├─ get_response_synthesizer().synthesize() → LLM con contexto
       │    └─ Stream SSE + citas de fuentes → de vuelta a la PWA
       │
       └─ Motor Ollama:
            routeOllamaModel() → Ollama /api/chat (JSON lines)
            → el ciclo de vida del modelo sigue el valor configurado de keep_alive
```

---

## Flujo de Indexación

```
index.py arranca
  │
  ├─ collect_files(root) → os.walk con poda agresiva
  │
  ├─ SourceContext(root, collection_id, source_id)
  │
  ├─ current_state(paths) → fingerprints de contenido + pipeline
  │
  ├─ read_manifest() → claves (collection:source:path)
  │
  ├─ Diff: new_files, changed, deleted
  │
  ├─ load_docs(paths) → objetos Document con metadatos
  │
  ├─ build_nodes(docs) → CodeSplitter (AST) o SentenceSplitter
  │
  ├─ Embed nodos (Qwen3 Embedding, sin LLM necesario)
  │
  └─ staging índice+manifest → publish con journal → marker de generación
```

---

## Modelo de Seguridad

| Capa | Mecanismo |
|---|---|
| **Red** | FastAPI/Ollama en loopback; solo el gateway PWA mira a LAN |
| **Identidad gateway** | Peer/método/ruta con HMAC fresca; backend ignora forwarding ordinario |
| **Identidad de dispositivo** | Pairing de un uso; bearer revocable con scopes guardado en una cookie `HttpOnly; SameSite=Strict`; solo los valores legacy se migran desde el almacenamiento web |
| **Endpoints protegidos** | Operaciones de bajo riesgo usan credenciales de dispositivo/admin; administrar el host exige loopback original verificado; credenciales inválidas fallan cerrado |
| **Fachada Ollama** | Allowlist método/ruta, autorización, token bucket monotónico y lock de inferencia |
| **Agente** | Raíces registradas, paths/symlinks, bubblewrap Linux sin red y fallo cerrado sin aislamiento |
| **TLS** | Los servicios administrados pueden usar certificados locales; `TRINAXAI_TLS_VERIFY` controla verificaciones salientes concretas |
| **Sudoers** | Comando exacto opcional a wrapper root-owned, nunca scripts editables del repo |
| **Datos** | Host por defecto; búsqueda web, descargas y endpoints remotos son rutas de red explícitas |

---

## Estructura de Almacenamiento

```
storage/
├── docstore.json          # Almacén de documentos de LlamaIndex
├── index_store.json       # Metadatos de índice de LlamaIndex
├── vectors.sqlite3        # Instantánea vectorial transaccional embebida
├── *_vector_store.json    # Archivos vectoriales antiguos, solo para migración
├── graph_store.json       # Almacén de grafo de LlamaIndex
├── manifest.json          # Fuente/ruta→fingerprints de contenido + pipeline
├── .index-generation.json # Marker durable de la generación activa
├── .proxy_secret          # Clave HMAC privada gateway/backend
├── .device_secret         # Clave privada para hashes de tokens/códigos
├── device_pairing.json    # Dispositivos con scope y hashes con clave
├── collections.json       # Metadatos de colecciones
├── usage.jsonl            # Estadísticas de uso (JSON lines)
├── app_state.json         # Valores schema-v2 + revisión monotónica
├── chat_attachments/      # Archivos de chat sincronizados por el host
├── usage_summary.json     # Agregado cacheado de uso
└── user_memory*.json      # Memorias/resumen cuando existen
```

---

## Decisiones de Diseño Clave

- **Sin LLM durante la indexación** — solo embeddings, ahorra RAM
- **Chunking AST** — respeta los límites de funciones/clases en el código
- **Búsqueda híbrida** — la fusión de vector + BM25 captura tanto coincidencias semánticas como exactas
- **Enrutamiento automático heurístico** — sin llamada al LLM, instantáneo y gratuito
- **Enrutamiento por capacidad** — las consultas públicas usan búsqueda web, el historial de proyectos propios usa RAG, las solicitudes complejas con varias fuentes usan investigación profunda y las creaciones ejecutables usan Agent
- **Puerta de aclaración del Agent** — una creación web incompleta pregunta por negocio, secciones, estilo visual y tecnología antes de modificar el workspace
- **Colecciones** — concepto de primera clase en todo el stack
- **PWA en lugar de Electron** — más ligera, compatible con móviles, sin cadena de herramientas nativa
- **Índice incremental transaccional** — fingerprints de contenido/pipeline,
  lock cross-process y publicación recuperable por generación
- **Identidad multi-source explícita** — `source_id` evita reemplazos/borrados
  cruzados entre archivos homónimos de raíces distintas
- **Sync versionado** — localStorage sigue como store cliente; revisiones,
  operaciones y deletes explícitos evitan snapshots ciegos
- **Pairing con scopes** — una ceremonia breve autorizada por local/admin emite
  una capability revocable sin distribuir el secreto administrador

---

## Guía para Contribuidores: Qué Tocar Según la Tarea

Esta sección ayuda a los contribuidores a encontrar los archivos correctos para tareas comunes.

### Chat / IA Conversacional

| Qué cambiar | Dónde |
|---|---|
| Lógica del endpoint de chat | `app/routes/chat.py` + `app/services/rag_service.py` |
| Recuperación RAG + síntesis | `app/services/rag_service.py` (`run_rag`, `prepare_query`) + `app/services/rag_generation.py` |
| Streaming SSE | `app/services/rag_streaming.py` + `chat-pwa/src/lib/api_streams.ts` (`api.ts` conserva la fachada pública) |
| Plantilla de prompt | `app/generation/prompts.py` (`GROUNDED_QA_TEMPLATE`) |
| Enrutamiento automático de modelos | `config.py` `route_model()` |
| Frontera de chat en frontend | `chat-pwa/src/components/ChatInterface.tsx` + `chat-pwa/src/components/chat/ChatInterfaceView.tsx` |
| Estado y envío del chat | `chat-pwa/src/hooks/useChatController.ts` + `chat-pwa/src/hooks/useChatSend.ts` |
| Acciones de mensajes | `chat-pwa/src/hooks/useChatMessageActions.ts` |
| UI y ejecución de Agent | `chat-pwa/src/components/agent/AgentInterfaceView.tsx` + `chat-pwa/src/hooks/useAgentController.ts` |
| Voz y contratos de Agent | `chat-pwa/src/hooks/useAgentVoice.ts` + `chat-pwa/src/components/agent/agentTypes.ts` |
| Hook de streaming en frontend | `chat-pwa/src/hooks/useStreamChat.ts` |

### Indexación / Pipeline RAG

| Qué cambiar | Dónde |
|---|---|
| Indexación de documentos | `index.py` (punto de entrada), `trinaxai_index_documents.py` (descubrimiento/extracción), `config.py` (configuración de chunking) |
| Estrategia de chunking | `index.py` + `trinaxai_index_documents.py` — `CodeSplitter` para código, `SentenceSplitter` para prosa |
| Modelo de embeddings | `config.py` `make_embed()` |
| Indexación incremental | `trinaxai_index_state.py` lógica de manifiestos/fingerprints + `config.py` `MANIFEST_PATH` |
| Publicación/recuperación transaccional | `trinaxai_index_storage.py` |
| Subida de índice (carpeta del navegador) | `app/routes/system.py` + `app/services/system_service.py` |
| Vigilante de archivos | `app/services/watcher_service.py` + `app/routes/watcher.py` |

### Sistema de Memoria

| Qué cambiar | Dónde |
|---|---|
| CRUD de memoria | `app/services/memory_service.py` |
| Resumen de memoria (LLM) | `app/services/memory_service.py` `_memory_refresh_sync()` |
| Memoria relevante del turno | `POST /v1/memory/context` + `app/services/memory_service.py::memory_context_for_query()`; delimitada como datos no confiables |
| Panel de memoria en frontend | `chat-pwa/src/components/MemoryPanel.tsx` |

### Colecciones de Conocimiento

| Qué cambiar | Dónde |
|---|---|
| CRUD de colecciones | `app/services/collection_service.py` |
| Endpoints de colecciones | `app/routes/collections.py` |
| Filtro de recuperación por colección | `app/services/rag_service.py` `_cached_retrieve()` |
| UI de colecciones en frontend | `chat-pwa/src/components/KnowledgeBrowser.tsx` |

### CLI

| Qué cambiar | Dónde |
|---|---|
| Punto de entrada CLI | `trinaxai_cli/app.py` |
| Subcomandos individuales | `trinaxai_cli/commands/*.py` |
| Configuración CLI | `trinaxai_cli/config.py` |
| Gestión de sesiones CLI | `trinaxai_cli/session.py` |
| Utilidades compartidas | `trinaxai_core.py` |

### Instaladores

| Qué cambiar | Dónde |
|---|---|
| Instalación Linux/macOS | `install.sh` |
| Instalación Windows (PowerShell) | `install.ps1` |
| Actualización | `update.sh` / `update.ps1` |
| Desinstalación | `uninstall.sh` / `uninstall.ps1` |
| Gestión de servicios | `service_manager.py` + `startup_ai.sh` / `shutdown_ai.sh` |

---

## Ejecución de Pruebas

### Backend (Python)

```bash
### Todas las pruebas del backend
.venv/bin/python -m pytest -q

### Archivos de prueba específicos
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
.venv/bin/python -m pytest tests/test_rag_api_reset_and_sources.py -v

### Métricas deterministas y evaluación golden contra API/resultados guardados
.venv/bin/python -m pytest tests/test_rag_metrics.py -v
.venv/bin/python scripts/evaluate_rag.py --api-url https://localhost:3333 \
  --token "$TRINAXAI_ADMIN_TOKEN" --output rag-eval-report.json

### Lint
.venv/bin/python -m ruff check .

### Verificación de tipos (mejor esfuerzo, no estricto)
.venv/bin/python -m py_compile rag_api.py config.py index.py
```

### Frontend (TypeScript/React)

```bash
cd chat-pwa
npx vitest run              # Pruebas unitarias
npx tsc --noEmit            # Verificación de tipos
npm run build               # Verificación de build de producción
```

### Auditoría Pre-lanzamiento

```bash
python3 scripts/public_readiness.py
```

### Atajos del Makefile

```bash
make test        # Pruebas backend + frontend
make lint        # Ruff + verificación de tipos TypeScript
make check       # Lint + test + audit + build
make audit       # Auditorías locales bloqueantes
```

---

## Zonas Sensibles de Seguridad

Estas áreas requieren cuidado extra al modificarlas:

| Zona | Riesgo | Mitigación |
|---|---|---|
| Endpoints `/system/*` | Control de procesos (inicio, apagado, recarga) | Guardián canónico: `app/security/admin_auth.py::authorize_system` |
| `/system/index-upload` | Escrituras en sistema de archivos | Prevención de path traversal, límites de tamaño, nombres saneados |
| `_factory_reset_runtime_state` | Eliminación de datos | Requiere cabecera de confirmación, solo limpia `storage/` y `local_sources/` |
| `authorize_system` | Bypass de control de acceso | Mantener la única implementación en `app/security/admin_auth.py` cubierta por pruebas |
| Configuración CORS | Acceso cross-origin | Por defecto: solo localhost + LAN; configurable vía `TRINAXAI_CORS_ORIGINS` |
| `_spawn_service_manager` | Ejecución de subprocesos | Solo acciones predefinidas, proceso separado |
| Proxy PWA `/api/rag` | Confusión remoto→loopback | Elimina identidad del cliente y firma peer original con HMAC fresca |
| Proxy PWA `/api/ollama` | Administración de modelos/disco y bypass del scheduler | Allowlist, credencial remota, token bucket monotónico y lock |
| Registro de pairing | Robo/replay de token y privilegio excesivo | Códigos de un uso con expiración, hashes con clave, archivos atómicos 0600, scopes y revocación |
| Shell del agente | Acceso/escape del host | Raíces registradas, bubblewrap sin red, kill de process group y fallo cerrado |
| Límite de frecuencia | Protección DoS | Token bucket monotónico por IP/bucket, capacidad 30 y recarga en 60 s |

---

## Cómo Funciona la Autorización LAN

1. El gateway elimina cabeceras de forwarding/identidad aportadas por el
   cliente, verifica credencial admin/de dispositivo y firma peer, método, ruta
   y frescura para la petición a FastAPI.
2. FastAPI acepta la aserción solo desde loopback o un peer privado de runtime
   configurado explícitamente y con la clave HMAC compartida; firmas obsoletas,
   repetidas, malformadas o de otra ruta fallan cerrado. Pertenecer a la red no
   concede privilegios por sí solo.
3. Loopback directo tiene privilegio del operador local. Los tokens de dispositivo
   solo pueden incluir `chat`, `read_private` y `web`; scopes elevados antiguos se ignoran.
4. Las rutas `system`, `index`, `agent` o `agent_yolo` exigen procedencia loopback
   original verificada. Un token admin no puede evitar esa comprobación.
5. `TRINAXAI_ALLOW_LAN_SYSTEM` se conserva solo por compatibilidad de configuración
   y no concede autoridad. Solicitudes inválidas o sin permiso devuelven `403`.
6. `agent_yolo` HTTP sigue limitado a loopback y las herramientas peligrosas
   conservan aprobación y sandbox.

**Valores por defecto:**
- `TRINAXAI_ADMIN_TOKEN` — vacío (no configurado). El acceso desde localhost funciona automáticamente.
- El pairing concede `chat,read_private` y opcionalmente puede añadir `web`.
  El token nuevo queda solo en una cookie `HttpOnly; SameSite=Strict` con alcance
  `/api/rag`; los valores legacy se leen únicamente durante la migración explícita
  de `/v1/pairing/me` y después se eliminan.
- `TRINAXAI_ALLOW_LAN_SYSTEM` — obsoleta e ignorada para autorización.

**Probar el modelo de seguridad:**
```bash
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
```

---

## Principios del Proyecto

Estos principios guían todas las decisiones de diseño y contribución:

1. **Local-first** — La inferencia local y el almacenamiento en el host son el valor predeterminado. La instalación/descarga de modelos y cualquier endpoint remoto configurado por la persona usuaria sí pueden usar la red.
2. **Privacidad por defecto** — Los datos de chat, código indexado y documentos se almacenan localmente por defecto. No hay cuentas integradas; las métricas de uso locales se guardan en el host.
3. **Sin nube obligatoria** — Ollama se ejecuta localmente. Opcional: los usuarios pueden apuntar a una instancia remota de Ollama en su propia infraestructura.
4. **Confirmaciones para acciones peligrosas** — El reseteo de fábrica, eliminación de colecciones y apagado del sistema requieren cabeceras de confirmación explícitas o prompts interactivos.
5. **Seguridad por defecto** — Los backends usan loopback, las lecturas LAN
   requieren pairing con scopes, administrar el host exige loopback original
   verificado y CORS es una defensa adicional del navegador, no identidad.
6. **Compatibilidad hacia atrás** — `rag_api.py` es una fachada delgada; el código nuevo usa `app.main`, routers y servicios directamente.
7. **Multiplataforma con evidencia** — Linux está probado en CI en Ubuntu. Windows y macOS tienen instaladores más validación de sintaxis/humo en CI, pero la validación completa de extremo a extremo debe permanecer explícita.
8. **Accesible** — Soporte bilingüe español e inglés. La PWA funciona en móvil. La CLI funciona sobre SSH.
9. **PRs pequeños y enfocados** — Preferir cambios pequeños y bien probados sobre grandes refactorizaciones. Cada PR debe abordar una sola preocupación.
10. **La documentación vive con el código** — Las decisiones se documentan aquí y existen referencias específicas para API, CLI, configuración, PWA y desarrollo.

---

## Documentos Relacionados

- [Índice de documentación](README.es.md) — Mapa completo de guías y referencias
- [Referencia de API](API_REFERENCE.es.md) — Contratos y endpoints HTTP
- [Referencia de configuración](CONFIGURATION.es.md) — Variables, perfiles y seguridad
- [Referencia de CLI](CLI_REFERENCE.es.md) — Comandos, flags y TOML
- [Guía de Desarrollo](DEVELOPER_GUIDE.es.md) — Configuración local, convenciones y depuración
- [Solución de problemas](TROUBLESHOOTING.es.md) — Acciones de recuperación y diagnóstico seguro
- [Documentación de la PWA](../chat-pwa/README.es.md) — Ejecución y desarrollo del frontend
- [Política de Seguridad](SECURITY.es.md) — Modelo de amenazas y reporte
- [Guía de Contribución](CONTRIBUTING.es.md) — Proceso de PR y directrices
