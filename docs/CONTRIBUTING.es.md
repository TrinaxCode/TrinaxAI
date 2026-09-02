<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🤝 Contribuir
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="CONTRIBUTING.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

¡Ante todo, gracias por considerar contribuir a TrinaxAI!

TrinaxAI es un proyecto de código abierto y nos encanta recibir contribuciones de la comunidad. Hay muchas formas de colaborar: escribir tutoriales o artículos de blog, mejorar la documentación, enviar reportes de errores y solicitudes de características, o escribir código que pueda incorporarse al propio TrinaxAI.

## Código de Conducta

Este proyecto sigue el [CODE_OF_CONDUCT.es.md](CODE_OF_CONDUCT.es.md). Sé respetuoso, directo y constructivo.

## ¿Cómo puedo contribuir?

### Reportar errores

Antes de crear un reporte de error:
- Consulta la [documentación](https://github.com/TrinaxCode/TrinaxAI/tree/main/docs)
- Sigue la [guía de solución de problemas y recuperación](TROUBLESHOOTING.es.md) y anota qué acción de recuperación ofreció o intentaste
- Busca en los [issues existentes](https://github.com/TrinaxCode/TrinaxAI/issues) para ver si ya está reportado

Al reportar un error, incluye:
- Tu sistema operativo y especificaciones de hardware (CPU, RAM)
- La versión de TrinaxAI o el hash del commit
- Pasos para reproducirlo
- El comportamiento esperado frente al comportamiento real
- Cualquier mensaje de error o log relevante
- El `request_id` de la API y el ID del job de indexación cuando existan; redacta tokens, rutas privadas, prompts y contenido de documentos

### Sugerir características

Las sugerencias de características se gestionan como GitHub Issues. Por favor describe:
- El problema que estás intentando resolver
- Cómo te gustaría que TrinaxAI lo solucione
- Cualquier alternativa que hayas considerado

### Pull Requests

1. Haz un fork del repositorio y crea tu rama desde `main`
2. Firma cada commit para el DCO: `git commit -s`
3. Si añadiste código, agrega pruebas si aplica
4. Ejecuta las verificaciones pre-release (ver abajo)
5. Abre el pull request

### Traducciones

TrinaxAI admite múltiples idiomas. Para añadir o mejorar traducciones:
- Edita `chat-pwa/src/i18n/translations.ts`
- Añade tu idioma siguiendo el patrón existente (ES, EN)
- Verifica que todos los elementos de la interfaz se muestren correctamente

### Documentación

¡Las mejoras a la documentación siempre son bienvenidas! Los docs se encuentran en:
- `docs/README.es.md` — mapa documental y fuentes de verdad para mantenimiento
- `docs/` — referencias de API, CLI, configuración, arquitectura, instalación y desarrollo
- `chat-pwa/README.es.md` — ejecución y desarrollo de la PWA
- `chat-pwa/src/components/Docs.tsx` (documentación integrada en la app)
- `README.md` (descripción general del proyecto)
- `README.es.md` (versión en español)

Mantén alineadas las versiones en inglés y `.es.md`. Verifica comandos en `trinaxai_cli/app.py`, rutas HTTP en `/openapi.json`, scripts PWA en `chat-pwa/package.json` y acciones visibles de recuperación en `chat-pwa/src/lib/api_errors.ts` y `chat-pwa/src/components/chat/MessageList.tsx`.

---

## Configuración del entorno de desarrollo

Consulta la [guía de desarrollo](DEVELOPER_GUIDE.es.md) para las instrucciones completas de configuración.

Inicio rápido:
```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh                # o install.ps1 en Windows
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
(cd chat-pwa && npm install && npm run dev)

# CLI (instalación editable)
pip install -e .
trinaxai doctor
```

## Verificaciones pre-release

Antes de abrir un PR o hacer push a main, ejecuta:

```bash
# Python
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py config.py index.py trinaxai_cli/app.py
ruff check .

# Frontend
cd chat-pwa
npx tsc --noEmit
npm run build
npm audit --audit-level=high

# Prueba del sistema (requiere servicios corriendo)
trinaxai doctor
python3 test_system.py --verbose
```

Ejecuta `make readiness` antes de abrir un pull request orientado a publicación.

## Estilo de commits

- Usa tiempo presente ("Agregar feature" no "Agregado feature")
- Commits enfocados — un cambio lógico por commit
- Referencia issues con `#123` cuando aplique
- Firma con `git commit -s` para cumplir con DCO

## Licencia

Al contribuir, aceptas que tu aportación se licencia bajo AGPL-3.0-or-later.

## ¿Preguntas?

Abre una [GitHub Discussion](https://github.com/TrinaxCode/TrinaxAI/discussions) o comunícate a través del issue tracker.

---

**Gracias por contribuir.**
