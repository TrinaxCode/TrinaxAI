# Referencia de API de TrinaxAI

La API RAG es un servidor FastAPI (puerto por defecto **3333**) que impulsa la PWA, la CLI y cualquier integración de terceros. Los endpoints de sistema requieren autorización. Los endpoints de chat están abiertos, pero limitados por la allowlist CORS configurada.

---

## Autenticación

Los endpoints de sistema (`/system/*`, `/app-state`, `/v1/memory`, CRUD de colecciones) requieren autorización:

- **localhost** — permitido por defecto.
- **LAN privada** — desactivada por defecto. Actívala explícitamente con `TRINAXAI_ALLOW_LAN_SYSTEM=1`.
- **Token de administrador** — configura `TRINAXAI_ADMIN_TOKEN` en `.env` y pásalo como cabecera `X-Admin-Token: <token>`.

Los endpoints de chat (`/v1/chat/completions`, `/health`) están abiertos a los orígenes de confianza (filtro CORS sobre IPs privadas + puertos 3334/3335).

---

## Chat y Recuperación

### `POST /v1/chat/completions`

Endpoint de chat compatible con OpenAI, con recuperación RAG. Soporta streaming SSE.

**Petición:**
```json
{
  "model": "auto",
  "messages": [
    {"role": "user", "content": "How does the auth module work?"},
    {"role": "assistant", "content": "..."}
  ],
  "stream": true,
  "collections": ["default", "my-project"]
}
```

**Respuesta (streaming SSE):**
```
data: {"trinaxai":{"model":"qwen2.5-coder:7b","project":"Insider"}}
data: {"choices":[{"delta":{"content":"The auth module..."}}]}
data: {"trinaxai_sources":[{"file":"auth.py","snippet":"...","score":0.89}]}
data: [DONE]
```

**Sin streaming:**
```json
{
  "choices": [{"message": {"role": "assistant", "content": "..."}}],
  "trinaxai": {"model": "qwen2.5-coder:7b", "sources": [...]}
}
```

| Campo | Notas |
|---|---|
| `model` | `"auto"` (por defecto) o cualquier nombre de modelo de Ollama |
| `stream` | `true` para SSE, `false` para respuesta JSON única |
| `collections` | Lista opcional de IDs de colección en las que buscar |

---

### `POST /v1/research`

Consulta de investigación profunda multi-pasada con descomposición en sub-preguntas.

**Petición:**
```json
{
  "query": "Compare authentication patterns across the project",
  "depth": 2,
  "collections": ["default"]
}
```

**Respuesta:** Stream SSE con resultados de cada pasada de investigación y síntesis final.

---

## Control del Sistema

### `POST /system/shutdown`

Apaga Ollama + la API RAG. **Requiere autorización.**

Devuelve `{"ok": true, "output": "AI shutdown initiated. ..."}`.

### `POST /system/startup`

Inicia Ollama + la API RAG. **Requiere autorización.**

Devuelve `{"ok": true|false, "output": "...", "error": "..."}`.

### `POST /system/stop-all`

Detiene todos los servicios inmediatamente. **Requiere autorización.**

### `POST /system/reload`

Recarga en caliente el índice RAG desde `storage/`. **Requiere autorización.**

Devuelve `{"ok": true}` o error.

### `POST /system/self-test`

Ejecuta verificaciones de salud automatizadas: Ollama, embeddings, consulta RAG. **Requiere autorización.**

Devuelve `{"ok": true|false, "results": {"ollama": bool, "embedding": bool, "rag_query": bool, "rag_indexed": bool}}`.

---

## Indexación

### `POST /system/index-upload`

Sube una carpeta para indexarla (selector de archivos del navegador). **Requiere autorización.**

**Petición:** `multipart/form-data` con los archivos de una carpeta.

**Respuesta:** `{"job_id": "abc123", "status": "starting"}`

### `GET /system/index-jobs/{job_id}`

Consulta el progreso de un trabajo de indexación.

**Respuesta:**
```json
{
  "status": "indexing",
  "progress": 65,
  "phase": "embedding",
  "eta": 12
}
```

### `POST /system/index-jobs/{job_id}/cancel`

Cancela un trabajo de indexación en ejecución. **Requiere autorización.**

---

## Colecciones

### `GET /collections`

Lista todas las colecciones RAG.

**Respuesta:** `["default", "my-project", "docs"]`

### `POST /collections`

Crea una colección. **Requiere autorización.**

**Petición:** `{"name": "My Project"}`

### `PUT /collections/{collection_id}`

Renombra una colección. **Requiere autorización.**

**Petición:** `{"name": "New Name"}`

### `DELETE /collections/{collection_id}`

Elimina una colección y todos sus chunks. **Requiere autorización.**

---

## Explorador de Conocimiento

### `GET /v1/sources`

Lista los archivos indexados con el conteo de chunks en una colección.

**Query:** `?collection=default`

**Respuesta:**
```json
[
  {"file": "app/auth.py", "project": "Insider", "chunks": 45, "collection": "General"}
]
```

### `GET /v1/sources/{file_path}`

Obtiene todos los chunks de un archivo específico.

**Query:** `?collection=default&limit=50`

---

## Memoria

### `GET /v1/memory`

Lista todas las entradas de memoria persistente.

**Respuesta:** `[{"id": "abc", "text": "User prefers Python", "tags": ["pref"]}]`

### `POST /v1/memory`

Añade una entrada de memoria. **Requiere autorización.**

**Petición:** `{"text": "User prefers Python 3.12+", "tags": ["pref", "python"]}`

### `DELETE /v1/memory/{memory_id}`

Elimina una entrada de memoria. **Requiere autorización.**

### `POST /v1/memory/refresh`

Regenera el auto-resumen a partir de las entradas de memoria. **Requiere autorización.**

### `GET /v1/memory/summary`

Obtiene el texto del auto-resumen actual.

---

## Vigilante de Archivos

### `POST /v1/watch/start`

Inicia el vigilante del sistema de archivos. **Requiere autorización.** Requiere el paquete pip `watchdog`.

**Petición:** `{"paths": ["/home/user/projects"], "collection": "default"}`

### `POST /v1/watch/stop`

Detiene el vigilante de archivos. **Requiere autorización.**

### `GET /v1/watch/status`

Obtiene el estado del vigilante: en ejecución, rutas monitorizadas, conteo de eventos.

---

## Estadísticas

### `GET /v1/stats`

Obtiene estadísticas de uso desde `storage/usage.jsonl`.

**Respuesta:**
```json
{
  "total_messages": 1523,
  "estimated_tokens": 450000,
  "top_models": {"qwen2.5-coder:3b": 800},
  "top_collections": {"default": 1200}
}
```

---

## Salud y Telemetría

### `GET /health`

Resumen del estado del sistema.

**Respuesta:**
```json
{
  "status": "ok",
  "models": ["qwen2.5-coder:3b", "llama3.2:3b", "bge-m3"],
  "indexed": true,
  "profile": "16gb",
  "projects": ["Insider", "MyApp"],
  "features": {"reranker": false, "ocr": false, "watcher": false}
}
```

### `GET /resources`

Telemetría básica de RAM/VRAM local. Requiere `psutil`.

**Respuesta:**
```json
{
  "ram": {"total_gb": 32, "used_gb": 12, "percent": 37.5},
  "ollama_processes": 2
}
```

---

## Estado de la App (Sincronización entre Dispositivos)

### `GET /app-state`

Lee la configuración compartida almacenada en `storage/app_state.json`.

### `PUT /app-state`

Guarda el estado compartido (ajustes, historial de chat, preferencias). **Requiere autorización.**

**Petición:** `{"values": {"theme": "dark", "language": "en"}}`

### `DELETE /app-state`

Restablecimiento total del estado compartido a los valores por defecto del host. **Requiere autorización.**

---

## Extracción de Documentos

### `POST /documents/extract`

Extrae texto de PDF/DOCX/TXT para análisis temporal (no se indexa).

**Petición:** `multipart/form-data` con el archivo.

**Respuesta:** `{"ok": true, "name": "doc.pdf", "text": "...", "chars": 5000, "truncated": false}`

---

## Códigos de Error

| HTTP | Significado |
|---|---|
| 200 | Éxito |
| 400 | Petición incorrecta (parámetros faltantes, datos inválidos) |
| 401 | No autorizado (endpoint de sistema sin token) |
| 404 | No encontrado (colección, trabajo, memoria) |
| 429 | Límite de tasa excedido (30 peticiones/min por IP) |
| 500 | Error interno |
| 501 | No implementado (ej., watchdog no instalado) |
| 503 | Servicio no disponible (Ollama caído, índice no cargado) |

---

## Límite de Tasa

- **30 peticiones por minuto** por dirección IP
- Ventana: 60 segundos deslizantes
- Afecta: completaciones de chat y endpoints de sistema
- Devuelve HTTP 429 cuando se supera el límite
