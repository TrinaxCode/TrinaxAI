# Registro de cambios

Todos los cambios notables en TrinaxAI se documentan aquí. Este proyecto sigue el formato [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] — 2026-06-27

### Añadido
- PWA local con chat de Ollama, RAG, voz, análisis de imágenes y acceso por teléfono/LAN
- Indexación de proyectos y carpetas con colecciones, seguimiento de progreso, cancelación y citas
- Fragmentación con conciencia AST para más de 15 lenguajes de programación mediante tree-sitter
- Recuperación híbrida (vectorial + BM25 + reranker opcional)
- Enrutamiento automático multi-modelo heurístico (sin sobrecarga de LLM)
- Gestor de servicios multiplataforma (systemd, launchctl, subprocess)
- Memoria de conversaciones (hechos explícitos de "recuerda que" persistidos localmente)
- Modo de investigación profunda con descomposición RAG en múltiples pasadas
- Observador del sistema de archivos para reindexado automático ante cambios
- Sincronización de estado compartido entre dispositivos mediante backend local
- Agregación de estadísticas de uso a partir de logs JSONL
- Interfaz bilingüe español/inglés con sistema i18n
- Tema oscuro/claro con detección de preferencia del sistema
- Instalabilidad PWA completa (iOS, Android, escritorio)
- HTTPS autofirmado para acceso local en LAN
- Configuración de integración con Continue.dev para VSCode
- Instaladores con un solo comando para Linux (install.sh), macOS (install.sh) y Windows (install.ps1)
- Herramienta de auditoría previa al lanzamiento (scripts/public_readiness.py)
- Prueba de estado del sistema (test_system.py)
- Pipeline de CI con verificación DCO, compilación de Python, verificación de tipos TypeScript y build

### Cambiado
- Identidad de producto más sólida: el asistente se identifica como TrinaxAI, no como el autor del proyecto
- Licenciado bajo AGPL-3.0-or-later
- query.py marcado como obsoleto en favor del paquete trinaxai_cli/

### Corregido
- La compactación del historial de chat evita errores de cuota en localStorage
- El preprocesamiento de imágenes evita errores OOM en el modelo de visión
- El modo de voz gestiona TTS a nivel de oración con soporte de interrupción

[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
