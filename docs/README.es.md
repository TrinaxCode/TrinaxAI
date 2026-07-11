# Documentación de TrinaxAI

Este directorio es el punto de entrada a la documentación técnica y operativa de TrinaxAI. La documentación describe el código de la rama actual; cuando una opción o endpoint sea crítico, confirma también su valor en `.env.example` o en la especificación OpenAPI expuesta por FastAPI.

## Empieza aquí

| Necesidad | Documento |
|---|---|
| Instalar y usar TrinaxAI | [README principal](../README.es.md) |
| Entender los componentes y flujos | [Arquitectura](ARCHITECTURE.es.md) |
| Configurar modelos, red, RAG y PWA | [Referencia de configuración](CONFIGURATION.es.md) |
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
- Consulta [SUPPORT.es.md](../SUPPORT.es.md) para pedir ayuda y [SECURITY.es.md](../SECURITY.es.md) para reportar vulnerabilidades.

## Contribución y publicación

- [Contribuir](../CONTRIBUTING.es.md)
- [Código de conducta](../CODE_OF_CONDUCT.es.md)
- [Checklist de publicación](PUBLIC_RELEASE.es.md)
- [Changelog](../CHANGELOG.es.md)
- [Roadmap](../ROADMAP.es.md)

## Fuentes de verdad

Para evitar documentación desactualizada, estas son las fuentes autoritativas:

| Tema | Fuente |
|---|---|
| Dependencias y comandos Python | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| Comandos y flags de CLI | `trinaxai_cli/app.py` |
| Endpoints HTTP | `rag_api.py`, `app/routes/voice.py`, `/openapi.json` |
| Variables de entorno | `.env.example`, `config.py`, `service_manager.py`, `chat-pwa/vite.config.ts` |
| Scripts de frontend | `chat-pwa/package.json` |
| Manifest, caché y proxies PWA | `chat-pwa/vite.config.ts` |

## Convenciones de la documentación

- Los archivos sin sufijo están en inglés; los archivos `.es.md`, en español.
- Los comandos se ejecutan desde la raíz del repositorio salvo que se indique `cd chat-pwa`.
- Los puertos por defecto son `3334` (PWA), `3333` (API RAG) y `11434` (Ollama).
- Las rutas locales de datos (`storage/`, `local_sources/`, `logs/`, `backups/`) no deben versionarse.

