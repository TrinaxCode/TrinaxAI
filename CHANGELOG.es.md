# Registro de cambios

Todos los cambios importantes de TrinaxAI se documentan aquí. El proyecto sigue
el formato de [Keep a Changelog](https://keepachangelog.com/).

## [Sin publicar]

### Añadido

- Se agregó `trinaxai network refresh` y un aviso accesible en la PWA para
  recuperar orígenes cacheados tras cambiar de Wi-Fi, router o dirección LAN.
- La copia offline permite borrar explícitamente su caché, datos locales y
  service worker para retirar una instalación guardada en una dirección anterior.
- Una dirección nueva detecta el estado existente del servidor y abre la
  recuperación por vinculación en vez de repetir la configuración inicial.

## [1.0.2] — 2026-08-01

### Corregido

- Inicialización del driver de contenedor de Buildx para publicar la imagen en
  GHCR con atestaciones de SBOM y procedencia.

## [1.0.1] — 2026-07-31

### Añadido

- Publicación de assets mediante un único workflow de release verificado.
- Cobertura del gateway de producción y pruebas multiplataforma de CLI,
  instaladores, servicios, cancelación, timeouts y rutas de error.

### Cambiado

- Los perfiles escalan embeddings Qwen3 oficiales desde 0.6B/1024d en equipos
  de 8/16 GB hasta 4B/2560d en `max` y 8B/4096d en `ultra`.
- Docker Compose puede iniciar con valores seguros aunque no exista `.env`.

### Corregido

- Se reforzaron timeouts de inferencia, verificación TLS, identidad del proxy,
  errores de API, limpieza de recursos y checks de Windows/macOS/Linux.

## [1.0.0] — 2026-07-21

### Añadido

- PWA local-first con chat de Ollama, RAG citado, investigación web opcional,
  visión, voz y emparejamiento de dispositivos por capacidades.
- Indexación híbrida de proyectos y documentos con colecciones, chunks de código
  con AST, progreso persistente, cancelación, reintento y publicación incremental segura.
- Una sola CLI empaquetada, `trinaxai`, para chat, agente, indexación,
  investigación, memoria, colecciones, watcher, pairing, diagnóstico y servicios.
- Agente con herramientas limitado a workspaces aprobados, confirmación para
  acciones peligrosas y shell Linux aislada sin red.
- Instaladores y supervisión multiplataforma para Linux, macOS y Windows, además
  de documentación bilingüe de producto y técnica.

### Cambiado

- Los perfiles automáticos cubren desde equipos con poca memoria hasta sistemas
  con 64+ GB y usan embeddings multilingües `qwen3-embedding:0.6b` por defecto.
- La PWA incluye iconos de instalación renovados, un modo llamada más claro y
  animaciones accesibles que respetan la reducción de movimiento.
- La CLI mantiene HTTPS verificado y acepta autoridades privadas mediante
  `--ca-file` o `TRINAXAI_CA_FILE`.

### Corregido

- Los saludos simples en modo automático de la CLI usan el chat normal de Ollama
  en vez de forzar una búsqueda RAG vacía.
- Los fallos de generación, RAG, investigación, agente, memoria, pairing,
  servicios y búsqueda web terminan de forma predecible y conservan el estado.
- Los streams del micrófono, nodos de Web Audio, timers, previews y listeners de
  subida se liberan al cancelar, navegar o recibir un error.
- Los documentos y subidas grandes usan lotes, timeouts y limpieza acotados; una
  indexación fallida nunca publica una generación parcial.
- El paquete expone solo la CLI modular y genera wheel, archivo fuente,
  instaladores y checksums coherentes.

### Seguridad

- Las URLs base de Ollama se restringen centralmente a endpoints HTTP(S) válidos
  antes del acceso de red desde backend, CLI, agente y diagnósticos.
- Las aserciones del proxy se firman, caducan y son de un solo uso; las operaciones
  protegidas exigen pairing con scope o credenciales administrativas explícitas.
- CI revisa dependencias Python/frontend, hallazgos estáticos de severidad alta,
  secretos, paquetes, flujos del navegador y preparación para release pública.

[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
