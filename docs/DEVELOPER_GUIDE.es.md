# Guía del Desarrollador de TrinaxAI

## Configuración

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh           # o install.ps1 en Windows
source .venv/bin/activate
pip install -r requirements.txt
cd chat-pwa && npm install && cd ..
```

Para el reranker (opcional pero recomendado para mayor precisión):
```bash
pip install -r requirements-rerank.txt
```

Copia `.env.example` a `.env` y edítalo según sea necesario:
```bash
cp .env.example .env
```

---

## Estructura del Proyecto

```
.
├── config.py              # Configuración central (modelos, perfiles, chunking)
├── rag_api.py             # Backend FastAPI (RAG, memoria, colecciones, watcher)
├── index.py               # Indexador de documentos (con conciencia AST, incremental)
├── trinaxai_cli/          # Interfaz de terminal (modular, con subcomandos)
├── trinaxai_cli.py        # CLI autónomo heredado (deprecado)
├── service_manager.py     # Supervisor de servicios multiplataforma
├── test_system.py         # Verificaciones de salud automatizadas
│
├── chat-pwa/              # Frontend PWA en React
│   ├── src/components/    # 18 componentes React
│   ├── src/lib/           # Capa de API, config, estado compartido, perfil de usuario
│   ├── src/hooks/         # useChatHistory, useStreamChat, useZenMode
│   ├── src/i18n/          # Traducciones español/inglés (~250 claves)
│   └── vite.config.ts     # Config de build, plugin PWA, proxy de API
│
├── scripts/               # Herramientas de release (public_readiness.py)
├── docs/                  # Documentación (referencia de API, arquitectura, guía dev)
├── storage/               # Índices persistidos, manifiesto, colecciones
├── certs/                 # Certificados HTTPS autofirmados para desarrollo local
└── .github/               # CI, plantilla de PR, plantillas de issues
```

---

## Convenciones de Código

### Python

- Usa `pathlib.Path` para código nuevo (el código existente con `os.path` puede permanecer)
- Docstrings en estilo Google o NumPy, tanto en español como en inglés (convención del proyecto: bilingüe)
- Orden de importaciones: stdlib → terceros → local
- Se fomentan las anotaciones de tipo, pero no se aplican estrictamente
- Evita `except Exception: pass` sin más — registra la excepción como mínimo

### TypeScript (chat-pwa)

- TypeScript estricto (`strict: true` en tsconfig.json)
- Usa `const` para variables no reasignadas
- Los componentes son funcionales con hooks, sin componentes de clase (excepto `ErrorBoundary`)
- i18n: añade nuevas cadenas en `translations.ts` tanto en `es` como en `en`
- CSS: clases de utilidad Tailwind; CSS personalizado solo en `index.css`

### Scripts de Shell

- Usa el shebang `#!/usr/bin/env bash`
- Incluye `set -euo pipefail`
- Añade función `usage()` y flag `--help`
- Documenta las variables de entorno utilizadas

---

## Añadir un Nuevo Modelo

1. Añade la constante del modelo en `config.py`:
   ```python
   MODEL_MY_NEW = os.getenv("TRINAXAI_MODEL_MY_NEW", "my-model:latest")
   ```
2. Agrégalo a la lista `MODEL_FLEET`
3. Actualiza `route_model()` si el modelo necesita heurísticas de enrutamiento especiales
4. Descarga el modelo: `ollama pull my-model:latest`
5. Añádelo a la tabla de enrutamiento automático en la sección de modelos de `Docs.tsx`

---

## Añadir un Nuevo Endpoint de API

1. Añade la función del endpoint en `rag_api.py`:
   ```python
   @app.get("/v1/my-feature")
   async def my_feature(request: Request):
       # No se necesita autenticación para endpoints de solo lectura
       return {"ok": True}
   ```

   Para endpoints de sistema que modifican el estado:
   ```python
   @app.post("/system/my-action")
   async def my_action(request: Request):
       _authorize_system(request)
       # ...
       return {"ok": True}
   ```

2. Añádelo a la referencia de API en `docs/API_REFERENCE.md`
3. Añádelo a la documentación integrada en la sección de API de `Docs.tsx`
4. Si la PWA lo necesita, añade la función fetch en `chat-pwa/src/lib/api.ts`

---

## Añadir Cadenas i18n

1. Abre `chat-pwa/src/i18n/translations.ts`
2. Añade las claves a los objetos `es` y `en`
3. Usa `const { t, lang } = useI18n()` en los componentes
4. Llama a `t('myKey')` o `isEs ? 'Texto' : 'Text'` para texto en línea

---

## Pruebas

### Verificación de Salud
```bash
python test_system.py --verbose
```
Verifica: Ollama en ejecución, embeddings funcionando, consulta RAG operativa.

### Auditoría Pre-Release
```bash
python scripts/public_readiness.py
```
Comprueba: archivos requeridos, rutas hardcodeadas, cobertura de i18n, compilación de Python.

### CI
`.github/workflows/ci.yml` se ejecuta en push/PR:
- Comprobación de sintaxis Python (`python -m compileall`)
- Comprobación de tipos TypeScript (`npx tsc --noEmit`)
- Build del frontend (`npm run build`)

---

## Consejos de Depuración

### La API RAG no arranca
```bash
# Verificar el puerto
lsof -i :3333

# Ejecutar directamente con salida detallada
python -c "import uvicorn; uvicorn.run('rag_api:app', host='0.0.0.0', port=3333, reload=True)"
```

### Ollama no responde
```bash
# Verificar si está en ejecución
curl http://localhost:11434/api/tags

# Verificar logs
journalctl -u ollama -f  # Linux
```

### La PWA no carga
```bash
cd chat-pwa
npx vite --host 0.0.0.0 --port 3334
# Revisa la consola para errores, problemas de CORS o de certificados
```

### Problemas de indexación
```bash
# Re-indexación completa (opción nuclear)
rm -rf storage/docstore.json storage/index_store.json storage/manifest.json
python index.py
curl -k -X POST https://localhost:3333/system/reload
```

---

## Tareas Comunes

### Resetear todo
```bash
./shutdown_ai.sh
rm -rf storage/ chat-pwa/dist/
python index.py
./startup_ai.sh
```

### Actualizar dependencias
```bash
./update.sh  # backup, git pull, pip install, npm ci, rebuild PWA
```

### Añadir un nuevo idioma
1. Crea la entrada del nuevo locale en `chat-pwa/src/i18n/translations.ts`
2. Actualiza `I18nContext.tsx` para incluir el nuevo idioma
3. Añade la opción de idioma en `OnboardingWizard.tsx`

### Conectar VSCode (Continue.dev)
```bash
cp continue-config.yaml ~/.continue/config.yaml
# Reinicia VSCode — los modelos aparecen en el selector de Continue
```

---

## Lista de Verificación para el Release

Antes de etiquetar un release, ejecuta:
```bash
python scripts/public_readiness.py
python test_system.py --verbose
cd chat-pwa && npx tsc --noEmit && npm run build && cd ..
git diff --check  # verifica que no haya espacios en blanco al final
```
