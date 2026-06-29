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
│  │   Ollama   │  qwen2.5 · llama3.2       │
│  │   :11434   │  bge-m3 · moondream       │
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

- **Flota de modelos** — `MODEL_GENERAL`, `MODEL_CODE`, `MODEL_DEEP`, `MODEL_FAST`
- **Perfiles de hardware** — ajustados automáticamente por `TRINAXAI_PROFILE` (8gb/16gb/max/ultra)
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

18 componentes en TypeScript con Tailwind CSS y framer-motion:

| Componente | Propósito |
|---|---|
| `ChatInterface` | Interfaz principal de chat con streaming, markdown, voz y slash commands |
| `ChatSidebar` | Historial de sesiones, búsqueda, exportación (Markdown/PDF/Word) |
| `Settings` | Panel de configuración con 5 secciones (general, indexación, prompts, memoria, estadísticas) |
| `KnowledgeBrowser` | Explora chunks indexados por colección→archivo→chunk |
| `Sources` | Tarjetas de citación con archivo, proyecto, fragmento y puntuación |
| `OnboardingWizard` | Configuración inicial en 7 pasos |
| `Docs` | Documentación integrada en la app con 11 secciones |

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
            → descarga del modelo (keep_alive=0)
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
| **Red** | Solo localhost + LAN privada (filtro CORS por IP + puerto) |
| **Endpoints de sistema** | Requieren localhost/LAN o token de administrador (`TRINAXAI_ADMIN_TOKEN`) |
| **Control de LAN** | `TRINAXAI_ALLOW_LAN_SYSTEM=0` deshabilita el acceso de sistema por LAN |
| **TLS** | HTTPS con certificados autofirmados (solo localhost, `TRINAXAI_TLS_VERIFY` lo controla) |
| **Sudoers** | `setup_trinaxai.sh` crea `/etc/sudoers.d/trinaxai` para el control de servicios |
| **Datos** | Todos los datos permanecen en el dispositivo — sin subidas a la nube, sin telemetría |

---

## Estructura de Almacenamiento

```
storage/
├── docstore.json          # Almacén de documentos de LlamaIndex
├── index_store.json       # Índice FAISS/vectorial
├── manifest.json          # Archivo→mtime para indexación incremental
├── collections.json       # Metadatos de colecciones
├── usage.jsonl            # Estadísticas de uso (JSON lines)
└── app_state.json         # Estado compartido entre dispositivos
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
- **localStorage como almacén primario** — con respaldo, compactación y sincronización entre dispositivos
