<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 📚 Documentación
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Este directorio es el punto de entrada a la documentación técnica y operativa de **TrinaxAI 1.2.1**, la release actual Production/Stable bajo **AGPL-3.0-or-later**. La documentación describe la rama de release; cuando una opción o endpoint sea crítico, confirma también su valor en `.env.example`, `chat-pwa/package.json` o en la especificación OpenAPI expuesta por FastAPI.

Para la vista general del producto, las capturas y los benchmarks, consulta la web oficial: **[trinaxai.app](https://www.trinaxai.app/)**.

> Estado del release: `v1.2.1` es la release actual Production/Stable. Sus paquetes fuente, instaladores, wheel, checksums y firmas separadas están publicados en GitHub. Los instaladores están fijados y nunca vuelven a `main`.

## Capacidades actuales

| Área | Incluye | Referencia |
|---|---|---|
| Chat e IA local | Ollama, streaming, router multimodelo y pipeline por tipo de tarea | [Arquitectura](ARCHITECTURE.es.md) |
| RAG | 16 parsers de código conscientes de AST, fallback de texto, vector + BM25, reranker, citas, colecciones y explorador de fuentes | [Configuración](CONFIGURATION.es.md) |
| Internet | Búsqueda web opcional con DuckDuckGo/Brave/SearXNG, lectura segura de páginas e investigación profunda | [API](API_REFERENCE.es.md) |
| Agente | CLI y PWA, herramientas de archivos/shell, workspace, sandbox y aprobaciones | [CLI](CLI_REFERENCE.es.md) |
| Multimodal | Visión, adjuntos, extracción documental, STT y TTS | [PWA](../chat-pwa/README.es.md) |
| Datos locales | Memoria, historial, sincronización, estadísticas, watcher y backups | [Arquitectura](ARCHITECTURE.es.md) |
| Dispositivos | PWA instalable, shell offline, LAN, pairing por scopes y revocación | [Seguridad](SECURITY.es.md) |
| Operación | Instaladores, actualizador, gestor de servicios, doctor y perfiles de hardware | [README](../README.es.md) |

## Empieza aquí

Para una instalación normal, ejecuta el comando de una línea de tu plataforma. No necesitas Git:

```bash
set -e; version="1.2.1"; base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"; installer="$(mktemp)"; trap 'rm -f "$installer"' EXIT; curl -fsSL "$base/TrinaxAI-${version}-installer.sh" -o "$installer"; expected="$(curl -fsSL "$base/SHA256SUMS" | awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }')"; actual="$( (shasum -a 256 "$installer" 2>/dev/null || sha256sum "$installer") | awk '{print $1}' )"; test "$expected" = "$actual"; bash "$installer"
```

En Windows PowerShell usa el mismo flujo de revisar antes de ejecutar con un instalador fijado al release:

```powershell
$ErrorActionPreference="Stop"; $version="1.2.1"; $base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"; $installer=Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"; Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer; $line=Invoke-RestMethod -Uri "$base/SHA256SUMS" | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1; $expected=if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash; if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }; & $installer
```

El instalador valida el paquete fuente firmado y su manifiesto SHA-256. Para
revisión manual o verificación GPG independiente, consulta
[firma de releases](RELEASE_SIGNING.es.md).

| Necesidad | Documento |
|---|---|
| Instalar, actualizar o desinstalar desde una terminal | [README principal](../README.es.md#inicio-rápido) |
| Entender los componentes y flujos | [Arquitectura](ARCHITECTURE.es.md) |
| Configurar modelos, red, RAG y PWA | [Referencia de configuración](CONFIGURATION.es.md) |
| Consultar cualquier variable de entorno | [Inventario de variables](ENVIRONMENT_VARIABLES.es.md) |
| Comparar perfiles y mediciones de modelos locales | [Benchmark de modelos](MODEL_BENCHMARK.es.md) |
| Usar la terminal | [Referencia de CLI](CLI_REFERENCE.es.md) |
| Integrar un cliente HTTP | [Referencia de API](API_REFERENCE.es.md) |
| Desarrollar y depurar | [Guía del desarrollador](DEVELOPER_GUIDE.es.md) |
| Resolver un fallo o recuperar un servicio | [Solución de problemas y recuperación](TROUBLESHOOTING.es.md) |
| Trabajar en la interfaz | [Documentación de la PWA](../chat-pwa/README.es.md) |
| Validar instaladores y comprobaciones de release | [Guía de pruebas](../TESTING.es.md) |
| Vincular un teléfono y confiar en HTTPS local | [Guía de pairing LAN](NETWORK_PAIRING.es.md) |
| Firmar assets de escritorio del release | [Firma de releases](RELEASE_SIGNING.es.md) |
| Leer la guía integrada de la app | Abre **Configuración → Documentación** en la PWA o consulta la [documentación de la PWA](../chat-pwa/README.es.md) |

## Instalación por plataforma

- [Linux](INSTALL_LINUX.es.md)
- [macOS](INSTALL_MACOS.es.md)
- [Windows](INSTALL_WINDOWS.es.md)
- [Pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md)
- [Firma de releases](RELEASE_SIGNING.es.md)

## Operación y mantenimiento

- La configuración parte de [`.env.example`](../.env.example); no confirmes `.env` al repositorio.
- Usa `trinaxai doctor` para diagnóstico y `trinaxai status` para estado de servicios.
- Usa `./backup.sh` antes de cambios de versión o modificaciones del índice.
- Cuando un aviso incluya una acción de recuperación, ejecútala primero; si no,
  consulta la [tabla de diagnóstico](TROUBLESHOOTING.es.md) antes de borrar datos.
- Consulta [soporte](SUPPORT.es.md) para pedir ayuda y [seguridad](SECURITY.es.md) para reportar vulnerabilidades.

## Mapa completo de referencias

### Referencias técnicas

- [Arquitectura](ARCHITECTURE.es.md) — componentes, flujos, almacenamiento, autorización y pruebas.
- [Referencia de API](API_REFERENCE.es.md) — contratos HTTP, autorización, SSE, subidas, pairing y errores.
- [Configuración](CONFIGURATION.es.md) — ajustes operativos, modelos, límites, red y recuperación.
- [Variables de entorno](ENVIRONMENT_VARIABLES.es.md) — inventario canónico de `TRINAXAI_*` y `VITE_TRINAXAI_*`.
- [Referencia de CLI](CLI_REFERENCE.es.md) — comandos, slash commands, pairing, TOML y códigos de salida.
- [Solución de problemas y recuperación](TROUBLESHOOTING.es.md) — síntoma, diagnóstico seguro, siguiente acción y paquete para soporte.
- [Guía del desarrollador](DEVELOPER_GUIDE.es.md) — entorno local, convenciones, depuración, PWA y release.
- [Benchmark de modelos](MODEL_BENCHMARK.es.md) — mediciones locales versionadas y sus limitaciones.

### Operación y comunidad

- [Instalación en Linux](INSTALL_LINUX.es.md), [macOS](INSTALL_MACOS.es.md) y [Windows](INSTALL_WINDOWS.es.md).
- [Guía de pruebas](../TESTING.es.md) — dry-runs de instaladores y validación multiplataforma.
- [Política de seguridad](SECURITY.es.md) — canal de reporte, amenazas y despliegue seguro.
- [Soporte](SUPPORT.es.md) — diagnóstico mínimo para abrir un issue útil.
- [Contribuir](CONTRIBUTING.es.md) y [Código de conducta](CODE_OF_CONDUCT.es.md).
- [Marca](TRADEMARK.es.md) — uso permitido del nombre y logotipo de TrinaxAI.
- [Registro de cambios](CHANGELOG.es.md) — historial de releases y trabajo sin publicar.

## Proyecto y contribución

- [Contribuir](CONTRIBUTING.es.md)
- [Código de conducta](CODE_OF_CONDUCT.es.md)
- [Changelog](CHANGELOG.es.md)

## Fuentes de verdad

Para evitar documentación desactualizada, estas son las fuentes autoritativas:

| Tema | Fuente |
|---|---|
| Dependencias y comandos Python | `pyproject.toml`, `requirements*.txt`, `Makefile` |
| Comandos y flags de CLI | `trinaxai_cli/app.py` |
| Endpoints HTTP | `app/routes/`, `app/main.py`, `/openapi.json` |
| Variables de entorno | `docs/ENVIRONMENT_VARIABLES.es.md`, `.env.example` |
| Scripts de frontend | `chat-pwa/package.json` |
| Manifest, caché y proxies PWA | `chat-pwa/vite.config.ts` |
| Navegación y enlaces de Docs integrada | `chat-pwa/src/components/Docs.tsx`; el texto de usuario vive en los `docs/*.md` enlazados |
| Acciones visibles de errores | `chat-pwa/src/lib/api_errors.ts`, `chat-pwa/src/components/chat/MessageList.tsx` |

## Convenciones de la documentación

- Los archivos sin sufijo están en inglés; los archivos `.es.md`, en español.
- Los comandos se ejecutan desde la raíz del repositorio salvo que se indique `cd chat-pwa`.
- Los puertos por defecto son `3334` (PWA), `3333` (API RAG) y `11434` (Ollama).
- Las instalaciones administradas prefieren HTTPS para la PWA y la API RAG; HTTP
  directo es un fallback de desarrollo en loopback. Un navegador LAN debe
  confiar en la CA pública que muestra `trinaxai network`.
- Las rutas locales de datos (`storage/`, `local_sources/`, `logs/`, `backups/`) no deben versionarse.
- Cuando cambie un comportamiento visible, actualiza la referencia canónica en inglés y su traducción `.es.md` revisada cuando aplique; mantén actualizados los enlaces de Docs integrada.
- No copies secretos, rutas privadas ni archivos generados de `storage/` a los ejemplos. Usa placeholders como `HOST-LAN-IP` y deja los valores en `.env.example`.
