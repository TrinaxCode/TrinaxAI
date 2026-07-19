# Contribuir a TrinaxAI

[English](../../CONTRIBUTING.md)

¡Ante todo, gracias por considerar contribuir a TrinaxAI!

TrinaxAI es un proyecto de código abierto y nos encanta recibir contribuciones de la comunidad. Hay muchas formas de colaborar: escribir tutoriales o artículos de blog, mejorar la documentación, enviar reportes de errores y solicitudes de características, o escribir código que pueda incorporarse al propio TrinaxAI.

## Código de Conducta

Este proyecto sigue el [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Sé respetuoso, directo y constructivo.

## ¿Cómo puedo contribuir?

### 🐛 Reportar errores

Antes de crear un reporte de error:
- Consulta la [documentación](https://github.com/TrinaxCode/TrinaxAI/tree/main/docs)
- Busca en los [issues existentes](https://github.com/TrinaxCode/TrinaxAI/issues) para ver si ya está reportado

Al reportar un error, incluye:
- Tu sistema operativo y especificaciones de hardware (CPU, RAM)
- La versión de TrinaxAI o el hash del commit
- Pasos para reproducirlo
- El comportamiento esperado frente al comportamiento real
- Cualquier mensaje de error o log relevante

### 💡 Sugerir características

Las sugerencias de características se gestionan como GitHub Issues. Por favor describe:
- El problema que estás intentando resolver
- Cómo te gustaría que TrinaxAI lo solucione
- Cualquier alternativa que hayas considerado

### 📝 Pull Requests

1. Haz un fork del repositorio y crea tu rama desde `main`
2. Firma cada commit para el DCO: `git commit -s`
3. Si añadiste código, agrega pruebas si aplica
4. Ejecuta las verificaciones pre-release (ver abajo)
5. Abre el pull request

### 🌍 Traducciones

TrinaxAI admite múltiples idiomas. Para añadir o mejorar traducciones:
- Edita `chat-pwa/src/i18n/translations.ts`
- Añade tu idioma siguiendo el patrón existente (ES, EN)
- Verifica que todos los elementos de la interfaz se muestren correctamente

### 📚 Documentación

¡Las mejoras a la documentación siempre son bienvenidas! Los docs se encuentran en:
- `docs/README.es.md` — mapa documental y fuentes de verdad para mantenimiento
- `docs/` — referencias de API, CLI, configuración, arquitectura, instalación y desarrollo
- `chat-pwa/README.es.md` — ejecución y desarrollo de la PWA
- `chat-pwa/src/components/Docs.tsx` (documentación integrada en la app)
- `README.md` (descripción general del proyecto)
- `README.es.md` (versión en español)

Mantén alineadas las versiones en inglés y `.es.md`. Verifica comandos en `trinaxai_cli/app.py`, rutas HTTP en `/openapi.json` y scripts PWA en `chat-pwa/package.json`.

---

## Configuración del entorno de desarrollo

Consulta la [guía de desarrollo](../DEVELOPER_GUIDE.es.md) para las instrucciones completas de configuración.

Inicio rápido:
```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh                # o install.ps1 en Windows
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd chat-pwa
npm install
npm run dev

# CLI (instalación editable)
pip install -e .
trinaxai doctor
```

## Verificaciones pre-release

Antes de abrir un PR o hacer push a main, ejecuta:

```bash
# Python
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py config.py index.py trinaxai_cli.py
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

⭐ **¡Gracias por contribuir!**
