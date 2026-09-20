<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 📚 Documentación
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.6"><img src="https://img.shields.io/badge/version-1.2.6-006bbd" alt="Release estable: 1.2.6"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="Estado de CI"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="Licencia AGPL-3.0-or-later"></a>
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="../README.es.md">Inicio</a> · <a href="https://www.trinaxai.app/">Sitio web</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Este centro te lleva desde una instalación npm funcional hasta el uso diario,
la configuración, el emparejamiento, la recuperación y el desarrollo. Describe
TrinaxAI v1.2.6, el release estable actual.

## Instalar una vez

La ruta pública de instalación es el lanzador npm. Funciona en Linux, macOS y
Windows:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

El lanzador descarga el instalador del release correspondiente y verifica su
checksum SHA-256 antes de configurarlo. No necesitas clonar el repositorio ni
ejecutar los scripts de plataforma en una instalación normal.

Después de la configuración, verifica los servicios locales:

~~~bash
trinaxai doctor
trinaxai status
~~~

Abre [https://localhost:3334](https://localhost:3334) para usar la PWA. Consulta
el [README principal](../README.es.md) para la primera pregunta y el mapa de
comandos diarios.

## Elige una guía

| Tu tarea | Guía |
| --- | --- |
| Entender el primer inicio en tu plataforma | [Linux](INSTALL_LINUX.es.md), [macOS](INSTALL_MACOS.es.md) o [Windows](INSTALL_WINDOWS.es.md) |
| Configurar modelos, RAG, límites o red | [Configuración](CONFIGURATION.es.md) |
| Encontrar una variable de entorno | [Variables de entorno](ENVIRONMENT_VARIABLES.es.md) |
| Usar la interfaz de terminal | [Referencia CLI](CLI_REFERENCE.es.md) |
| Emparejar otro dispositivo | [Pairing LAN](NETWORK_PAIRING.es.md) |
| Resolver un fallo de salud | [Solución de problemas](TROUBLESHOOTING.es.md) |
| Entender el almacenamiento y los flujos | [Arquitectura](ARCHITECTURE.es.md) |
| Integrar el servicio HTTP | [Referencia de API](API_REFERENCE.es.md) |
| Desarrollar o contribuir | [Guía del desarrollador](DEVELOPER_GUIDE.es.md) |

## Guías por plataforma

Las páginas de plataforma explican requisitos, lo que hace el comando de
configuración npm, las comprobaciones iniciales, el ciclo de vida de servicios,
las copias de seguridad, la red local y la recuperación específica. No ofrecen
un segundo comando de instalación.

- [Linux](INSTALL_LINUX.es.md): systemd, distribuciones, permisos y Docker
- [macOS](INSTALL_MACOS.es.md): Apple Silicon, launchd, certificados y red local
- [Windows](INSTALL_WINDOWS.es.md): PowerShell, supervisor de procesos, firewall y WSL

## Operar de forma segura

Usa estos comandos desde cualquier carpeta:

~~~bash
trinaxai status
trinaxai doctor --strict
trinaxai update
trinaxai uninstall
~~~

Haz una copia antes de actualizar o modificar el índice. Mantén privados los
puertos 3333, 3334 y 11434 salvo que entiendas el flujo de pairing LAN y
certificados. La [guía de seguridad](SECURITY.es.md) explica los límites de
confianza.

## Referencias técnicas

- [Arquitectura](ARCHITECTURE.es.md): componentes, flujos, almacenamiento y límites de autorización
- [Configuración](CONFIGURATION.es.md): modelos, RAG, red, límites y recuperación
- [Variables de entorno](ENVIRONMENT_VARIABLES.es.md): inventario canónico de TRINAXAI
- [Referencia CLI](CLI_REFERENCE.es.md): comandos, flags, pairing y códigos de salida
- [Referencia de API](API_REFERENCE.es.md): contratos HTTP, SSE, subidas, pairing y errores
- [Benchmark de modelos](MODEL_BENCHMARK.es.md): mediciones locales versionadas y limitaciones
- [Documentación de la PWA](../chat-pwa/README.es.md): flujos frontend, caché y pruebas

## Recuperación y soporte

Empieza con trinaxai doctor. Después consulta las
[tablas de diagnóstico](TROUBLESHOOTING.es.md). Incluye la salida de diagnóstico
redactada y el estado relevante de los servicios al abrir un issue.

Lee [soporte](SUPPORT.es.md) para preparar el paquete de información y
[seguridad](SECURITY.es.md) para reportar vulnerabilidades de forma privada.

## Desarrollo y releases

La ruta de desarrollo está separada de la instalación de usuarios. Empieza por
la [guía del desarrollador](DEVELOPER_GUIDE.es.md), sigue con la
[guía para contribuir](CONTRIBUTING.es.md) y consulta la
[guía de pruebas](../TESTING.es.md).

Los operadores de releases pueden consultar [firma de releases](RELEASE_SIGNING.es.md).
El lanzador npm es la entrada pública compatible; los instaladores de plataforma
firmados son detalles internos del release.

## Convenciones de idioma y fuentes

- Los archivos sin sufijo están en inglés; los archivos .es.md, en español
- Los cambios visibles para usuarios actualizan la referencia inglesa y su traducción española
- Los comandos se ejecutan desde la raíz salvo que la guía indique entrar en chat-pwa
- Los puertos predeterminados son 3334 para la PWA, 3333 para la API RAG y 11434 para Ollama
- No copies secretos, rutas privadas ni archivos generados de almacenamiento a los ejemplos

Las fuentes autoritativas viven en pyproject.toml, chat-pwa/package.json,
trinaxai_cli/app.py, app/routes/, .env.example y las referencias enlazadas.
La vista Docs integrada lee los mismos archivos Markdown.
