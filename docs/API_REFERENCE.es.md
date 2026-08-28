# Referencia de API de TrinaxAI

[English](API_REFERENCE.md)

La API FastAPI conecta la PWA y la CLI con el índice RAG, la memoria, la voz y la administración local. Por defecto escucha en `https://localhost:3333`; la URL depende de `TRINAXAI_HOST`, `TRINAXAI_PORT` y TLS.

Las instalaciones administradas prefieren HTTPS. Usa la CA pública que imprime
`trinaxai network` en los clientes de API; HTTP directo es solo un fallback de
desarrollo en loopback. Los clientes LAN deben entrar por el gateway PWA del
puerto `3334`, confiar en la CA pública desde su dispositivo y no conectarse
directamente al puerto `3333` ni a Ollama `11434`. Para una ruta de recuperación
por síntoma, consulta [Solución de problemas](TROUBLESHOOTING.es.md).

Documentación generada en una instancia activa:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

## Autorización y límites

Los endpoints protegidos de bajo riesgo aceptan peer loopback directo,
credencial de dispositivo con scope (`X-TrinaxAI-Device-Token`) o credencial
admin (`X-Admin-Token`). Los scopes exclusivos del host (`system`, `index`,
`agent` y `agent_yolo`) exigen primero procedencia loopback original verificada;
ninguna credencial ni ajuste LAN legacy evita ese requisito. El gateway local elimina cabeceras de
identidad del cliente y firma peer, método y ruta con HMAC fresca y de un uso.
FastAPI solo acepta esa firma desde loopback o un peer privado de runtime
configurado explícitamente que además demuestre la clave compartida; nunca usa
`Forwarded`/`X-Forwarded-For` como identidad.

Chat, STT y TTS usan token buckets monotónicos separados por IP verificada. La
capacidad general es 30 y un bucket vacío se recarga en 60 segundos.

```bash
curl -k https://localhost:3333/health
curl -k -H "X-Admin-Token: $TOKEN" https://localhost:3333/v1/memory
curl -k -H "X-TrinaxAI-Device-Token: $DEVICE_TOKEN" https://localhost:3333/v1/memory
```

Los scopes de dispositivo disponibles son `chat`, `read_private` y `web`; el
pairing concede `chat` y `read_private` por defecto. Se rechazan solicitudes de
scopes retirados (`index`, `system`, `agent`, `agent_yolo`) y se ignoran en tokens
antiguos. Un token admin puede autenticar lecturas protegidas, pero no convierte
un peer LAN en localhost. Una credencial inválida nunca se ignora por ser loopback.

## Resumen de endpoints

| Método y ruta | Protección | Propósito |
|---|---|---|
| `POST /v1/chat/completions`, `/v1/research` | `chat` + rate limit | Chat e investigación. |
| `POST /v1/agent`, `/v1/agent/approve`, `/v1/agent/cancel`, `GET /v1/agent/browse` | Solo loopback | Stream de agente, aprobación/cancelación y raíces registradas. |
| `GET/POST /v1/voice/*` | `chat` + rate limit | Reconocimiento y síntesis de voz. |
| `POST /documents/extract` | LAN/VPN o `chat` + rate limit | Extracción temporal sin persistencia. |
| `GET /v1/sources` | `read_private` | Archivos indexados por colección. |
| `GET /v1/sources/{collection}/{file}/chunks` | `read_private` | Chunks paginados. |
| `DELETE /v1/sources/*` | Solo loopback | Elimina archivo o colección de fuentes. |
| `GET /v1/memory/*`, `POST /v1/memory/context` / escrituras de memoria | `read_private` / loopback (`system`) | Lectura versus mutación de memoria privada. |
| `POST/GET /v1/watch/*` | Solo loopback | Administra watcher. |
| `POST /v1/usage`, `GET /v1/stats` | `chat` / `read_private` | Métricas locales. |
| `GET /health`, `GET /ready`, `GET /resources` | Pública | Vida del servicio, disponibilidad de Ollama y RAM local. |
| `GET/PUT/DELETE /v1/settings/web-search*` | Solo loopback | Configuración local del proveedor web y borrado de credenciales. |
| `GET/PUT /app-state` / `DELETE /app-state` | `read_private` / loopback (`system`) | Estado PWA versionado / reset total. |
| `POST /attachments`, `GET /attachments/{id}` / `DELETE /attachments/{id}`, `POST /attachments/{id}/open` | `read_private` / loopback (`system`) | Guardar/recuperar versus eliminar/abrir adjuntos en el host. |
| `GET /collections` / mutaciones | `read_private` / solo loopback | Colecciones. |
| `/system/index*` / resto `/system/*` | Solo loopback | Índice versus lifecycle/autoprueba. |
| `/v1/pairing/*` | Mixto | Pairing de dispositivos y revocación. |

## Contrato de errores

Cada error de API devuelve un objeto `error` seguro (y los mismos campos
canónicos en `detail`): `category`, `code` interno, `message` para el usuario, `recovery` y
`retryable`. Las categorías son `internet_unavailable`,
`external_service_unavailable`, `ai_model_unavailable`, `model_loading_failed`,
`tool_timeout`, `permission_denied`, `authentication_failed`,
`resource_exhausted`, `memory_limit_reached`, `gpu_unavailable`,
`file_not_found`, `document_unreadable`, `invalid_input`, `unsupported_format`,
`network_timeout`, `internal_server_error` y `unknown_error`. Los detalles de
excepciones quedan solo en los registros de desarrollador del servidor; se
devuelve `request_id` para soporte. Las lecturas idempotentes seguras se
reintentan una vez cuando `retryable` es `true`. Respuestas RAG antiguas pueden
usar los códigos legacy `collection_empty` o `collection_not_found`; la PWA los
convierte en la acción **Abrir indexación**. Los clientes deben usar
`category`, `code`, `recovery` y `retryable`, no comparar el texto localizado.

## Pairing de dispositivos

Solo loopback real puede crear un código; una credencial admin desde LAN no basta:

```http
POST /v1/pairing/start
{"scopes":["chat","read_private"],"ttl_seconds":300,"device_ttl_days":null}
```

El código en claro se devuelve una vez. Un cliente de LAN/VPN lo consume con
`POST /v1/pairing/claim {"code":"ABCD-EFGH","device_name":"Teléfono"}`.
Hay un límite de cinco intentos por cliente cada cinco minutos. La respuesta
fija una cookie `HttpOnly; SameSite=Strict` con alcance `/api/rag` y contiene
metadatos del dispositivo, pero no un bearer. En disco solo quedan hashes con
clave. Los códigos duran entre 60 y 900 segundos y son single-use.

La PWA envía esa cookie automáticamente y no persiste tokens recién obtenidos
en `localStorage` ni `sessionStorage`. Por compatibilidad, un bearer guardado por
una versión anterior solo se envía como cabecera
`X-TrinaxAI-Device-Token` durante la migración explícita de
`GET /v1/pairing/me`; después de una respuesta exitosa la PWA elimina el valor
legacy. La CLI sigue usando esa cabecera, por ejemplo mediante
`TRINAXAI_DEVICE_TOKEN`. Registro y secreto de hashing son archivos atómicos
separados modo `0600`. Pairing autentica dispositivo/capability; no es sistema
multiusuario.

`GET /v1/pairing/me` y `DELETE /v1/pairing/me` aceptan la cookie; la cabecera
legacy sigue soportada para clientes CLI y la migración. `GET /v1/pairing/devices`
y `DELETE /v1/pairing/devices/{id}` requieren loopback real. La revocación afecta
tanto FastAPI como el gateway de Ollama.

## Chat RAG

### `POST /v1/chat/completions`

Compatible en forma básica con completions de chat de OpenAI:

```json
{
  "model": null,
  "messages": [{"role": "user", "content": "¿Cómo funciona la autorización?"}],
  "stream": true,
  "collections": ["default"],
  "mode": "knowledge",
  "think": true,
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

- `messages`: 1–100 objetos; roles `system`, `user` o `assistant`; 100,000 caracteres por mensaje, 200,000 en total y al menos un mensaje `user`.
- `model`: `null`/vacío activa el router; también acepta un nombre de Ollama.
- `collections`: hasta 50 IDs.
- `mode`: `auto` clasifica si necesita evidencia; `knowledge` siempre recupera y
  responde solo con evidencia recuperada (o indica que no hay índice/evidencia);
  `model` desactiva retrieval aunque la frase parezca referirse a documentos.

En el enrutamiento conversacional automático, el cliente elige la capacidad antes de llamar a su endpoint: una consulta pública directa como `Busca quién es TrinaxCode` usa búsqueda web; una pregunta sobre proyectos propios como `¿Qué programas de Python he hecho?` usa `knowledge`; y una investigación compleja con varias fuentes usa `/v1/research`. La ejecución con Agent nunca se infiere por las palabras: entra explícitamente en modo Agent antes de llamar a `/v1/agent`. `route_model()` solo elige el modelo; no elige web, RAG, investigación ni Agent.

- `think`: preferencia explícita del cliente. `false` desactiva el razonamiento;
  `true` lo permite solo en tareas analíticas o complejas; si se omite usa
  `TRINAXAI_THINKING_MODE`. Los turnos simples no usan ese canal.
- `stream=false`: devuelve `chat.completion` JSON con `choices` y `trinaxai.sources`;
  `trinaxai.abstained` es `true` cuando no hay índice, la colección está vacía,
  no se encontró evidencia relevante o el modelo rechaza explícitamente responder
  sin evidencia del contexto suministrado.
- `stream=true`: devuelve `text/event-stream`.

Eventos SSE posibles:

```text
data: {"trinaxai":{"model":"...","project":null,"phase":"retrieving"}}
data: {"choices":[{"delta":{"content":"texto"}}]}
data: {"trinaxai_sources":[{"file":"...","snippet":"...","score":0.8}]}
data: [DONE]
```

La respuesta no-stream incluye modo, `rag_used`, colecciones, conteo, request ID,
fuentes y uso explícitamente estimado. SSE añade retrieval, uso, timing y
**heurísticas de calidad** post-stream. Estas heurísticas detectan omisiones o
salida probablemente mal formada; no equivalen a compilar, typecheckear, probar
en navegador ni demostrar corrección. Si no hay índice, responde un mensaje
informativo sin fuentes en vez de fallar.

### Configuración de búsqueda web

`GET|PUT|DELETE /v1/settings/web-search` lee, actualiza o restablece la configuración local del host. `POST /v1/settings/web-search/test` prueba el proveedor desde el backend y `DELETE /v1/settings/web-search/credentials/brave` elimina explícitamente la clave administrada. Todas son exclusivas del host y exigen procedencia loopback verificada; los secretos son de solo escritura y nunca se serializan.

### `POST /v1/research`

```json
{
  "query": "Compara los mecanismos de persistencia",
  "collections": ["default"],
  "depth": 2,
  "think": true,
  "model": null,
  "keep_alive": "10m",
  "aggressive_quant": false
}
```

`depth` se normaliza a 1–3. La respuesta añade `web_search`, `web_provider` y
`search_query`. La investigación web busca y después intenta leer un conjunto
acotado de páginas. Cada fuente marca `content_scope: full_page` cuando extrajo
texto de página o `snippet_only` con `fetch_error` cuando solo quedó el extracto
del buscador. El fetch rechaza credenciales, esquemas no HTTP, destinos
privados/loopback/link-local y redirects inseguros; resuelve una vez y conecta a
la IP pública validada, con topes de redirects, bytes, texto y tiempo. `full_page`
sigue siendo extracción acotada, no copia integral del sitio.

`POST /v1/research/preflight` acepta el mismo request y comprueba Ollama, el
modelo elegido, las colecciones locales y el proveedor web sin ejecutar la
investigación completa.

Si un proveedor web no está disponible, la investigación devuelve un estado
degradado en vez de un error vacío: explica el motivo clasificado, no inventa
fuentes web y etiqueta cualquier respuesta alternativa como conocimiento general
del modelo local.

## Fuentes y colecciones

```http
GET /v1/sources?collection=default
GET /v1/sources/default/path/to/file.py/chunks?source_id=ID&limit=50&offset=0&q=texto
DELETE /v1/sources/default/path/to/file.py?source_id=ID
```

La ruta puede contener `/` y debe codificarse. Una colección puede incluir la
misma ruta relativa desde varias raíces; usa el `source_id` de la lista para
seleccionar una sin eliminar su homónima. La lista responde
`{collection,sources}` y chunks incluye también `source_id`. `limit`: 1–500.

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
POST /system/index-jobs/{job_id}/retry
```

El estado persiste entre reconexiones del frontend e informa etapa, tiempo transcurrido, actividad reciente, contadores de páginas/chunks/lotes y si `progress` es exacto. Los trabajos fallidos o cancelados pueden reintentarse mientras la fuente subida siga disponible. `DELETE /system/index-imports` recibe `{"path":"...","collection_id":"..."}` y solo acepta rutas internas seguras de importaciones locales.

## Memoria, watcher y métricas

```http
GET    /v1/memory
POST   /v1/memory             {"text":"...","tags":["estilo"],"kind":"preference","provenance":"manual","expires_at":null}
PATCH  /v1/memory/{id}        {"text":"...","kind":"decision","clear_expiration":true}
DELETE /v1/memory/{id}
POST   /v1/memory/context     {"query":"turno actual","max_entries":8}
POST   /v1/memory/refresh     {"scope":null}
GET    /v1/memory/summary

POST /v1/watch/start          {"paths":["/ruta"],"collection":"default"}
POST /v1/watch/stop
GET  /v1/watch/status

POST /v1/usage               {"engine":"ollama","model":"...","est_tokens":100}
GET  /v1/stats
```

Los tipos son `fact`, `preference`, `decision` y `note`; provenance es `manual`
o `inferred`, y se excluyen entradas expiradas. `/context` devuelve solo
memorias activas relevantes. PWA, CLI y backend las delimitan como datos no
confiables, nunca instrucciones. El resumen global es una vista para la persona
y no se inyecta en turnos. La PWA confirma el borrado y permite editar tipo,
provenance y expiración. Su scratchpad local `tc-project-memory` tampoco entra al
prompt.

El watcher requiere `watchdog` y solo acepta directorios existentes. Las estadísticas se almacenan localmente.

## Estado compartido

- GET exige autorización y devuelve `{ok,schema_version:2,revision,values}` con
  ETag `"trinaxai-app-state-v2-N"`; `If-None-Match` puede producir `304`.
- PUT envía `schema_version:2`, `device_id`, `base_revision` y operaciones
  ordenadas `set`/`delete`. Solo aplica el lote atómicamente si coincide la
  revisión; un escritor obsoleto recibe `409` con estado actual para merge/retry.
  `If-Match` puede transportar la misma revisión.
- El formato legacy `{"values":...}` solo se admite con concurrencia optimista
  (o sobre store vacío en revisión cero); si no, devuelve `428`.
- DELETE exige autorización y `X-TrinaxAI-Confirm: reset-app-state`; incrementa
  la revisión para que un dispositivo offline anterior no restaure el estado.

El estado compartido tiene un límite predeterminado de 6 MiB (`TRINAXAI_APP_STATE_MAX_BYTES`).

## Adjuntos, documentos y voz

POST acepta un multipart autorizado y lo guarda en
`storage/chat_attachments/`; GET/DELETE exigen la misma autorización y tienen
rate limit. Devuelve `id`, nombre, tamaño, MIME y `storage_key server:`.
`POST /attachments/{attachment_id}/open` pide al sistema del host abrir el
archivo con su aplicación predeterminada y también exige autorización/rate
limit. Los tipos desconocidos se descargan con `nosniff`. El historial conserva
la referencia al adjunto, no otra copia persistente del texto completo. Límites:
512 MiB por archivo, 4 GiB total y 1,000 archivos.

## Agente

`POST /v1/agent` transmite eventos SSE y una herramienta peligrosa pausa en
`approval_request` hasta `/v1/agent/approve`.
El modelo decide si responde directamente o llama una o varias herramientas,
ordena las llamadas dependientes y sintetiza sus resultados. Búsqueda web,
investigación profunda, memoria, búsqueda documental y descubrimiento de
colecciones están disponibles por defecto. Los booleanos `web_search`,
`deep_research` y `knowledge_search` solo restringen disponibilidad; nunca
fuerzan la ejecución. `POST /v1/agent/cancel` detiene una sesión activa de la
misma identidad. La aprobación debe incluir el
`session_id` del evento `start` y el `approval_id`,
y usar la misma identidad autenticada que abrió el stream. El workspace debe descender de
`TRINAXAI_AGENT_WORKSPACE_ROOTS`; se rechazan raíces del sistema. Yolo HTTP está
apagado y, aun activado, solo funciona por transporte loopback real con
`agent_yolo`. Todo agente remoto aprueba cada acción peligrosa. Las herramientas de archivo
rechazan escapes por path/symlink. En Linux el shell exige bubblewrap sin red y
solo el workspace es escribible; en hosts sin aislamiento falla cerrado salvo
opt-in explícito a acceso completo del usuario con
`TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1`.

`POST /documents/extract` acepta un archivo multipart y devuelve `{ok, name, text, chars, truncated}`. Soporta extracción especializada de PDF, DOCX y PPTX, y decodificación de formatos de texto. No indexa ni conserva el documento, por lo que un dispositivo sin emparejar puede usarlo desde la LAN o VPN. Los clientes de redes públicas aún necesitan el scope `chat`. Los límites se documentan en [CONFIGURATION.es.md](CONFIGURATION.es.md).

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
| `POST /system/stop-all` | Detiene todo; solo queda la recuperación por loopback en `https://localhost:3334` y la LAN permanece cerrada hasta iniciar localmente. |
| `POST /system/reload` | Recarga el índice en memoria. |
| `POST /system/self-test` | Comprueba Ollama, embeddings e índice/RAG. |
| `GET /health` | Modelos, perfil activo/detectado, hardware, recomendaciones, índice, colecciones y capacidades. |
| `GET /ready` | El mismo estado; responde `503` hasta que Ollama esté disponible. |
| `GET /resources` | RAM y VRAM detectada en bytes, además de la instantánea de hardware. |

## Errores

FastAPI usa `{"detail": {...}, "error": {...}, "request_id": "..."}`. `detail`
puede incluir un código o pista de campo segura por compatibilidad, pero nunca
texto crudo de una excepción. Las respuestas reintentables incluyen
`Retry-After: 1`. Los estados más relevantes son `400` (entrada inválida), `403`
(autorización), `404`, `409` (confirmación requerida), `413` (límite), `422`
(validación/extracción), `429`, `500`, `501` y `503`. Consulta la [guía de
solución de problemas](TROUBLESHOOTING.es.md) y la [configuración](CONFIGURATION.es.md)
para recuperación, límites y red.
