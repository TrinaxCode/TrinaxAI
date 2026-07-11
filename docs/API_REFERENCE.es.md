# Referencia de API de TrinaxAI

La API FastAPI conecta la PWA y la CLI con el índice RAG, la memoria, la voz y la administración local. Por defecto escucha en `https://localhost:3333`; la URL depende de `TRINAXAI_HOST`, `TRINAXAI_PORT` y TLS.

Documentación generada en una instancia activa:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

## Autorización y límites

Los endpoints marcados como **protegidos** aceptan la solicitud cuando ocurre una de estas condiciones:

1. El peer TCP es loopback.
2. `X-Admin-Token` coincide con el token configurado.
3. El peer pertenece a una red privada y `TRINAXAI_ALLOW_LAN_SYSTEM` está activado.

Un token enviado pero incorrecto produce `403`. La implementación no confía en `X-Forwarded-For`. Si colocas un reverse proxy, conserva esta frontera o añade autenticación en el proxy.

Chat, STT y TTS tienen buckets separados por IP. Los valores generales son 30 solicitudes por 60 segundos y se configuran con `TRINAXAI_RATE_LIMIT_PER_MINUTE` y `TRINAXAI_RATE_LIMIT_WINDOW_SECONDS`.

```bash
curl -k https://localhost:3333/health
curl -k -H "X-Admin-Token: $TOKEN" https://localhost:3333/v1/memory
```

## Resumen de endpoints

| Método y ruta | Protección | Propósito |
|---|---|---|
| `POST /v1/chat/completions` | Rate limit | Chat RAG JSON o SSE. |
| `POST /v1/research` | Protegido | Investigación RAG multipasada. |
| `GET /v1/voice/capabilities` | Pública | Motores locales de voz disponibles. |
| `POST /v1/voice/stt` | Rate limit | Audio multipart a texto. |
| `POST /v1/voice/tts` | Rate limit | Texto JSON a audio. |
| `GET /v1/sources` | Protegido | Archivos indexados por colección. |
| `GET /v1/sources/{collection}/{file}/chunks` | Protegido | Chunks paginados de un archivo. |
| `DELETE /v1/sources/{collection}/{file}` | Protegido | Elimina chunks de un archivo. |
| `DELETE /v1/sources/{collection}` | Protegido | Vacía una colección no predeterminada. |
| `GET/POST /v1/memory` | Protegido | Lista o crea memorias. |
| `DELETE /v1/memory/{memory_id}` | Protegido | Elimina una memoria. |
| `POST /v1/memory/refresh` | Protegido | Regenera el resumen. |
| `GET /v1/memory/summary` | Protegido | Lee el resumen. |
| `POST/GET /v1/watch/*` | Protegido | Inicia, detiene o consulta el watcher. |
| `POST /v1/usage`, `GET /v1/stats` | Protegido | Métricas locales. |
| `GET /health`, `GET /resources` | Pública | Salud y RAM local. |
| `GET /app-state` | Pública | Estado compartido con ETag. |
| `PUT/DELETE /app-state` | Protegido | Sincroniza o restablece estado. |
| `POST /attachments`, `GET /attachments/{attachment_id}` | Pública | Persiste/recupera adjuntos del chat. |
| `POST /documents/extract` | Pública | Extracción temporal de documento. |
| `GET /collections` | Pública | Lista metadatos de colecciones. |
| `POST/PATCH/DELETE /collections/*` | Protegido | Administra colecciones. |
| `/system/*` | Protegido | Servicios, índice y autoprueba. |

## Chat RAG

### `POST /v1/chat/completions`

Compatible en forma básica con completions de chat de OpenAI:

```json
{
  "model": null,
  "messages": [{"role": "user", "content": "¿Cómo funciona la autorización?"}],
  "stream": true,
  "collections": ["default"],
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

- `messages`: 1–100 objetos; roles `system`, `user` o `assistant`; máximo total de 2,000,000 caracteres y al menos un mensaje `user`.
- `model`: `null`/vacío activa el router; también acepta un nombre de Ollama.
- `collections`: hasta 50 IDs.
- `stream=false`: devuelve `chat.completion` JSON con `choices` y `trinaxai.sources`.
- `stream=true`: devuelve `text/event-stream`.

Eventos SSE posibles:

```text
data: {"trinaxai":{"model":"...","project":null,"phase":"retrieving"}}
data: {"choices":[{"delta":{"content":"texto"}}]}
data: {"trinaxai_sources":[{"file":"...","snippet":"...","score":0.8}]}
data: [DONE]
```

Si no hay índice, responde un mensaje informativo sin fuentes en vez de fallar.

### `POST /v1/research`

```json
{
  "query": "Compara los mecanismos de persistencia",
  "collections": ["default"],
  "depth": 2,
  "model": null,
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`depth` se normaliza a 1–3. La respuesta es JSON, no SSE: `answer`, `sub_questions`, `sources`, `passes` y `model`.

## Fuentes y colecciones

```http
GET /v1/sources?collection=default
GET /v1/sources/default/path/to/file.py/chunks?limit=50&offset=0&q=texto
DELETE /v1/sources/default/path/to/file.py
```

La ruta del archivo puede contener `/` y debe codificarse como URL. La lista responde `{collection, sources}`; chunks responde `{collection, file, total, chunks, query}`. `limit` se restringe a 1–500.

Colecciones:

```http
GET    /collections
POST   /collections                 {"name":"Documentación"}
PATCH  /collections/{collection_id} {"name":"Nuevo nombre"}
DELETE /collections/{collection_id}
```

`GET /collections` devuelve `{ok, collections}`. La colección `default` no puede eliminarse. Borrar metadatos de colección y vaciar sus fuentes son operaciones diferentes.

## Indexación desde navegador

`POST /system/index-upload` recibe `multipart/form-data`:

| Campo | Tipo / valor inicial |
|---|---|
| `files` | Uno o más archivos; requerido. |
| `label` | Texto; `import`. |
| `collection_id` | Texto; `default`. |
| `embed_model` | Texto opcional. |
| `aggressive_quant` | Booleano; `false`. |
| `watch_id` | Texto opcional para importaciones sincronizadas. |

La respuesta contiene `job_id`, ruta local, archivos guardados/omitidos, bytes y colección. El trabajo continúa en segundo plano:

```http
GET  /system/index-jobs/{job_id}
POST /system/index-jobs/{job_id}/cancel
```

`DELETE /system/index-imports` recibe `{"path":"...","collection_id":"..."}` y solo acepta rutas internas seguras de importaciones locales.

## Memoria, watcher y métricas

```http
GET    /v1/memory
POST   /v1/memory             {"text":"...","tags":["preferencia"]}
DELETE /v1/memory/{id}
POST   /v1/memory/refresh     {"scope":null}
GET    /v1/memory/summary

POST /v1/watch/start          {"paths":["/ruta"],"collection":"default"}
POST /v1/watch/stop
GET  /v1/watch/status

POST /v1/usage               {"engine":"ollama","model":"...","est_tokens":100}
GET  /v1/stats
```

El watcher requiere `watchdog` y solo acepta directorios existentes. Las estadísticas se almacenan localmente.

## Estado compartido

- `GET /app-state` devuelve `{ok, values}` y `ETag`; acepta `If-None-Match` y puede responder `304`.
- `PUT /app-state` acepta `{"values":{"tc-clave":"valor-string"}}`; solo conserva claves `tc-*` y valores string.
- `DELETE /app-state` exige además `X-TrinaxAI-Confirm: reset-app-state`; limpia el estado de ejecución local y devuelve los elementos eliminados.

El estado compartido tiene un límite predeterminado de 6 MiB (`TRINAXAI_APP_STATE_MAX_BYTES`).

## Adjuntos, documentos y voz

`POST /attachments` recibe un archivo multipart y lo guarda bajo `storage/chat_attachments/` para que las conversaciones sincronizadas puedan abrirlo desde otros navegadores. Devuelve `id`, nombre, tamaño, MIME y una `storage_key` con prefijo `server:`. `GET /attachments/{attachment_id}` muestra inline imágenes, PDF y texto seguros; los tipos desconocidos se descargan con `nosniff`. `DELETE /attachments/{attachment_id}` está protegido como las operaciones de sistema. Los límites predeterminados son 250 MiB por archivo, 1 GiB total y 1,000 archivos retenidos. Las cargas y descargas tienen rate limiting. Estos endpoints siguen siendo públicos dentro de la frontera de red configurada: no expongas la API a clientes no confiables.

`POST /documents/extract` acepta un archivo multipart y devuelve `{ok, name, text, chars, truncated}`. Soporta extracción especializada de PDF, DOCX y PPTX, y decodificación de formatos de texto. No indexa el contenido. Los límites se documentan en [CONFIGURATION.es.md](CONFIGURATION.es.md).

Voz:

```http
GET  /v1/voice/capabilities
POST /v1/voice/stt   multipart: file, lang=es
POST /v1/voice/tts   {"text":"Hola","lang":"es"}
```

TTS devuelve bytes de audio con su `Content-Type`. STT/TTS responden `501` cuando no hay motor local instalado.

## Sistema y diagnóstico

| Endpoint | Resultado |
|---|---|
| `POST /system/shutdown` | Detiene IA, mantiene la PWA. |
| `POST /system/startup` | Inicia servicios de IA. |
| `POST /system/stop-all` | Detiene todo. |
| `POST /system/reload` | Recarga el índice en memoria. |
| `POST /system/self-test` | Comprueba Ollama, embeddings e índice/RAG. |
| `GET /health` | Modelos, perfil, índice, colecciones y capacidades. |
| `GET /resources` | RAM en bytes; VRAM actualmente `null`. |

## Errores

FastAPI usa `{"detail":"mensaje"}` para errores HTTP. Los más relevantes son `400` (entrada inválida), `403` (autorización), `404`, `409` (confirmación requerida), `413` (límite), `422` (validación/extracción), `429`, `500`, `501` y `503`.
