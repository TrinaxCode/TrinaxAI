<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🩺 Solución de problemas
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="TROUBLESHOOTING.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

TrinaxAI muestra un mensaje de recuperación cuando una solicitud no puede
terminar. Empieza por la acción que aparece en la PWA o la CLI; esta página es
el respaldo cuando la acción no está disponible, no es clara o el problema
regresa. No borres `storage/` como primer paso: contiene índices, colecciones,
memoria, estado y datos de recuperación. Haz una copia antes de cualquier
mantenimiento destructivo.

## Ruta rápida

| Síntoma | Primera acción |
|---|---|
| **La colección seleccionada no contiene documentos indexados.** | Pulsa **Abrir indexación** en el aviso, elige una carpeta y colección en **Configuración → Indexación** y espera a que termine el job. Seleccionar o adjuntar un archivo no lo indexa automáticamente. |
| No se encontró la colección seleccionada. | Abre **Configuración → Indexación → Colecciones**, elige una colección existente o crea una, selecciónala en el chat y reintenta. En CLI: `trinaxai collections list`. |
| Un job de indexación falló o se detuvo. | Abre **Configuración → Indexación**, revisa la fase que falló y pulsa **Reintentar**. Reindexa solo después de revisar la fuente, el modelo y la memoria disponible. |
| La PWA dice que el servicio local está desconectado. | En el host, pulsa **Encender IA** en la PWA local o ejecuta `trinaxai status` y `trinaxai doctor`. |
| Falta un modelo. | Ejecuta `ollama list` y luego `ollama pull MODELO`, o usa la acción de modelos en **Configuración → General**. Confirma que coincida con el perfil activo. |
| Un modelo no carga o se agotó la memoria. | Detén cargas competidoras, elige un modelo/perfil menor, reduce concurrencia o contexto y reintenta. No elimines el índice salvo que haya cambiado la configuración de embeddings. |
| Un teléfono no puede abrir la PWA. | Ejecuta `trinaxai network refresh` en el host, abre la URL HTTPS impresa, confía en la CA pública desde el teléfono y permite solo el puerto `3334`. Mantén `3333` y `11434` cerrados a la LAN. |
| El modo de búsqueda no encuentra la web. | Revisa el proveedor configurado y la conexión a Internet. El RAG local no necesita Internet; usa RAG cuando la respuesta deba venir de archivos indexados. |
| La interfaz quedó desactualizada después de actualizar o cambiar de red. | Acepta la actualización de la PWA, recarga una vez y, si hace falta, elimina el service worker/datos del sitio del origen anterior. Ejecuta `trinaxai network refresh` después de cambiar la dirección LAN. |

## Qué significa la acción de recuperación

La PWA combina una explicación segura con la siguiente acción útil cuando
reconoce el error:

- **Abrir indexación** aparece para una colección RAG vacía o inexistente. Abre
  la zona de indexación del host; el dispositivo aún necesita permiso para
  hacer ese cambio.
- **Reintentar** es adecuado para errores temporales de red, proveedor,
  timeout o jobs fallidos. No cambia la fuente ni la colección.
- **Encender IA** inicia los servicios locales desde el host. Un teléfono
  emparejado no puede administrar el ciclo de vida del host.
- **Abrir configuración** se usa para configurar modelos, perfiles y proveedores.

Un adjunto usado como contexto de chat no es lo mismo que una fuente indexada.
Para que una carpeta esté disponible en futuros turnos RAG, indexa la carpeta en
una colección y espera un job correcto. Después selecciona esa colección en el
chat y reintenta la pregunta.

## Diagnóstico en orden

Ejecuta la comprobación más pequeña que responda a la pregunta actual. Los
comandos parten de la raíz del repositorio salvo que se indique lo contrario.

```bash
# 1. Estado de servicios y comprobaciones básicas
trinaxai status
trinaxai doctor

# 2. Resultado JSON determinista para scripts o soporte
trinaxai doctor --strict --json

# 3. Proveedor y modelos instalados
ollama list
```

Para comprobar directamente la salud local, prefiere el bundle de CA que muestra
`trinaxai network`:

```bash
curl --cacert RUTA_A_CA_PUBLICA.pem https://localhost:3333/health
```

`curl -k https://localhost:3333/health` solo es aceptable como diagnóstico de
loopback cuando el certificado local aún no es de confianza. Nunca uses `-k`
para hacer segura una conexión LAN no confiable y nunca expongas directamente
la API ni los puertos de Ollama a la red.

Las rutas de logs más útiles son `logs/rag_api.log`, `logs/frontend.log`,
`logs/supervisor.log` y `logs/recovery.log`. Contienen request IDs y estado de
diagnóstico; aun así, redacta el paquete antes de compartirlo.

## Tablas de decisión

### RAG e indexación

| Comprobación | Significado | Siguiente paso |
|---|---|---|
| La colección está vacía | No hay una fuente publicada en la colección seleccionada. | Abre indexación, elige la colección correcta, indexa una carpeta/archivo compatible y espera el estado `completed`. |
| El job sigue ejecutándose | La nueva generación aún no se publicó. | Mantén la página abierta o reconecta al job; no inicies otro job completo para la misma raíz. |
| El job falló | La generación actual queda protegida; la generación fallida no se publicó. | Lee la fase y la actividad reciente, corrige fuente/modelo/recursos y usa **Reintentar**. |
| Hay fuentes, pero las respuestas no tienen evidencia | El chat puede usar otra colección, un índice en memoria antiguo o no hubo chunks relevantes. | Confirma las colecciones activas, inspecciona **Fuentes** y recarga el backend con `POST /system/reload` desde el host si cambió la configuración. |
| Cambiaron el modelo, dimensiones o estrategia de chunks | Los vectores existentes ya no son compatibles. | Haz backup de `storage/`, ejecuta una reindexación completa y espera la publicación antes de consultar. |
| Falta un solo archivo | Puede no ser compatible, legible, estar excluido o fuera de la raíz seleccionada. | Revisa el resultado del job y la extensión; usa `trinaxai browse list-files` e inspecciona la ruta. |

`reload` refresca un índice publicado en memoria; no crea embeddings y no
sustituye una reindexación.

### Modelos y recursos

| Síntoma | Comprobación | Acción |
|---|---|---|
| `model not found` | `ollama list` | Descarga el modelo configurado exacto o elige uno instalado en Configuración. |
| Falló la carga del modelo | RAM/VRAM y perfil activo | Elige un modelo menor, reduce contexto/concurrencia, cierra cargas y reintenta. |
| Embeddings lentos | `TRINAXAI_EMBED_KEEP_ALIVE`, workers y batch | Mantén el embedder activo durante un lote; reduce workers/batch si falta memoria. |
| GPU no disponible | Estado del hardware y perfil seleccionado | Usa el perfil/modelo compatible con CPU o habilita la GPU. |
| Las solicitudes agotan el tiempo | `trinaxai doctor`, tamaño del modelo/archivo y logs recientes | Reduce la solicitud, usa un archivo/modelo menor y reintenta antes de aumentar límites. |

Los perfiles canónicos son `8gb`, `16gb`, `32gb` y `64gb`. `max` y `ultra` son
alias de compatibilidad antiguos, no perfiles actuales adicionales.

### PWA, LAN y HTTPS

| Síntoma | Comprobación | Acción |
|---|---|---|
| La PWA del host no carga | `trinaxai status` y puerto local `3334` | Inicia la PWA/gestor y abre `https://localhost:3334`. Si usaste **Detener TODO**, abre recovery por loopback y pulsa **Encender IA**. |
| El teléfono no conecta | URL del host, firewall y puerto `3334` | Ejecuta `trinaxai network refresh`, usa la nueva URL HTTPS, permite solo `3334` y confía en la CA pública desde el dispositivo. |
| Persiste el aviso de certificado | Instalación de CA y hostname de la URL | Instala la CA/perfil público en ese dispositivo y usa la IP o hostname `.local` impreso. No transfieras la clave privada ni desactives la verificación. |
| Las acciones están deshabilitadas remotamente | Scope efectivo y origen | Administra indexación, modelos, ciclo de vida, Agent y dispositivos desde `https://localhost:3334` en el host. Pairing no equivale a administración del host. |
| Sigue apareciendo la dirección anterior o una interfaz vacía | Caché/service worker por origen | Elimina los datos del origen PWA anterior, abre la URL actual y acepta la actualización. |

### Búsqueda web, Agent y voz

- La búsqueda web requiere proveedor configurado e Internet. Ejecuta el
  preflight de Investigación o revisa **Configuración → Búsqueda web**; un
  proveedor desactivado no es un fallo de indexación.
- Las acciones de archivos de Agent requieren un workspace registrado y pueden
  pausar para aprobación. Un dispositivo LAN emparejado no puede usar Agent ni
  administrar shell del host.
- La voz depende de permisos del navegador, hardware de audio y extras Python
  opcionales. Comprueba `GET /v1/voice/capabilities`; un `501` indica que el
  motor local no está instalado o disponible.

### Almacenamiento y recuperación

- Antes de actualizar, cambiar modelos o reindexar por completo, ejecuta
  `./backup.sh` y conserva `.env` aparte sin publicarlo.
- Reintenta o cancela un job fallido antes de eliminar datos. Las generaciones
  fallidas o canceladas no sustituyen una generación funcional.
- Si **Detener TODO** fue intencional, la página de recovery solo en el host en
  `https://localhost:3334/` es esperada. Inicia los servicios allí; no borres
  `storage/`.
- Si recovery no abre, revisa `storage/recovery.pid` y `logs/recovery.log`, luego
  usa `trinaxai status` desde el host. Escala el problema antes de quitar
  archivos de estado manualmente.

## Contrato de errores para integraciones

Los clientes de API deben usar campos estructurados en lugar de comparar el
mensaje en inglés:

```json
{
  "detail": {"category": "...", "code": "...", "message": "...", "recovery": "...", "retryable": true},
  "error": {"category": "...", "code": "...", "message": "...", "recovery": "...", "retryable": true},
  "request_id": "..."
}
```

El frontend también reconoce códigos RAG legacy como `collection_empty` y
`collection_not_found` y los mapea a **Abrir indexación**. Las categorías
canónicas incluyen `ai_model_unavailable`, `model_loading_failed`,
`permission_denied`, `authentication_failed`, `resource_exhausted`,
`memory_limit_reached`, `file_not_found`, `document_unreadable`,
`invalid_input`, `unsupported_format`, `network_timeout` e
`internal_server_error`. Respeta `retryable` y `Retry-After`; conserva el
`request_id` para soporte, pero no muestres ni registres tokens o contenido
privado.

Consulta el [contrato completo de errores de la API](API_REFERENCE.es.md#errores),
la [referencia de configuración](CONFIGURATION.es.md) y la [referencia de CLI](CLI_REFERENCE.es.md).

## Paquete para soporte

Cuando la primera acción no resuelva el problema, incluye:

1. Versión de TrinaxAI, sistema operativo, Python, Node.js, Ollama, RAM/GPU y
   perfil activo.
2. La acción o comando exacto, hora aproximada y si la solicitud vino de
   localhost o de un dispositivo emparejado.
3. Salida redactada de `trinaxai doctor --strict --json`, estado relevante y el
   `request_id` de la API.
4. Colección, tipo de archivo, modelo/perfil y el ID del job de indexación
   afectado, pero no el contenido del archivo.
5. El fragmento relevante de log con tokens, API keys, rutas privadas, prompts y
   documentos personales eliminados.

Abre un issue comunitario después de revisar [Soporte](SUPPORT.es.md). Envía las
vulnerabilidades sospechadas mediante [Seguridad](SECURITY.es.md), no en un
issue público.
