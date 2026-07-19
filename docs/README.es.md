# Documentación de TrinaxAI

Este directorio es el punto de entrada a la documentación técnica y operativa de **TrinaxAI 1.2.0**, publicado bajo **AGPL-3.0-or-later**. La documentación describe el código de la rama actual; cuando una opción o endpoint sea crítico, confirma también su valor en `.env.example` o en la especificación OpenAPI expuesta por FastAPI.

## Capacidades de 1.2.0

| Área | Incluye | Referencia |
|---|---|---|
| Chat e IA local | Ollama, streaming, router multimodelo y pipeline por tipo de tarea | [Arquitectura](ARCHITECTURE.es.md) |
| RAG | Indexación AST, vector + BM25, reranker, citas, colecciones y explorador de fuentes | [Configuración](CONFIGURATION.es.md) |
| Internet | Búsqueda web opcional con DuckDuckGo/Brave/SearXNG, lectura segura de páginas e investigación profunda | [API](API_REFERENCE.es.md) |
| Agente | CLI y PWA, herramientas de archivos/shell, workspace, sandbox y aprobaciones | [CLI](CLI_REFERENCE.es.md) |
| Multimodal | Visión, adjuntos, extracción documental, STT y TTS | [PWA](../chat-pwa/README.es.md) |
| Datos locales | Memoria, historial, sincronización, estadísticas, watcher y backups | [Arquitectura](ARCHITECTURE.es.md) |
| Dispositivos | PWA instalable, shell offline, LAN, pairing por scopes y revocación | [Seguridad](es/SECURITY.md) |
| Operación | Instaladores, actualizador, gestor de servicios, doctor y perfiles de hardware | [README](../README.es.md) |

## Empieza aquí

| Necesidad | Documento |
|---|---|
| Instalar y usar TrinaxAI | [README principal](../README.es.md) |
| Entender los componentes y flujos | [Arquitectura](ARCHITECTURE.es.md) |
| Configurar modelos, red, RAG y PWA | [Referencia de configuración](CONFIGURATION.es.md) |
| Consultar cualquier variable de entorno | [Inventario de variables](ENVIRONMENT_VARIABLES.md) |
| Usar la terminal | [Referencia de CLI](CLI_REFERENCE.es.md) |
| Integrar un cliente HTTP | [Referencia de API](API_REFERENCE.es.md) |
| Desarrollar y depurar | [Guía del desarrollador](DEVELOPER_GUIDE.es.md) |
| Trabajar en la interfaz | [Documentación de la PWA](../chat-pwa/README.es.md) |

## Instalación por plataforma

- [Linux](INSTALL_LINUX.es.md)
- [macOS](INSTALL_MACOS.es.md)
- [Windows](INSTALL_WINDOWS.es.md)

## Operación y mantenimiento

- La configuración parte de [`.env.example`](../.env.example); no confirmes `.env` al repositorio.
- Usa `trinaxai doctor` para diagnóstico y `trinaxai status` para estado de servicios.
- Usa `./backup.sh` antes de cambios de versión o modificaciones del índice.
- Consulta [soporte](es/SUPPORT.md) para pedir ayuda y [seguridad](es/SECURITY.md) para reportar vulnerabilidades.

## Proyecto y contribución

- [Contribuir](es/CONTRIBUTING.md)
- [Código de conducta](es/CODE_OF_CONDUCT.md)
- [Changelog](../CHANGELOG.es.md)

## Fuentes de verdad

Para evitar documentación desactualizada, estas son las fuentes autoritativas:

| Tema | Fuente |
|---|---|
| Dependencias y comandos Python | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| Comandos y flags de CLI | `trinaxai_cli/app.py` |
| Endpoints HTTP | `app/routes/`, `app/main.py`, `/openapi.json` |
| Variables de entorno | `docs/ENVIRONMENT_VARIABLES.md`, `.env.example` |
| Scripts de frontend | `chat-pwa/package.json` |
| Manifest, caché y proxies PWA | `chat-pwa/vite.config.ts` |

## Convenciones de la documentación

- Los archivos sin sufijo están en inglés; los archivos `.es.md`, en español.
- Los comandos se ejecutan desde la raíz del repositorio salvo que se indique `cd chat-pwa`.
- Los puertos por defecto son `3334` (PWA), `3333` (API RAG) y `11434` (Ollama).
- Las rutas locales de datos (`storage/`, `local_sources/`, `logs/`, `backups/`) no deben versionarse.
