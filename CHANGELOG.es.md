# Registro de cambios

Todos los cambios notables en TrinaxAI se documentan aquí. Este proyecto sigue el formato [Keep a Changelog](https://keepachangelog.com/).

## [Sin publicar]

### Añadido
- Preferencia global persistente para efectos de sonido y señales centralizadas de generación, herramientas, archivos, agente, voz, llamada, errores y confirmaciones.
- Trabajos persistentes de indexación con progreso real por etapa/página/chunk/lote, cancelación, reintento, deduplicación, timeouts y reconexión.
- Cobertura de regresión para ciclo de vida del micrófono, SSE, fallos/recuperación de indexación, duplicados, temporales y PDFs textuales de 160 páginas.

### Corregido
- STT y Call Mode comparten un único ciclo de micrófono y liberan pistas, Web Audio, reinicios, TTS y transcripciones pendientes al salir o desmontar.
- Las esperas del primer token y la indexación de adjuntos tienen límites recuperables en vez de carga infinita.
- Los PDFs grandes usan lotes acotados y CI/`make setup` completan correctamente una instalación limpia.
- Monitores globales, timers de notificaciones, vistas previas y listeners de subida liberan sus recursos.

### Cambiado
- Search Mode y RAG muestran errores recuperables explícitos; una indexación fallida nunca publica una generación parcial.

## [1.1.0] — 2026-07-14

### Añadido
- PWA local-first con chat de Ollama, RAG, voz, análisis de imágenes y acceso por teléfono/LAN
- Indexación de proyectos y carpetas con colecciones, seguimiento de progreso, cancelación y citas
- Fragmentación con conciencia AST para más de 15 lenguajes de programación mediante tree-sitter
- Recuperación híbrida (vectorial + BM25 + reranker opcional)
- Enrutamiento automático multi-modelo heurístico (sin sobrecarga de LLM)
- Gestor de servicios multiplataforma (systemd, launchctl, subprocess)
- CLI para desarrolladores (`trinaxai ask`, `trinaxai chat`, `trinaxai index`, `trinaxai doctor`, etc.)
- Paquete CLI modular (`trinaxai_cli/`) con subcomandos: browse, collections, doctor, export, index, memory, obsidian, research, watch
- Memoria de conversaciones (hechos explícitos de "recuerda que" persistidos localmente)
- Modo de investigación profunda con descomposición RAG en múltiples pasadas
- Búsqueda web opcional con DuckDuckGo, Brave Search o SearXNG y lectura acotada de páginas públicas
- Agente compartido por CLI/PWA con workspaces autorizados, aprobación por sesión y cancelación cooperativa
- Emparejamiento LAN por capacidades; el chat local permanece disponible sin exponer datos privados
- Observador del sistema de archivos para reindexado automático ante cambios
- Sincronización de estado compartido entre dispositivos mediante backend local
- Agregación de estadísticas de uso a partir de logs JSONL
- Interfaz bilingüe español/inglés con paridad automática de claves i18n
- Adjuntos de chat respaldados por el host con fallback IndexedDB para sesiones offline o backends antiguos
- Índice documental bilingüe y referencias específicas de API, CLI, configuración, arquitectura, instalación, PWA y desarrollo
- Tema oscuro/claro con detección de preferencia del sistema
- Instalabilidad PWA completa (iOS, Android, escritorio)
- HTTPS autofirmado para acceso local en LAN
- Configuración de integración con Continue.dev para VSCode
- Instaladores con un solo comando para Linux (install.sh), macOS (install.sh) y Windows (install.ps1)
- Herramienta de auditoría previa al lanzamiento (scripts/public_readiness.py)
- Prueba de estado del sistema (test_system.py)
- Componente de notificación de actualización PWA (PwaUpdater)
- Página de respaldo offline
- Sección FAQ en README

### Cambiado
- Identidad de producto más sólida: el asistente se identifica como TrinaxAI, no como el autor del proyecto
- Licenciado bajo AGPL-3.0-or-later
- Manifiesto PWA: corregida discrepancia de display, añadidas categorías, dir, lang, atajos, display_override
- Iconos PWA: eliminados tamaños duplicados de Apple touch icon, mejorado manejo de pantalla de inicio
- README reescrito con sección CLI, modelo de seguridad, FAQ y estructura mejorada
- SECURITY.md ampliado con modelo de amenazas y recomendaciones de despliegue

### Corregido
- La compactación del historial de chat evita errores de cuota en localStorage
- El preprocesamiento de imágenes evita errores OOM en el modelo de visión
- El modo de voz gestiona TTS a nivel de oración con soporte de interrupción
- KnowledgeBrowser era inaccesible desde el router de la aplicación
- La pantalla de inicio de iOS usaba un tamaño de icono incorrecto en todos los dispositivos
- El manifiesto PWA tenía discrepancia de modo de visualización (standalone vs fullscreen)
- Faltaban includeAssets en el precache del service worker (nuevas variantes de logo)
- backup.sh ahora valida el contenido del tarball antes de la extracción (protección contra path traversal)
- uninstall.sh ya no elimina unidades systemd antes de la confirmación del usuario
- El instalador de Ollama se enlaza a 127.0.0.1 por defecto (no 0.0.0.0)

### Seguridad
- Control de sistema LAN desactivado por defecto (estaba activado); opt-in explícito con --lan-system
- El endpoint PUT /app-state ahora requiere autorización de sistema
- collection_id saneado con _collection_slug antes de pasarlo al subproceso
- Token de administrador autogenerado al activar el control de sistema LAN
- bare except Exception reemplazado con tipos de excepción específicos en archivos Python
- create_ssl_context consolidado en una única implementación en config.py
- Eliminada dependencia requests no utilizada de requirements.txt
- Código muerto eliminado: importAndIndexFolder de api.ts, import ssl no utilizado de config.py

## [1.0.0] — 2026-06-28

### Añadido
- Publicación pública inicial de TrinaxAI.

[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
