# Soporte

[English](SUPPORT.md)

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
