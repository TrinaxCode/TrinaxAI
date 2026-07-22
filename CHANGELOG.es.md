# Registro de cambios

Todos los cambios importantes de TrinaxAI se documentan aquí. El proyecto sigue
el formato de [Keep a Changelog](https://keepachangelog.com/).

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
- Contenedor oficial de la API RAG en GitHub Container Registry con la etiqueta
  versionada `1.0.0` y las etiquetas móviles `1.0`, `1` y `latest`.

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

[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
