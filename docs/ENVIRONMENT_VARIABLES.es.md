# Inventario de variables de entorno

Este es el inventario canónico de variables de entorno que entiende TrinaxAI. Usa [`.env.example`](../.env.example) como plantilla inicial y conserva solo los overrides que necesite tu instalación. Las variables del entorno del proceso tienen prioridad sobre el `.env` de la raíz cuando `service_manager.py` inicia los servicios.

Los valores booleanos normalmente aceptan `1`/`0`; los ajustes de seguridad y servicios también aceptan `true`/`false`, `yes`/`no` y `on`/`off` cuando el código lo indica. Los límites de bytes son enteros. Las variables marcadas como **internas** las establecen los scripts de TrinaxAI para procesos hijos y normalmente no deben añadirse a `.env`.

Si un override provoca un fallo, usa la [guía de solución de problemas y recuperación](TROUBLESHOOTING.es.md) antes de acumular más overrides. Recuerda que `VITE_*` se fija al construir, mientras que los valores del backend y gateway se leen en runtime.

## Ejecución, rutas y red

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_HOME` | autodetectado | Raíz de instalación usada por la CLI, el gateway frontend y los scripts de ciclo de vida. |
| `TRINAXAI_PYTHON` | Python actual | Ejecutable de Python usado por servicios y scripts de mantenimiento. |
| `TRINAXAI_PROFILE` | autodetectado | Perfil: `8gb`, `16gb`, `32gb` o `64gb`. La detección CPU/RAM/GPU se guarda en `storage/hardware_profile.json`. |
| `TRINAXAI_PERFORMANCE_MODE` | `fast` | Ajuste de ejecución: `fast`, `balanced` o `quality`. |
| `TRINAXAI_THINKING_MODE` | `1` | Fallback del backend cuando el cliente omite `think`; `0` desactiva el razonamiento. |
| `TRINAXAI_HOST` | `127.0.0.1` en la plantilla endurecida | Dirección de escucha de la API. Mantén FastAPI detrás del gateway del mismo host; no la publiques directamente. |
| `TRINAXAI_UNSAFE_BIND_BACKEND` | `0` | Escape explícito de alto riesgo que permite una dirección no loopback en `TRINAXAI_HOST`. Déjalo desactivado. |
| `TRINAXAI_PORT` | `3333` | Puerto TCP de la API. |
| `TRINAXAI_RAG_HTTPS` | `1` | Activa TLS administrado para la API cuando existen certificados locales. |
| `TRINAXAI_CA_FILE` | autodetectado | Bundle CA explícito para HTTPS verificado de la CLI. Las raíces mkcert/locales se descubren automáticamente. |
| `TRINAXAI_HEALTH_URL` | derivada del puerto/TLS | URL de salud usada por instaladores y diagnósticos. |
| `TRINAXAI_FRONTEND_URL` | `https://localhost:3334` | URL local/pública reportada para la PWA. |
| `TRINAXAI_PWA_PORT` | `3334` | Puerto TCP del gateway PWA normal y su listener de recuperación loopback. |
| `TRINAXAI_PWA_HOST` | `127.0.0.1` | Interfaz donde escucha el gateway PWA. Usa `0.0.0.0` solo para una configuración LAN HTTPS intencional; los navegadores remotos aún necesitan un scope vinculado. |
| `TRINAXAI_PWA_DIST` | `dist` | Directorio opcional de salida/build frontend relativo a `chat-pwa`; útil para previews y E2E paralelos aislados. |
| `TRINAXAI_ALLOW_INSECURE_HTTP` | `0` | Escape solo para pruebas que permite HTTP en una interfaz PWA no loopback. Déjalo desactivado; HTTP loopback sigue disponible para pruebas locales. |
| `TRINAXAI_FRONTEND_MODE` | `serve` | Gateway Node de producción usado por el gestor de servicios; `dev` selecciona Vite HMR. |
| `TRINAXAI_STOP_ALL_DELAY` | `0` (`0.25` durante el handoff API) | Retardo interno breve para enviar la respuesta de detener todo antes de cerrar el supervisor. |
| `TRINAXAI_TLS_VERIFY` | `0` | Verifica certificados TLS para ciertas solicitudes salientes del backend. La CLI siempre verifica TLS; usa `--ca-file` o `TRINAXAI_CA_FILE` para una CA privada. |
| `TRINAXAI_CORS_ORIGINS` | orígenes locales seguros | Orígenes exactos del navegador separados por comas. CORS no es autenticación. |
| `TRINAXAI_CORS_ORIGIN_REGEX` | regex de LAN privada | Expresión regular adicional de orígenes FastAPI. Revísala antes de ampliarla. |
| `TRINAXAI_ALLOW_LAN_SYSTEM` | `0` | Variable de compatibilidad obsoleta; ya no concede administración del host por LAN. |
| `TRINAXAI_ADMIN_TOKEN` | vacío | Credencial admin para operaciones protegidas de bajo riesgo. Nunca evita el requisito loopback para administrar el host. |
| `TRINAXAI_DEVICE_REGISTRY` | `storage/device_pairing.json` | Registro atómico con hashes, metadatos/scopes y hashes de códigos temporales. Nunca guarda tokens de dispositivo en claro. |
| `TRINAXAI_DEVICE_SECRET_FILE` | `storage/.device_secret` | Clave con modo 0600 para hashear códigos de pairing y tokens bearer. FastAPI y el gateway deben compartirla. |
| `TRINAXAI_DEVICE_TOKEN` | vacío | Credencial de la CLI empaquetada para un dispositivo vinculado, enviada como `X-TrinaxAI-Device-Token`. |
| `TRINAXAI_PROXY_SECRET_FILE` | `storage/.proxy_secret` | Clave HMAC con modo 0600 compartida solo por los procesos locales del gateway/backend. |
| `TRINAXAI_PROXY_SECRET` | vacío | Override directo del secreto HMAC. Prefiere el archivo para no copiarlo en definiciones de servicio o historial de shell. |
| `TRINAXAI_PROXY_TRUSTED_PEERS` | vacío | IPs/CIDR separadas por comas permitidas como peers de transporte para aserciones del gateway. |
| `TRINAXAI_RATE_LIMIT_PER_MINUTE` | `30` | Capacidad de cada bucket de tokens, indexado por IP verificada y bucket de endpoint. |
| `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Segundos en los que un bucket vacío vuelve a llenarse. |
| `TRINAXAI_OLLAMA_PROXY_RATE_LIMIT` | `30` | Solicitudes por minuto y peer verificado a través de la fachada Ollama allowlisted. |
| `TRINAXAI_CERT_PASSPHRASE` | `trinaxai-local` | Contraseña usada por el gateway frontend para el certificado PFX local. |
| `TRINAXAI_LOCAL_CA_FILE` | autodetectado | Bundle CA opcional usado por el gateway PWA para HTTPS verificado hacia la API RAG loopback. |
| `TRINAXAI_APP_STATE_MAX_BYTES` | `6291456` | Tamaño máximo del estado compartido persistido de la PWA. |
| `TRINAXAI_CONFIG` | ruta de configuración de la plataforma | Ruta TOML explícita para la CLI empaquetada. |
| `TRINAXAI_LANG` | autodetectado | Idioma de la interfaz de la CLI: `en` o `es`. |
| `TRINAXAI_NO_COLOR` | no definido | Desactiva el color ANSI de la salida de CLI cuando está presente. |

## Docker Compose

Estos valores los consume `compose.yaml`; son ajustes de despliegue, no opciones de la aplicación FastAPI.

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_DOCKER_IMAGE` | `trinaxai-api:local` | Imagen backend. Usa `ghcr.io/trinaxcode/trinaxai:1.2.0` para el paquete oficial fijado. |
| `TRINAXAI_DOCKER_UID` / `TRINAXAI_DOCKER_GID` | `1000` | Identidad del host dentro del contenedor para conservar propietarios de archivos montados. |
| `TRINAXAI_DOCKER_PORT` | `3333` | Puerto loopback del host asignado al puerto `3333` del contenedor. |
| `TRINAXAI_DOCKER_OLLAMA_URL` | `http://host.docker.internal:11434` | Endpoint Ollama accesible desde el contenedor. |
| `TRINAXAI_DOCKER_INDEX_DIR` | `./projects` | Carpeta del host montada en solo lectura en `/data/projects`. |
| `TRINAXAI_DOCKER_NETWORK_CIDR` | `172.31.0.0/24` | Subred privada de Compose y rango de transporte HMAC confiable. |

## Modelos, generación y embeddings

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_MODEL_GENERAL` | derivado del perfil | Modelo de conversación general. |
| `TRINAXAI_MODEL_CODE` | derivado del perfil | Modelo normal de código. |
| `TRINAXAI_MODEL_DEEP` | derivado del perfil | Modelo para código/razonamiento complejo. |
| `TRINAXAI_MODEL_FAST` | derivado del perfil | Modelo de baja latencia. |
| `TRINAXAI_LLM` | modelo de código | Modelo usado cuando se desactiva el routing automático. |
| `TRINAXAI_LLM_HEAVY` | modelo profundo | Fallback pesado cuando se desactiva el routing automático. |
| `TRINAXAI_AUTO_ROUTE` | `1` | Activa el routing por tarea. |
| `TRINAXAI_NUM_CTX` | derivado del perfil | Ventana de contexto RAG/modelo. |
| `TRINAXAI_AGENT_NUM_CTX` | derivada de `TRINAXAI_NUM_CTX` | Ventana de contexto del Agent. |
| `TRINAXAI_AGENT_TIMEOUT` | `600` | Máximo de segundos para una ejecución HTTP del Agent. |
| `TRINAXAI_AGENT_STALL_TIMEOUT` | `120` | Máximo de segundos sin tokens, actividad de herramientas o aprobación pendiente. |
| `TRINAXAI_AGENT_QUEUE_MAXSIZE` | `128` | Máximo de eventos SSE almacenados por sesión del Agent antes de cancelar por backpressure. |
| `TRINAXAI_AGENT_QUEUE_PUT_TIMEOUT` | `0.25` | Segundos que el worker espera para encolar un evento SSE antes de considerar que el cliente no puede seguir el ritmo. |
| `TRINAXAI_NUM_THREAD` | `8` | Hilos CPU solicitados por generación Ollama. |
| `OLLAMA_NUM_GPU` | autodetectado | Hints de capas GPU de Ollama; `0` usa CPU y un valor alto descarga las capas que caben en la GPU detectada. |
| `TRINAXAI_KEEP_ALIVE` | derivado del perfil | Duración de permanencia de modelos Ollama. |
| `TRINAXAI_TIMEOUT` | `300` | Timeout de solicitudes Ollama en segundos. |
| `TRINAXAI_MODEL_MAX_CONCURRENCY` | `1` | Tareas de modelo simultáneas; mantenlo bajo para evitar thrashing de RAM/VRAM. |
| `TRINAXAI_INFERENCE_QUEUE_TIMEOUT` | `600` | Segundos que FastAPI y el gateway esperan el lock de inferencia compartido. |
| `TRINAXAI_INFERENCE_LOCK_FILE` | `storage/.inference.lock` | Ruta del lock atómico compartido por el gateway. |
| `TRINAXAI_GEN_NUM_CTX` | derivado de tarea/perfil | Ventana de contexto de generación libre. |
| `TRINAXAI_GEN_NUM_CTX_MAX` | `16384` | Límite máximo de contexto de generación. |
| `TRINAXAI_MAX_CONTINUATIONS` | `2` | Máximo de continuaciones acotadas tras una respuesta limitada por longitud o Markdown incompleto. `0` desactiva la continuación automática. |
| `VITE_TRINAXAI_MAX_CONTINUATIONS` | `2` | Fallback del frontend para continuaciones acotadas cuando el backend no informa un límite. |
| `TRINAXAI_GEN_NUM_PREDICT` | derivado de tarea | Override del presupuesto de tokens de salida. |
| `TRINAXAI_GEN_MAX_FIX` | derivado de tarea | Máximo de pasadas generar/validar/corregir. |
| `TRINAXAI_GEN_TEMPERATURE_CODE_GEN` | `0.15` | Override de temperatura para generar código. |
| `TRINAXAI_GEN_TEMPERATURE_CREATIVE` | `0.5` | Override de temperatura para tareas creativas. |
| `TRINAXAI_GEN_TEMPERATURE_EXPLAIN` | `0.4` | Override de temperatura para explicaciones. |
| `TRINAXAI_GEN_TEMPERATURE_GROUNDED_QA` | `0.0` | Override de temperatura para respuestas RAG fundamentadas. |
| `TRINAXAI_EMBED_PRESET` | derivado del perfil | Preset de embeddings: `balanced` (0.6B), `quality` (4B), `lite` o `fast`. Los valores legacy `max` migran a `quality`. |
| `TRINAXAI_EMBED` | derivado del preset | Modelo Ollama de embeddings. Cambiarlo requiere reindexar. |
| `TRINAXAI_EMBED_DIMS` | derivado del preset | Dimensiones del vector de embeddings. Cambiarlo requiere reindexar. |
| `TRINAXAI_EMBED_WORKERS` | derivado del perfil | Solicitudes de embeddings simultáneas. |
| `TRINAXAI_EMBED_BATCH` | derivado del perfil | Nodos por lote de embeddings. |
| `TRINAXAI_EMBED_KEEP_ALIVE` | derivado del perfil | Permanencia del modelo de embeddings. |
| `TRINAXAI_AGGRESSIVE_QUANT` | `0` | Activa hints de quantization/runtime agresivos. |

Ollama también consume `OLLAMA_BASE_URL`, `OLLAMA_HOST` y `OLLAMA_NUM_GPU`.

## Búsqueda web

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_WEB_SEARCH_PROVIDER` | `auto` | Proveedor: selección automática, Brave, SearXNG o desactivado. |
| `TRINAXAI_BRAVE_SEARCH_API_KEY` | vacío | Clave API del proveedor Brave Search. |
| `TRINAXAI_SEARXNG_URL` | vacío | URL base de una instancia SearXNG pública o del endpoint loopback local documentado `http://127.0.0.1:8080`; debe habilitar búsquedas JSON. |
| `TRINAXAI_WEB_SEARCH_TIMEOUT` | `15` | Timeout de búsqueda en segundos. |
| `TRINAXAI_WEB_SEARCH_MAX_RESULTS` | `6` | Máximo de resultados por búsqueda. |
| `TRINAXAI_WEB_SEARCH_CACHE_SECONDS` | `300` | Duración de la caché de resultados en memoria. |

## Recuperación, indexación y archivos persistidos

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_PERSIST_DIR` | `storage/` | Carpeta del índice persistido y del estado de ejecución; útil para instancias aisladas o desechables. |
| `TRINAXAI_INDEX_DIR` | `local_sources/` del repositorio | Carpeta recorrida recursivamente; vacía o sin configurar usa esa carpeta local. |
| `TRINAXAI_COLLECTION_ID` | `default` | Identificador de colección enviado al indexador. |
| `TRINAXAI_COLLECTION_NAME` | `General` | Nombre legible de la colección. |
| `TRINAXAI_DEFAULT_COLLECTION_ID` | `default` | Colección aceptada por el validador de runtime. |
| `TRINAXAI_INDEX_APPEND` | `0` | Conserva entradas cuyos archivos fuente desaparecieron cuando se activa. |
| `TRINAXAI_INDEX_BATCH_SIZE` | `100` | Archivos cargados por lote. |
| `TRINAXAI_INDEX_NODE_BATCH_SIZE` | `32` | Nodos embebidos por lote de construcción. |
| `TRINAXAI_INDEX_STAGE_TIMEOUT` | `900` | Máximo de segundos por etapa sin progreso estructurado. |
| `TRINAXAI_INDEX_LOAD_WORKERS` | hasta `8` | Cargadores simultáneos de archivos fuente. |
| `TRINAXAI_INDEX_LOCK_TIMEOUT` | `60` | Segundos de espera del lock del escritor del índice. |
| `TRINAXAI_INDEX_TIMEOUT` | `3600` | Segundos que la CLI espera al proceso indexador. |
| `TRINAXAI_WATCH_INDEX_TIMEOUT` | `1800` | Segundos permitidos a un indexador del watcher. |
| `TRINAXAI_WATCH_RELOAD_TIMEOUT` | `30` | Segundos de espera para recargar motores RAG. |
| `TRINAXAI_WATCH_OUTPUT_MAX_BYTES` | `16384` | Bytes máximos de stdout/stderr retenidos por trabajo. |
| `TRINAXAI_PROJECT_ROOT` | ruta seleccionada por la CLI | **Interna:** raíz pasada de `trinaxai index` al indexador. |
| `TRINAXAI_SOURCE_ID` | derivado de la raíz canónica | Identidad estable de una raíz sincronizada. |
| `TRINAXAI_CHUNK_SIZE` | derivado de modo/perfil | Tamaño de chunks de prosa en tokens. |
| `TRINAXAI_CHUNK_OVERLAP` | derivado de modo/perfil | Solapamiento de chunks de prosa. |
| `TRINAXAI_CODE_CHUNK_LINES` | `60` | Líneas objetivo por chunk de código. |
| `TRINAXAI_CODE_CHUNK_LINES_OVERLAP` | derivado del modo | Solapamiento de chunks de código. |
| `TRINAXAI_CODE_MAX_CHARS` | `2000` | Máximo preferido de caracteres por chunk de código. |
| `TRINAXAI_SIMILARITY_TOP_K` | derivado del perfil | Chunks finales enviados al modelo. |
| `TRINAXAI_FUSION_CANDIDATES` | derivado del perfil | Candidatos por recuperador antes de fusionar. |
| `TRINAXAI_RETRIEVAL_CACHE_SECONDS` | derivado del modo | Duración de la caché de recuperación; `0` la desactiva. |
| `TRINAXAI_RAG_MIN_SCORE` | `0.015` | Score mínimo de reciprocal-rank aceptado en Knowledge mode explícito. |
| `TRINAXAI_SOURCES_CACHE_SECONDS` | derivado del modo | Duración de caché de fuentes; `0` la desactiva. |
| `TRINAXAI_RETRIEVER_CACHE_MAX_COMBINATIONS` | `32` | Límite LRU de combinaciones de colecciones. |
| `TRINAXAI_RERANK` | `0` | Activa reranking opcional con cross-encoder. |
| `TRINAXAI_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Modelo de reranking. |
| `TRINAXAI_RERANK_TOP_N` | valor top-k | Resultados conservados por el reranker. |
| `TRINAXAI_MAX_FILE_BYTES` | `3145728` | Límite de archivos indexados normales. |
| `TRINAXAI_DOCUMENT_MAX_FILE_BYTES` | `536870912` | Límite de contenedores documentales grandes. |
| `TRINAXAI_UPLOAD_MAX_FILES` | `2500` | Máximo de archivos por operación. |
| `TRINAXAI_UPLOAD_MAX_BYTES` | `2147483648` | Máximo total de bytes por operación. |
| `TRINAXAI_DOCUMENT_MAX_CONCURRENCY` | `1` | Tareas simultáneas de extracción documental. |
| `TRINAXAI_DOC_EXTRACT_MAX_BYTES` | `134217728` | Tamaño máximo aceptado por extracción. |
| `TRINAXAI_DOC_EXTRACT_MAX_CHARS` | `120000` | Caracteres máximos devueltos/guardados por documento. |
| `TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES` | `536870912` | Tamaño máximo de un adjunto retenido. |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES` | `4294967296` | Cuota total de adjuntos retenidos. |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES` | `1000` | Cuota de cantidad de adjuntos retenidos. |
| `TRINAXAI_OCR` | `0` | Activa OCR opcional para PDFs escaneados con poco texto. |

El indexador reconoce código, prosa/datos, PDF y Office, HTML, EPUB, correo,
subtítulos, calendarios, contactos y notebooks. Los binarios opacos se omiten.

## Memoria persistente

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_MEMORY_MAX_ENTRIES` | `1000` | Máximo de entradas guardadas. |
| `TRINAXAI_MEMORY_MAX_FILE_BYTES` | `4194304` | Tamaño máximo serializado del almacén. |
| `TRINAXAI_MEMORY_TEXT_MAX_CHARS` | `20000` | Caracteres máximos por entrada. |
| `TRINAXAI_MEMORY_MAX_TAGS` | `50` | Tags máximos por memoria. |
| `TRINAXAI_MEMORY_TAG_MAX_CHARS` | `100` | Caracteres máximos por tag. |
| `TRINAXAI_MEMORY_SUMMARY_MAX_CHARS` | `50000` | Entrada máxima para refrescar el resumen visible. |

## Voz

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_VOICE_STT_MODEL` | `base` | Modelo Whisper para voz a texto local. |
| `TRINAXAI_VOICE_DEVICE` | `auto` | Dispositivo de ejecución, por ejemplo `cpu` o `cuda`. |
| `TRINAXAI_VOICE_COMPUTE_TYPE` | `default` | Tipo de cómputo compatible con el dispositivo. |
| `TRINAXAI_VOICE_TTS_ENGINE` | autodetectado | Fuerza un backend local de texto a voz. |
| `TRINAXAI_VOICE_MAX_AUDIO_BYTES` | `31457280` | Tamaño máximo de audio STT. |
| `TRINAXAI_VOICE_TTS_MAX_CHARS` | `1200` | Texto máximo por solicitud TTS. |
| `TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE` | `30` | Límite de voz por minuto. |
| `TRINAXAI_VOICE_MAX_CONCURRENCY` | `1` | Trabajos de voz simultáneos. |
| `TRINAXAI_PIPER_MODEL` | autodetectado | Ruta explícita del modelo Piper. |
| `TRINAXAI_COQUI_MODEL` | `tts_models/es/mai/tacotron2-DDC` | Identificador del modelo Coqui. |

## Aislamiento del agente

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_AGENT_WORKSPACE_ROOTS` | raíces configuradas y luego repositorio | Allowlist de workspaces HTTP del Agent separada por el separador de cada plataforma. |
| `TRINAXAI_AGENT_HTTP_YOLO` | `0` | Activa autoaprobación HTTP solo con prueba adicional de `agent_yolo`; el acceso remoto normal sigue bloqueado. |
| `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` | `0` | Escape explícito de alto riesgo cuando no hay sandbox del sistema. |

Las herramientas resuelven symlinks y rechazan rutas fuera del workspace. En
Linux, los comandos requieren bubblewrap, no tienen red y solo ven el workspace
como árbol escribible. Sin aislamiento compatible, la ejecución queda desactivada.

## Gateway PWA y build de Vite

Las variables `VITE_*` se integran al compilar; reconstruye la PWA después de
cambiarlas. Los destinos sin `VITE_*` se leen al ejecutar el gateway.

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_RAG_TARGET` | `http://127.0.0.1:3333` | Destino del gateway para `/api/rag`. |
| `TRINAXAI_OLLAMA_TARGET` | `http://127.0.0.1:11434` | Destino del gateway para `/api/ollama`. |
| `VITE_TRINAXAI_RAG_TARGET` | fallback del destino RAG | Fallback heredado del proxy de build. |
| `VITE_TRINAXAI_RAG_BASE` | `/api/rag` | Base RAG del navegador en producción. |
| `VITE_TRINAXAI_OLLAMA_BASE` | `/api/ollama` | Base Ollama del navegador en producción. |
| `VITE_TRINAXAI_DEV_RAG_BASE` | `/api/rag` | Base RAG del navegador en desarrollo. |
| `VITE_TRINAXAI_DEV_OLLAMA_BASE` | `/api/ollama` | Base Ollama del navegador en desarrollo. |
| `VITE_TRINAXAI_INDEX_DIR` | vacío (`local_sources/` elegido por el servidor) | Hint inicial de carpeta de índice mostrado por la PWA. |
| `VITE_TRINAXAI_REPO_URL` | repositorio del proyecto | Enlace al repositorio mostrado por la PWA. |
| `VITE_TRINAXAI_DOCS_URL` | README del repositorio | Enlace documental mostrado por la PWA. |
| `TRINAXAI_VISION_MODEL` | `qwen3.5:4b` | Modelo de visión usado por la CLI para analizar imágenes cuando no se indica otro explícitamente. |
| `VITE_TRINAXAI_VISION_MODEL` | `qwen3.5:4b` | Modelo de visión para OCR, capturas, documentos e imágenes. |
| `VITE_TRINAXAI_KEEP_ALIVE` | `10m` | Keep-alive de Ollama enviado por el navegador. |

## Instalación, actualización, backup y ciclo de vida

| Variable | Predeterminado | Propósito |
|---|---|---|
| `TRINAXAI_INTERACTIVE` | `1` | Permite preguntas opcionales en scripts POSIX. |
| `TRINAXAI_NONINTERACTIVE` | `0` | Suprime preguntas opcionales. |
| `TRINAXAI_INSTALL_MODELS` | `1` | Descarga modelos configurados durante la instalación. |
| `TRINAXAI_INSTALL_VISION` | `1` | Flag de compatibilidad; visión se descarga al primer análisis. |
| `TRINAXAI_ENABLE_AUTOSTART` | `1` | Activa arranque automático. |
| `TRINAXAI_ENABLE_AUTO_UPDATE` | `1` | Instala la tarea de comprobación de disponibilidad de releases. |
| `TRINAXAI_START_NOW` | `1` | Inicia TrinaxAI al terminar la instalación. |
| `TRINAXAI_BACKUP_DIR` | `./backups` | Destino de scripts de backup/actualización. |
| `TRINAXAI_BACKUP_QUIESCE` | `1` | Pausa la API durante el backup. |
| `TRINAXAI_UPDATE_BACKUP` | `1` | Crea un backup antes de actualizar. |
| `TRINAXAI_UPDATE_PULL` | `1` | Descarga cambios Git durante la actualización. |
| `TRINAXAI_UPDATE_MODELS` | auto/preguntado | Descarga modelos Ollama configurados. |
| `TRINAXAI_UPDATE_REMOVE_MODELS` | `0` | Elimina modelos configurados antes de reemplazarlos. |
| `TRINAXAI_UPDATE_REPAIR_OLLAMA` | `0` | Reinstala o repara Ollama durante la actualización. |
| `TRINAXAI_UPDATE_RESTART` | auto/preguntado | Reinicia servicios después de actualizar. |
| `TRINAXAI_UPDATE_AUDIT` | `1` | Ejecuta el readiness audit posterior. |
| `TRINAXAI_RELEASE_VERSION` | `1.2.0` | **Instalador:** versión fijada del release de GitHub para descargar el código. |
| `TRINAXAI_SOURCE_URL` | archivo oficial de GitHub | **Origen de instalación:** URL HTTPS del archivo usado al instalar desde un checkout de código fuente. |
| `TRINAXAI_SOURCE_SHA256` | manifiesto del release | **Instalador:** SHA-256 de un archivo personalizado; obligatorio junto con `TRINAXAI_SOURCE_URL`. |
| `TRINAXAI_UPDATE_ROOT` | directorio del script | **Interna:** raíz pasada al actualizador automático. |
| `TRINAXAI_PRIVILEGED_WRAPPER` | no definido | **Interna:** evita recursión desde wrapper sudoers. |

## Validación

```bash
trinaxai config
trinaxai doctor
curl -k https://localhost:3333/health
```

Cambiar el modelo/dimensiones de embeddings o el comportamiento de chunking
requiere reindexar por completo. `POST /system/reload` solo refresca en memoria
una generación publicada; no reconstruye vectores. Nunca confirmes `.env`, tokens,
certificados locales, `storage/` ni `local_sources/`. Consulta la [guía de
solución de problemas](TROUBLESHOOTING.es.md) para el orden seguro de recuperación.

[English version](ENVIRONMENT_VARIABLES.md) · [Documentation index](README.es.md)
