# Referencia de configuración de TrinaxAI

TrinaxAI lee configuración de variables de entorno y del archivo `.env` de la raíz. Copia la plantilla y cambia solo lo necesario:

```bash
cp .env.example .env
```

No confirmes `.env`, certificados ni tokens. Los valores de esta guía son los predeterminados de la rama actual; [`.env.example`](../.env.example) es la plantilla ejecutable.

## Cómo se carga

- El backend carga `.env` desde la raíz del repositorio.
- `service_manager.py` pasa el entorno a la API, Ollama y la PWA.
- Las variables `VITE_*` se incorporan al bundle durante `npm run build`; reconstruye la PWA tras cambiarlas.
- Las preferencias elegidas en la PWA se guardan con claves `tc-*` y pueden sobrescribir sus modelos de interfaz sin modificar `.env`.
- La CLI tiene un TOML independiente; consulta [CLI_REFERENCE.es.md](CLI_REFERENCE.es.md).

## Perfil y rendimiento

| Variable | Predeterminado | Valores / efecto |
|---|---:|---|
| `TRINAXAI_PROFILE` | `16gb` | `4gb`, `8gb`, `16gb`, `max`, `ultra`; ajusta modelos, contexto y concurrencia. |
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
| `TRINAXAI_MODEL_GENERAL` | `qwen3:4b-instruct-2507-q4_K_M` | Conversación general. |
| `TRINAXAI_MODEL_CODE` | `qwen2.5-coder:3b` | Código y tareas técnicas. |
| `TRINAXAI_MODEL_DEEP` | `qwen2.5-coder:7b` | Consultas complejas. |
| `TRINAXAI_MODEL_FAST` | `qwen3:4b-instruct-2507-q4_K_M` | Consultas breves. |
| `TRINAXAI_AUTO_ROUTE` | `1` | Selección heurística entre los modelos anteriores. |
| `TRINAXAI_LLM` / `TRINAXAI_LLM_HEAVY` | según perfil | Fallback cuando el auto-router está desactivado. |

Los nombres deben coincidir con `ollama list`. Descarga manualmente un modelo con `ollama pull NOMBRE`.

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
| `TRINAXAI_RERANK` | `0` | Activa reranking; requiere `requirements-rerank.txt`. |
| `TRINAXAI_INDEX_DIR` | padre del repo | Carpeta que usa `index.py`. |
| `TRINAXAI_INDEX_APPEND` | `0` | Si es `1`, no elimina del índice archivos ausentes. |
| `TRINAXAI_INDEX_BATCH_SIZE` | `100` | Archivos procesados por lote. |

Cambiar el modelo de embeddings, sus dimensiones o una estrategia de chunking requiere reindexar. Haz copia de `storage/` antes de reconstruir.

## Límites de archivos y extracción

| Variable | Predeterminado |
|---|---:|
| `TRINAXAI_MAX_FILE_BYTES` | 3 MiB |
| `TRINAXAI_DOCUMENT_MAX_FILE_BYTES` | 250 MiB |
| `TRINAXAI_UPLOAD_MAX_FILES` | `2500` |
| `TRINAXAI_UPLOAD_MAX_BYTES` | 512 MiB |
| `TRINAXAI_DOC_EXTRACT_MAX_BYTES` | 250 MiB |
| `TRINAXAI_DOC_EXTRACT_MAX_CHARS` | `120000` |
| `TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES` | 250 MiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES` | 1 GiB |
| `TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES` | `1000` |
| `TRINAXAI_OCR` | `0` |

OCR es opcional y necesita Tesseract, `pytesseract` y `pdf2image`; si no están disponibles, la extracción de PDF continúa sin OCR.

## Red, TLS y seguridad

| Variable | Predeterminado / ejemplo | Notas |
|---|---|---|
| `TRINAXAI_HOST` | `0.0.0.0` en la plantilla | Usa `127.0.0.1` si no necesitas LAN. |
| `TRINAXAI_PORT` | `3333` | Puerto de FastAPI. |
| `TRINAXAI_RAG_HTTPS` | `1` | HTTPS para la API administrada. |
| `TRINAXAI_CORS_ORIGINS` | orígenes PWA locales | Lista separada por comas; evita `*`. |
| `TRINAXAI_ALLOW_LAN_SYSTEM` | `0` | Autoriza endpoints protegidos desde una LAN privada. |
| `TRINAXAI_ADMIN_TOKEN` | vacío | Token de `X-Admin-Token`; usa un valor aleatorio largo. |
| `TRINAXAI_RATE_LIMIT_PER_MINUTE` | `30` | Límite independiente por bucket e IP. |
| `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Ventana del limitador. |
| `TRINAXAI_TLS_VERIFY` | `0` | Validación TLS de conexiones salientes del backend. |

El filtro CORS no es autenticación. No expongas `3333`, `3334` ni `11434` directamente a Internet; para acceso remoto usa una VPN o un proxy autenticado.

## PWA y proxy

| Variable | Uso |
|---|---|
| `TRINAXAI_FRONTEND_MODE` | `preview` sirve `dist/`; `dev` usa HMR. |
| `TRINAXAI_FRONTEND_URL` | URL reportada/abierta por las herramientas. |
| `TRINAXAI_RAG_TARGET` | Destino del proxy `/api/rag`. |
| `TRINAXAI_OLLAMA_TARGET` | Destino del proxy `/api/ollama`. |
| `VITE_TRINAXAI_RAG_BASE` | Base RAG de producción en el navegador. |
| `VITE_TRINAXAI_OLLAMA_BASE` | Base Ollama de producción. |
| `VITE_TRINAXAI_DEV_RAG_BASE` | Base RAG durante desarrollo. |
| `VITE_TRINAXAI_DEV_OLLAMA_BASE` | Base Ollama durante desarrollo. |
| `VITE_TRINAXAI_VISION_MODEL` | Modelo rápido de visión. |
| `VITE_TRINAXAI_VISION_QUALITY_MODEL` | Modelo de visión de calidad. |

La PWA usa por defecto rutas same-origin (`/api/rag` y `/api/ollama`), lo cual evita exponer Ollama al navegador. Reinicia servicios tras cambios de runtime y ejecuta `npm run build` tras cambios `VITE_*`.

## Voz

| Variable | Predeterminado | Uso |
|---|---:|---|
| `TRINAXAI_VOICE_STT_MODEL` | `base` | Modelo local de Whisper. |
| `TRINAXAI_VOICE_TTS_ENGINE` | autodetección | Fuerza backend TTS disponible. |
| `TRINAXAI_VOICE_MAX_AUDIO_BYTES` | 30 MiB | Máximo de audio STT. |
| `TRINAXAI_VOICE_TTS_MAX_CHARS` | `1200` | Máximo de texto TTS. |
| `TRINAXAI_VOICE_RATE_LIMIT_PER_MINUTE` | `30` | Reservado por la configuración de voz. |
| `TRINAXAI_PIPER_MODEL` | vacío | Ruta explícita a un modelo Piper. |

## Diagnóstico de configuración

```bash
trinaxai config
trinaxai doctor
curl -k https://localhost:3333/health
```

Si una variable parece no aplicarse, confirma si es de runtime o build-time, reinicia los servicios y revisa que se esté cargando el `.env` de la instalación correcta.
