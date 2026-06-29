# Contribuir a TrinaxAI

¡Ante todo, gracias por considerar contribuir a TrinaxAI!

TrinaxAI es un proyecto de código abierto y nos encanta recibir contribuciones de la comunidad. Hay muchas formas de colaborar: escribir tutoriales o artículos de blog, mejorar la documentación, enviar reportes de errores y solicitudes de características, o escribir código que pueda incorporarse al propio TrinaxAI.

## Código de Conducta

Este proyecto sigue el [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Sé respetuoso, directo y constructivo.

## ¿Cómo puedo contribuir?

### 🐛 Reportar errores

Antes de crear un reporte de error:
- Consulta el [FAQ](https://github.com/TrinaxCode/trinaxai#readme) y la [documentación](https://github.com/TrinaxCode/trinaxai/tree/main/docs)
- Busca en los [issues existentes](https://github.com/TrinaxCode/trinaxai/issues) para ver si ya está reportado

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
4. Ejecuta `python3 scripts/public_readiness.py`
5. Ejecuta `python3 -m py_compile *.py scripts/*.py`
6. Ejecuta `cd chat-pwa && npm run build`
7. Abre el pull request

### 🌍 Traducciones

TrinaxAI admite múltiples idiomas. Para añadir o mejorar traducciones:
- Edita `chat-pwa/src/i18n/translations.ts`
- Añade tu idioma siguiendo el patrón existente (ES, EN)
- Verifica que todos los elementos de la interfaz se muestren correctamente

### 📚 Documentación

¡Las mejoras a la documentación siempre son bienvenidas! Los docs se encuentran en:
- `docs/` — Referencia de API, arquitectura, guía para desarrolladores
- `chat-pwa/src/components/Docs.tsx` (documentación integrada en la app)
- `README.md` (descripción general del proyecto)
- `README.es.md` (versión en español)

---

## Configuración del entorno de desarrollo

Consulta [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) para las instrucciones completas de configuración.

Inicio rápido:
```bash
git clone https://github.com/TrinaxCode/trinaxai.git
cd trinaxai
./install.sh                # o install.ps1 en Windows
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd chat-pwa
npm install
npm run dev
```

## Verificaciones previas al lanzamiento

Antes de un lanzamiento:

```bash
python3 scripts/public_readiness.py
python3 -m py_compile *.py scripts/*.py
cd chat-pwa && npm run build
python3 test_system.py --verbose
```

Consulta `docs/PUBLIC_RELEASE.md` para el checklist completo.

## Licencia

Al contribuir, aceptas que tu aportación se licencia bajo AGPL-3.0-or-later.

## ¿Preguntas?

Abre una [GitHub Discussion](https://github.com/TrinaxCode/trinaxai/discussions) o comunícate a través del issue tracker.

---

⭐ **¡Gracias por contribuir!**
