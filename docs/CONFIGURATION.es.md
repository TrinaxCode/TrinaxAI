# Referencia de configuración de TrinaxAI

TrinaxAI lee configuración de variables de entorno y del archivo `.env` de la raíz. Copia la plantilla y cambia solo lo necesario:

```bash
cp .env.example .env
```

No confirmes `.env`, certificados ni tokens. Los valores de esta guía son los predeterminados de la rama actual; [`.env.example`](../.env.example) es la plantilla ejecutable.
El [inventario canónico de variables de entorno](ENVIRONMENT_VARIABLES.md)
reúne todas las variables `TRINAXAI_*` y `VITE_TRINAXAI_*` admitidas.

## Cómo se carga

- El backend carga `.env` desde la raíz del repositorio.
- `service_manager.py` pasa el entorno a la API, Ollama y la PWA.
- Las variables `VITE_*` se incorporan al bundle durante `npm run build`; reconstruye la PWA tras cambiarlas.
- Las preferencias elegidas en la PWA se guardan con claves `tc-*` y pueden sobrescribir sus modelos de interfaz sin modificar `.env`.
- La CLI tiene un TOML independiente; consulta [CLI_REFERENCE.es.md](CLI_REFERENCE.es.md).

## Perfil y rendimiento

| Variable | Predeterminado | Valores / efecto |
|---|---:|---|
| `TRINAXAI_PROFILE` | `16gb` | Instaladores: `8gb`, `16gb`, `max`, `ultra`; `4gb` es alias runtime de recursos bajos. |
| `TRINAXAI_PERFORMANCE_MODE` | `fast` | `fast`, `balanced`, `quality`; cambia recuperación y chunking. |
| `TRINAXAI_NUM_CTX` | según perfil | Ventana de contexto del LLM. |
| `TRINAXAI_NUM_THREAD` | `8` | Hilos CPU por solicitud. |
| `TRINAXAI_KEEP_ALIVE` | según perfil/modo | Tiempo que el modelo de chat permanece cargado (`0s`, `15m`, etc.). |
| `TRINAXAI_TIMEOUT` | `300` | Timeout de solicitudes a Ollama, en segundos. |
| `TRINAXAI_AGGRESSIVE_QUANT` | `0` | Activa el perfil de cuantización agresivo. |

Elige el perfil por RAM disponible, no por RAM total. Si hay cierres por memoria, reduce contexto, workers y tamaño del modelo antes de tocar el índice.

## Modelos y Ollama

| Variable | Valor de ejemplo | Propósito |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL usada por el backend. |
| `TRINAXAI_MODEL_GENERAL` | `granite4:3b` | Conversación general del perfil `16gb`; selección medida de baja latencia. |
| `TRINAXAI_MODEL_CODE` | `qwen2.5-coder:1.5b` | Código y tareas técnicas. |
| `TRINAXAI_MODEL_DEEP` | `qwen3.5:2b` | Consultas complejas del perfil `16gb`. |
| `TRINAXAI_MODEL_FAST` | `qwen3.5:0.8b` | Consultas breves del perfil `16gb`. |
| `TRINAXAI_AUTO_ROUTE` | `1` | Selección heurística entre los modelos anteriores. |
| `TRINAXAI_LLM` / `TRINAXAI_LLM_HEAVY` | según perfil | Fallback cuando el auto-router está desactivado. |

Los nombres deben coincidir con `ollama list`. Descarga manualmente un modelo con `ollama pull NOMBRE`.

El autorouter es determinista y local: clasifica la intención y las capacidades
necesarias sin hacer otra llamada al modelo. Respeta un modelo explícito si es
compatible e instalado; si no, elige un modelo instalado apto para chat, código,
razonamiento o herramientas. En el perfil normal `16gb`, `granite4:3b` es el
predeterminado general por su equilibrio medido de latencia/calidad;
`qwen3.5:2b` queda como modelo de razonamiento profundo.

## Sonidos de la PWA

**Configuración → General → Efectos de sonido** controla todas las señales de
interfaz que no son voz. La preferencia se guarda localmente, se aplica de
inmediato y persiste tras reiniciar. Al desactivarla, el administrador central
no crea `AudioContext` ni carga o reproduce audio de señales. STT y las
respuestas habladas se controlan por separado.

## Embeddings, recuperación e indexación

| Variable | Predeterminado | Propósito |
|---|---:|---|
| `TRINAXAI_EMBED_PRESET` | según perfil | `balanced` (`bge-m3`), `lite` (`nomic-embed-text`) o `fast` (`all-minilm`). |
| `TRINAXAI_EMBED` | según preset | Modelo de embeddings. |
| `TRINAXAI_EMBED_DIMS` | según preset | Dimensiones; cambiarlo exige reconstruir el índice. |
| `TRINAXAI_EMBED_WORKERS` | según perfil | Solicitudes de embedding concurrentes. |
| `TRINAXAI_EMBED_BATCH` | según perfil | Nodos por lote. |
| `TRINAXAI_EMBED_KEEP_ALIVE` | según perfil | Mantiene caliente el embedder. |
| `TRINAXAI_CHUNK_SIZE` | según modo | Tamaño de fragmentos de prosa. |
| `TRINAXAI_CHUNK_OVERLAP` | según modo | Solapamiento entre fragmentos. |
| `TRINAXAI_CODE_CHUNK_LINES` | `60` | Tamaño objetivo para código. |
| `TRINAXAI_SIMILARITY_TOP_K` | según perfil | Fragmentos finales entregados al LLM. |
| `TRINAXAI_FUSION_CANDIDATES` | según perfil | Candidatos por recuperador antes de fusionar. |
| `TRINAXAI_RETRIEVER_CACHE_MAX_COMBINATIONS` | `32` | Límite LRU de combinaciones activas de colecciones. |
| `TRINAXAI_RERANK` | `0` | Activa reranking; requiere `requirements-rerank.txt`. |
| `TRINAXAI_INDEX_DIR` | padre del repo | Carpeta que usa `index.py`. |
| `TRINAXAI_INDEX_APPEND` | `0` | Si es `1`, no elimina del índice archivos ausentes. |
| `TRINAXAI_INDEX_BATCH_SIZE` | `100` | Archivos procesados por lote. |
| `TRINAXAI_SOURCE_ID` | derivado de la raíz | Identidad estable de una raíz sincronizada independiente. |
| `TRINAXAI_INDEX_LOCK_TIMEOUT` | `3600` | Espera del writer lock cross-process. |
| `TRINAXAI_INDEX_TIMEOUT` | `3600` | Timeout del proceso indexador lanzado por la CLI. |
| `TRINAXAI_WATCH_INDEX_TIMEOUT` | `1800` | Timeout de cada indexador encolado por el watcher. |
| `TRINAXAI_WATCH_RELOAD_TIMEOUT` | `30` | Espera del watcher para que el backend recargue engines tras un indexado exitoso. |
| `TRINAXAI_WATCH_OUTPUT_MAX_BYTES` | `16384` | Cola máxima de stdout/stderr conservada por job del watcher. |

Cambiar embeddings, dimensiones o chunking exige reindexar. El manifest usa hash
de contenido y versión de pipeline; cada raíz tiene `source_id`, así que
sincronizar una segunda raíz en la colección no elimina la primera. Índice y
manifest se publican como generación con journal y rollback tras interrupción.

## Búsqueda web

| Variable | Predeterminado | Propósito |
|---|---:|---|
| `TRINAXAI_WEB_SEARCH_PROVIDER` | `auto` | `auto`, `duckduckgo`, `brave`, `searxng` o `disabled`. |
| `TRINAXAI_BRAVE_SEARCH_API_KEY` | vacío | Credencial de Brave Search; permanece solo en el backend. |
| `TRINAXAI_SEARXNG_URL` | vacío | URL de una instancia SearXNG propia con salida JSON habilitada. |
| `TRINAXAI_WEB_SEARCH_TIMEOUT` | `15` | Tiempo máximo por búsqueda saliente. |
| `TRINAXAI_WEB_SEARCH_MAX_RESULTS` | `6` | Fuentes web entregadas al modelo, entre 1 y 10. |

En `auto`, TrinaxAI prefiere Brave si hay una clave, luego SearXNG si hay una URL y finalmente DuckDuckGo sin credenciales. La consulta sale de la máquina únicamente cuando el botón del mundo está activo o el usuario pide explícitamente buscar en Internet.

Los mismos proveedores se administran en **PWA → Configuración → Búsqueda web**. Los valores se guardan únicamente en el backend, en `storage/web_search_settings.json` con permisos `0600`; la API solo devuelve estados de disponibilidad y nunca las claves. La precedencia es: variables de entorno, configuración administrada y valores predeterminados. Un campo de clave vacío conserva la existente; eliminar credencial y restablecer son acciones explícitas. Las URLs de SearXNG introducidas en la PWA deben ser HTTP(S) públicas, sin credenciales ni destinos privados.

## Límites de archivos y extracción

| Variable | Predeterminado |
|---|---:|
| `TRINAXAI_MAX_FILE_BYTES` | 3 MiB |
| `TRINAXAI_DOCUMENT_MAX_FILE_BYTES` | 512 MiB |
| `TRINAXAI_UPLOAD_MAX_FILES` | `2500` |
| `TRINAXAI_UPLOAD_MAX_BYTES` | 2 GiB |
| `TRINAXAI_DOC_EXTRACT_MAX_BYTES` | 512 MiB |
| `TRINAXAI_DOC_EXTRACT_MAX_CHARS` | `120000` |
| `TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES` | 512 MiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES` | 4 GiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES` | `1000` |
| `TRINAXAI_OCR` | `0` |

OCR es opcional. Además de Tesseract, la extracción rasterizada necesita dependencias Python y del sistema compatibles; si no están disponibles, la extracción de PDF continúa sin OCR.

Las subidas reciben un identificador de trabajo después de validarse y
guardarse; la conexión HTTP no permanece abierta durante extracción y
embeddings. PDFs, chunks y embeddings se procesan en lotes acotados. La PWA
muestra etapa persistida, tiempo, actividad reciente, páginas, chunks y lotes;
si una etapa no tiene denominador exacto se muestra como indeterminada. Los
timeouts `TRINAXAI_INDEX_STAGE_TIMEOUT` y `TRINAXAI_INDEX_TOTAL_TIMEOUT` son
configurables. Cancelar o fallar descarta generaciones no publicadas y limpia
temporales; los trabajos elegibles se pueden reintentar.

Search Mode informa proveedor deshabilitado/bloqueado, timeout o falta de
fuentes. RAG informa índice/modelo ausente, SSE interrumpido o timeout del primer
token. Son errores recuperables: la interfaz sale de espera, conserva la
conversación y permite reintentar; nunca inventa un resultado silencioso.

## Red, TLS y seguridad

| Variable | Predeterminado / ejemplo | Notas |
|---|---|---|
| `TRINAXAI_HOST` | `127.0.0.1` | Conserva FastAPI detrás del gateway local. |
| `TRINAXAI_UNSAFE_BIND_BACKEND` | `0` | Escape peligroso para permitir bind no-loopback; no lo habilites en LAN compartida/Internet. |
| `TRINAXAI_PORT` | `3333` | Puerto de FastAPI. |
| `TRINAXAI_RAG_HTTPS` | `1` | HTTPS para la API administrada. |
| `TRINAXAI_CA_FILE` | autodetectado | Bundle CA explícito para HTTPS verificado desde la CLI; también detecta raíces mkcert/autofirmadas locales. |
| `TRINAXAI_CORS_ORIGINS` | orígenes PWA locales | Lista separada por comas; evita `*`. |
| `TRINAXAI_ALLOW_LAN_SYSTEM` | `0` | Fallback legacy solo para sistema y sin token admin; prefiere pairing. |
| `TRINAXAI_ADMIN_TOKEN` | vacío | Supercredencial administradora; consérvala en el host. |
| `TRINAXAI_DEVICE_REGISTRY` | `storage/device_pairing.json` | Registro atómico modo `0600` con dispositivos/scopes y hashes con clave. |
| `TRINAXAI_DEVICE_SECRET_FILE` | `storage/.device_secret` | Clave modo `0600` para hashear códigos y tokens. |
| `TRINAXAI_DEVICE_TOKEN` | vacío | Bearer de una CLI emparejada; se envía como `X-TrinaxAI-Device-Token`. |
| `TRINAXAI_PROXY_SECRET_FILE` | `storage/.proxy_secret` | Clave HMAC privada gateway/backend, creada con modo `0600`. |
| `TRINAXAI_RATE_LIMIT_PER_MINUTE` | `30` | Capacidad del token bucket por IP verificada/bucket. |
| `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Segundos para recargar un bucket vacío a capacidad. |
| `TRINAXAI_TLS_VERIFY` | `0` | Validación TLS de conexiones salientes del backend. |

CORS no es autenticación. FastAPI y Ollama administrados quedan en loopback; el
gateway PWA es la frontera LAN. Bloquea 3333/11434 y usa VPN. Estado PWA,
adjuntos, fuentes, memoria, colecciones, índice/sistema y agente exigen auth,
incluidas sus lecturas.

Ejecuta `trinaxai pair start` en el host para emitir un código de un uso. Por
defecto concede `chat,read_private`; eleva a `index`, `system` o `agent` solo si
el dispositivo lo necesita. `trinaxai pair list` muestra el inventario y
`trinaxai pair revoke ID` invalida un equipo. La PWA guarda el bearer en
`localStorage` como identidad persistente del dispositivo; pairing administra
capabilities de dispositivo, no cuentas.

## PWA y proxy

| Variable | Uso |
|---|---|
| `TRINAXAI_FRONTEND_MODE` | `preview` sirve `dist/`; `dev` usa HMR. |
| `TRINAXAI_FRONTEND_URL` | URL reportada/abierta por las herramientas. |
| `TRINAXAI_RAG_TARGET` | Destino del proxy `/api/rag`. |
| `TRINAXAI_OLLAMA_TARGET` | Destino del proxy `/api/ollama`. |
| `TRINAXAI_OLLAMA_PROXY_RATE_LIMIT` | Solicitudes/minuto por peer en la fachada Ollama. |
| `TRINAXAI_INFERENCE_LOCK_FILE` | Lock compartido del scheduler gateway/backend. |
| `TRINAXAI_INFERENCE_QUEUE_TIMEOUT` | Espera máxima de la cola de inferencia. |
| `VITE_TRINAXAI_RAG_BASE` | Base RAG de producción en el navegador. |
| `VITE_TRINAXAI_OLLAMA_BASE` | Base Ollama de producción. |
| `VITE_TRINAXAI_DEV_RAG_BASE` | Base RAG durante desarrollo. |
| `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Base Ollama durante desarrollo. |
| `VITE_TRINAXAI_VISION_MODEL` | Modelo de visión; por defecto `qwen3-vl:4b-instruct` en 16GB y se descarga al primer análisis de imagen. |

`/api/rag` firma peer/método/ruta con la clave HMAC y `/api/ollama` publica una
allowlist reducida: no es proxy genérico. Los procesos comparten lock para que
chat, RAG y agente no eludan la cola. Reinicia tras runtime y recompila para
variables `VITE_*`.

## Agente

| Variable | Predeterminado | Uso |
|---|---:|---|
| `TRINAXAI_AGENT_WORKSPACE_ROOTS` | raíces indexadas + repo | Allowlist de raíces HTTP separadas por el separador de paths del SO. |
| `TRINAXAI_AGENT_HTTP_YOLO` | `0` | Autoaprobación HTTP solo en loopback real si se activa. |
| `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` | `0` | Escape de alto riesgo: shell con permisos completos del usuario. |

Las herramientas de archivo resuelven symlinks y rechazan escapes. En Linux el
shell exige bubblewrap sin red y solo deja el workspace escribible. Sin sandbox
compatible, falla cerrado salvo el opt-in explícito anterior.

## Voz

| Variable | Predeterminado | Uso |
|---|---:|---|
| `TRINAXAI_VOICE_STT_MODEL` | `base` | Modelo local de Whisper. |
| `TRINAXAI_VOICE_DEVICE` | `auto` | Device de `faster-whisper`, por ejemplo `cpu`/`cuda`. |
| `TRINAXAI_VOICE_COMPUTE_TYPE` | `default` | Tipo de cómputo compatible con el device. |
| `TRINAXAI_VOICE_TTS_ENGINE` | autodetección | Fuerza backend TTS disponible. |
| `TRINAXAI_VOICE_MAX_AUDIO_BYTES` | 30 MiB | Máximo de audio STT. |
| `TRINAXAI_VOICE_TTS_MAX_CHARS` | `1200` | Máximo de texto TTS. |
| `TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE` | `30` | Reservado por la configuración de voz. |
| `TRINAXAI_PIPER_MODEL` | vacío | Ruta explícita a un modelo Piper. |

## Diagnóstico de configuración

```bash
trinaxai config
trinaxai doctor --strict --json
curl -k https://localhost:3333/health
```

Si una variable parece no aplicarse, confirma si es de runtime o build-time, reinicia los servicios y revisa que se esté cargando el `.env` de la instalación correcta.
