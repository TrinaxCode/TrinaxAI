<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 💬 Soporte
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="SUPPORT.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

TrinaxAI es un proyecto de código abierto con enfoque local. El soporte de la comunidad se gestiona mediante GitHub issues y discusiones.

Empieza por la [guía de solución de problemas y recuperación](TROUBLESHOOTING.es.md). Si la PWA ofrece **Abrir indexación**, **Reintentar**, **Encender IA** o **Abrir configuración**, usa esa acción antes de recopilar logs.

## Antes de abrir un issue

Ejecuta estos comandos desde la raíz del repositorio:

```bash
python3 test_system.py --verbose
python3 scripts/public_readiness.py
cd chat-pwa && npm run build
```

Si los servicios no están activos, usa `trinaxai doctor --strict --json` en
lugar de la prueba del sistema. Al reportar un fallo, incluye el comando que
falló, una descripción breve del comportamiento esperado y la salida relevante
sin secretos. Para fallos de API, incluye el request ID si se devolvió alguno.
Consulta primero el [índice de documentación](README.es.md), la [guía de solución de problemas](TROUBLESHOOTING.es.md) y la
[política de seguridad](SECURITY.es.md).

## Información útil

Por favor incluye:

- Sistema operativo y versión: distribución de Linux, versión de macOS o versión de Windows.
- Versión de Python.
- Versión de Node.js.
- Versión de Ollama.
- RAM y GPU, si es relevante.
- Perfil de TrinaxAI: `8gb`, `16gb`, `32gb` o `64gb`.
- Si usas solo localhost o también acceso por LAN o teléfono.

## Seguridad

No publiques tokens, documentos privados, capturas de pantalla con datos
sensibles ni archivos personales. Para reportes de seguridad, usa
[SECURITY.es.md](SECURITY.es.md) en lugar de un issue público.
