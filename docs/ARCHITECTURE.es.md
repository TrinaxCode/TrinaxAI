# Arquitectura de TrinaxAI

## Visión General

```
┌──────────────────────────────────────────┐
│              Tu Dispositivo              │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │PWA(React)│  │ VSCode (Continue)   │   │
│  │  :3334   │  │ continue-config.yaml│   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │    RAG API (FastAPI) :3333         │   │
│  │ LlamaIndex · bge-m3 · BM25        │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │   Ollama   │  qwen3 · qwen2.5-coder    │
│  │   :11434   │  bge-m3 · qwen3-vl        │
│  └────────────┘                            │
└──────────────────────────────────────────┘
```

TrinaxAI es un **stack local de tres capas**:

1. **Frontend PWA** (React 19 + TypeScript + Vite) en el puerto 3334
2. **API RAG** (FastAPI + LlamaIndex) en el puerto 3333
3. **Ollama** (entorno de ejecución de modelos) en el puerto 11434

Todo se ejecuta en localhost o en una LAN privada de confianza. Sin dependencias en la nube.

---

## Arquitectura de Componentes

### `config.py` — Centro de Configuración Central

La fuente única de verdad para todos los subsistemas. Define:

- **Flota de modelos** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP`, `MODEL_FAST` (todos con soporte de tool-calling y sin "thinking", es decir, listos para flujos agénticos)
- **Perfiles de hardware** — ajustados automáticamente por `TRINAXAI_PROFILE` (4gb/8gb/16gb/max/ultra)
- **Presets de embeddings** — bge-m3 equilibrado, nomic lite, all-minilm rápido
- **Funciones de fábrica** — `make_llm()`, `make_embed()`, `make_reranker()`
- **Enrutador automático** — clasificador heurístico `route_model()` (sin llamada al LLM)
- **Reglas de archivos** — qué indexar, qué omitir, tamaños de chunks por perfil

### `rag_api.py` — Backend FastAPI (2000+ líneas)

El núcleo del sistema. Subsistemas clave:

| Característica | Implementación |
|---|---|
| **Hybrid retrieval** | Vectorial (bge-m3) + BM25 (palabras clave) → fusión por rango recíproco |
| **Reranking** | Cross-encoder (bge-reranker-v2-m3) reordena los candidatos |
| **Colecciones** | Espacios de nombres separados dentro del mismo almacén vectorial |
| **Detección de proyectos** | Heurística a partir de rutas de archivos y la consulta del usuario |
| **Memoria** | Hechos explícitos de "recuerda que" almacenados y auto-resumidos |
| **Investigación profunda** | Descomposición multi-pasada con RAG de sub-preguntas |
| **Vigilante de archivos** | watchdog del sistema de archivos para re-indexación automática |
| **Límite de tasa** | Token bucket, 30 peticiones/min por IP, thread-safe |
| **Estadísticas de uso** | Analítica local basada en JSONL |
| **Sincronización de estado** | Almacén clave-valor compartido entre dispositivos |

### `index.py` — Indexador de Documentos

- **Recolección de archivos** — Poda agresiva de directorios que omite `node_modules`, `.git`, `venv`, etc.
- **Chunking con conciencia AST** — `CodeSplitter` para más de 15 lenguajes, `SentenceSplitter` para prosa
- **Modo incremental** — El manifiesto rastrea archivo→mtime, solo re-indexa archivos nuevos o modificados
- **Soporte de colecciones** — Cada chunk se etiqueta con metadatos de `collection_id`
- **Salida** — `VectorStoreIndex` de LlamaIndex persistido en `storage/`

### `chat-pwa/` — Frontend PWA en React

Los componentes TypeScript construidos con Tailwind CSS y framer-motion incluyen:

| Componente | Propósito |
|---|---|
| `ChatInterface` | Interfaz principal de chat con streaming, markdown, voz y slash commands |
| `ChatSidebar` | Historial, carpetas, búsqueda y flujos de exportación |
| `Settings` | Panel de configuración con 5 secciones (general, indexación, prompts, memoria, estadísticas) |
| `KnowledgeBrowser` | Explora chunks indexados por colección→archivo→chunk |
| `Sources` | Tarjetas de citación con archivo, proyecto, fragmento y puntuación |
| `OnboardingWizard` | Configuración inicial de perfil y modelos |
| `Docs` | Documentación bilingüe integrada en la app |

**Stack tecnológico**: React 19, Vite 6, TypeScript, Tailwind CSS, vite-plugin-pwa, react-markdown

### `trinaxai_cli/` — Interfaz de Terminal

Paquete Python con subcomandos: `chat`, `index`, `browse`, `research`, `memory`, `collections`, `watch`, `export`, `obsidian`, `doctor`.

Usa `httpx` para las llamadas a la API y `rich` para el formato en terminal.

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
  ├─ ¿Docs adjuntos? → extractDocumentText() → inyectar en el prompt
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
  ├─ current_state(paths) → {source_key: mtime}
  │
  ├─ read_manifest() → mapa de claves canonicalizado (collection:path → mtime)
  │
  ├─ Diff: new_files, changed, deleted
  │
  ├─ load_docs(paths) → objetos Document con metadatos
  │
  ├─ build_nodes(docs) → CodeSplitter (AST) o SentenceSplitter
  │
  ├─ Embed nodos (bge-m3, sin LLM necesario)
  │
  └─ persistir en storage/ + write_manifest()
```

---

## Modelo de Seguridad

| Capa | Mecanismo |
|---|---|
| **Red** | Dirección de escucha configurable y orígenes/regex CORS explícitos |
| **Endpoints protegidos** | Requieren loopback, LAN privada habilitada o token (`TRINAXAI_ADMIN_TOKEN`) |
| **Control de LAN** | `TRINAXAI_ALLOW_LAN_SYSTEM=0` deshabilita el acceso de sistema por LAN |
| **TLS** | Los servicios administrados pueden usar certificados locales; `TRINAXAI_TLS_VERIFY` controla verificaciones salientes concretas |
| **Sudoers** | `setup_trinaxai.sh` crea `/etc/sudoers.d/trinaxai` para el control de servicios |
| **Datos** | Todos los datos permanecen en el dispositivo — sin subidas a la nube, sin telemetría |

---

## Estructura de Almacenamiento

```
storage/
├── docstore.json          # Almacén de documentos de LlamaIndex
├── index_store.json       # Metadatos de índice de LlamaIndex
├── *_vector_store.json    # Almacenes vectoriales/namespaces persistidos
├── graph_store.json       # Almacén de grafo de LlamaIndex
├── manifest.json          # Archivo→mtime para indexación incremental
├── collections.json       # Metadatos de colecciones
├── usage.jsonl            # Estadísticas de uso (JSON lines)
├── app_state.json         # Estado compartido entre dispositivos
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
- **Colecciones** — concepto de primera clase en todo el stack
- **PWA en lugar de Electron** — más ligera, compatible con móviles, sin cadena de herramientas nativa
- **Todo incremental** — detección de cambios basada en manifiesto, segundos en lugar de horas

---

## Guía para Contribuidores: Qué Tocar Según la Tarea

Esta sección ayuda a los contribuidores a encontrar los archivos correctos para tareas comunes.

### Chat / IA Conversacional

| Qué cambiar | Dónde |
|---|---|
| Lógica del endpoint de chat | `rag_api.py` → `/v1/chat/completions` — migrando a `app/routes/chat.py` |
| Recuperación RAG + síntesis | `app/services/rag_service.py` (`run_rag`, `build_engine`, `prepare_query`) |
| Streaming SSE | `rag_api.py` `generate_stream()` + `chat-pwa/src/lib/api.ts` `parseRagSseLine()` |
| Plantilla de prompt | `app/services/rag_service.py` `qa_prompt_tmpl` |
| Enrutamiento automático de modelos | `config.py` `route_model()` |
| UI del chat en frontend | `chat-pwa/src/components/ChatInterface.tsx` |
| Hook de streaming en frontend | `chat-pwa/src/hooks/useStreamChat.ts` |

### Indexación / Pipeline RAG

| Qué cambiar | Dónde |
|---|---|
| Indexación de documentos | `index.py` (punto de entrada), `config.py` (configuración de chunking) |
| Estrategia de chunking | `index.py` — `CodeSplitter` para código, `SentenceSplitter` para prosa |
| Modelo de embeddings | `config.py` `make_embed()` |
| Indexación incremental | `index.py` lógica del manifiesto + `config.py` `MANIFEST_PATH` |
| Subida de índice (carpeta del navegador) | `rag_api.py` `/system/index-upload` |
| Vigilante de archivos | `rag_api.py` clase `_watch_Handler` + endpoints `/v1/watch/*` |

### Sistema de Memoria

| Qué cambiar | Dónde |
|---|---|
| CRUD de memoria | `app/services/memory_service.py` |
| Resumen de memoria (LLM) | `app/services/memory_service.py` `memory_refresh()` |
| Inyección de memoria en chat | `rag_api.py` inyección de contexto en cadena de prompt |
| Panel de memoria en frontend | `chat-pwa/src/components/MemoryPanel.tsx` |

### Colecciones de Conocimiento

| Qué cambiar | Dónde |
|---|---|
| CRUD de colecciones | `app/services/collection_service.py` |
| Endpoints de colecciones | `rag_api.py` `/collections/*` — migrando a `app/routes/collections.py` |
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
| Configuración de perfil de hardware | `install_ollama_16gb_profile.sh` |

---

## Ejecución de Pruebas

### Backend (Python)

```bash
# Todas las pruebas del backend
.venv/bin/python -m pytest -q

# Archivos de prueba específicos
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
.venv/bin/python -m pytest tests/test_rag_api_reset_and_sources.py -v

# Lint
.venv/bin/python -m ruff check .

# Verificación de tipos (mejor esfuerzo, no estricto)
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
| Endpoints `/system/*` | Control de procesos (inicio, apagado, recarga) | El guardián en tiempo de ejecución es `rag_api.py::_authorize_system`; el extraído `app/security/admin_auth.py` debe mantenerse sincronizado hasta que la migración de rutas se complete |
| `/system/index-upload` | Escrituras en sistema de archivos | Prevención de path traversal, límites de tamaño, nombres saneados |
| `_factory_reset_runtime_state` | Eliminación de datos | Requiere cabecera de confirmación, solo limpia `storage/` y `local_sources/` |
| `_authorize_system` / `authorize_system` | Bypass de control de acceso | Mantener comportamiento equivalente entre auth en runtime y auth extraída durante la migración |
| Configuración CORS | Acceso cross-origin | Por defecto: solo localhost + LAN; configurable vía `TRINAXAI_CORS_ORIGINS` |
| `_spawn_service_manager` | Ejecución de subprocesos | Solo acciones predefinidas, proceso separado |
| Límite de frecuencia | Protección DoS | Token bucket por IP, 30 req/min por defecto |

---

## Cómo Funciona el Control de LAN / Sistema

```
                     ┌──────────────────────────────┐
                     │    authorize_system(request)  │
                     └─────────────┬────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │  ¿ADMIN_TOKEN configurado?   │
                    └──────┬─────────────┬────────┘
                           │ Sí          │ No
                           ▼             ▼
              ┌──────────────────┐   ┌──────────────────┐
              │ ¿Token coincide? │   │ ¿Localhost?      │
              └──┬───────────┬───┘   └──┬───────────┬───┘
                 │ Sí        │ No      │ Sí        │ No
                 ▼           ▼         ▼           ▼
              ✅ PERMITIR  ❌ 403   ✅ PERMITIR ┌──────────────┐
                                               │ ¿LAN activada?│
                                               └──┬────────┬──┘
                                                  │ Sí     │ No
                                                  ▼        ▼
                                           ┌──────────┐ ❌ 403
                                           │ ¿IP LAN? │
                                           └──┬───┬───┘
                                              │Sí │No
                                              ▼   ▼
                                           ✅  ❌ 403
```

**Valores por defecto:**
- `TRINAXAI_ADMIN_TOKEN` — vacío (no configurado). El acceso desde localhost funciona automáticamente.
- `TRINAXAI_ALLOW_LAN_SYSTEM` — `0` (desactivado). Teléfonos/tablets en WiFi pueden usar la PWA pero no pueden llamar a endpoints de sistema.
- Activa el control de sistema LAN con `--lan-system` durante la instalación, que genera un token aleatorio fuerte.

**Probar el modelo de seguridad:**
```bash
.venv/bin/python -m pytest tests/test_security_endpoints.py -v
```

---

## Principios del Proyecto

Estos principios guían todas las decisiones de diseño y contribución:

1. **Local-first** — Todo se ejecuta en el dispositivo del usuario. Sin dependencias en la nube, sin telemetría, sin exfiltración de datos.
2. **Privacidad por defecto** — Datos de chat, código indexado y documentos nunca salen de la máquina. Sin cuentas, sin analíticas.
3. **Sin nube obligatoria** — Ollama se ejecuta localmente. Opcional: los usuarios pueden apuntar a una instancia remota de Ollama en su propia infraestructura.
4. **Confirmaciones para acciones peligrosas** — El reseteo de fábrica, eliminación de colecciones y apagado del sistema requieren cabeceras de confirmación explícitas o prompts interactivos.
5. **Seguridad por defecto** — El control de sistema LAN está desactivado. Los tokens de administrador se autogeneran al activarse. CORS está restringido a localhost + LAN de confianza.
6. **Compatibilidad hacia atrás** — Los cambios disruptivos requieren un camino de migración. La migración `rag_api.py` → `app/` es incremental.
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
- [Documentación de la PWA](../chat-pwa/README.es.md) — Ejecución y desarrollo del frontend
- [Política de Seguridad](../SECURITY.md) — Modelo de amenazas y reporte
- [Guía de Contribución](../CONTRIBUTING.md) — Proceso de PR y directrices
- [Hoja de Ruta](../ROADMAP.md) — Funcionalidades planeadas e hitos
- [Checklist de Publicación](PUBLIC_RELEASE.md) — Pasos de auditoría pre-lanzamiento
