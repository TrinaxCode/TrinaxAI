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
├── rag_api.py             # Punto de entrada compatible de la API
├── index.py               # Indexador de documentos (con conciencia AST, incremental)
├── app/
│   ├── main.py            # Fábrica canónica de FastAPI
│   ├── routes/            # Routers HTTP pequeños agrupados por dominio
│   ├── schemas/           # Contratos Pydantic compartidos
│   ├── services/          # Chat, fuentes, memoria, indexación, sistema, etc.
│   └── security/          # Autorización y rate limiting
├── trinaxai_cli/          # Interfaz de terminal (modular, con subcomandos)
├── trinaxai_cli.py        # CLI autónomo heredado (deprecado)
├── service_manager.py     # Supervisor de servicios multiplataforma
├── test_system.py         # Verificaciones de salud automatizadas
│
├── chat-pwa/              # Frontend PWA en React
│   ├── src/components/    # Componentes de UI en React
│   ├── src/lib/           # Capa de API, config, estado compartido, perfil de usuario
│   ├── src/hooks/         # useChatHistory y useStreamChat
│   ├── src/i18n/          # Traducciones español/inglés
│   └── vite.config.ts     # Config de build, plugin PWA, proxy de API
│
├── scripts/               # Herramientas de release (public_readiness.py)
├── docs/                  # Documentación (referencia de API, arquitectura, guía dev)
├── storage/               # Índices persistidos, manifiesto, colecciones
├── chat-pwa/certs/        # Certificados HTTPS locales (generados localmente)
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
- CSS: utilidades Tailwind y CSS local junto a componentes complejos

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

1. Añade la lógica al módulo correspondiente de `app/services/`.
2. Regístrala en el router correspondiente de `app/routes/*.py`:
   ```python
   @router.get("/v1/my-feature")
   async def my_feature(request: Request):
       # Clasifica los datos: las lecturas privadas usan authorize_system
       # (preferible como dependencia del router). Solo health/resources
       # declarados públicos omiten autorización.
       return {"ok": True}
   ```

   Para endpoints de sistema que modifican el estado:
   ```python
   @router.post("/system/my-action")
   async def my_action(request: Request):
       authorize_system(request)
       # ...
       return {"ok": True}
   ```

3. Añade o actualiza el contrato Pydantic en `app/schemas/`.
4. Añade una prueba de contrato y actualiza `docs/API_REFERENCE.es.md`.
5. Si la PWA lo necesita, añade la función fetch en `chat-pwa/src/lib/api.ts`.

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
curl -k -X POST http://localhost:3333/system/reload
```

---

## Desarrollo de la PWA

### Servidor de Desarrollo
El servidor de desarrollo Vite se ejecuta en `https://localhost:3334` con reemplazo de módulos en caliente. Proxy de `/api/rag` → `localhost:3333` y `/api/ollama` → `localhost:11434`.

```bash
cd chat-pwa
npm run dev
```

### Caché del Service Worker
La PWA usa `vite-plugin-pwa` con `registerType: 'prompt'`: una actualización
espera la decisión de la persona y no interrumpe un stream o borrador. Durante
desarrollo, el service worker **no** se registra para evitar cachés. Para probar:

```bash
npm run build
npm run preview   # Sirve la build de producción con service worker
```

### Depuración del Frontend
- **React DevTools**: Instala la extensión del navegador para inspeccionar componentes.
- **Pestaña Network**: Todas las llamadas API pasan por el proxy de Vite — revisa la pestaña Network para `/api/rag/*` y `/api/ollama/*`.
- **IndexedDB**: Los archivos adjuntos se almacenan en `trinaxai-chat-files` — inspecciona vía DevTools > Application > IndexedDB.
- **localStorage**: El historial de chat, configuración y estado compartido están en localStorage — revisa Application > Local Storage.
- **Service Worker**: Usa Application > Service Workers para desregistrar o actualizar.
- **Streaming SSE**: Los eventos aparecen en la pestaña Network como respuestas `text/event-stream`.

### División de Código
Las dependencias pesadas se dividen en chunks separados (configurado en `vite.config.ts`):
- `vendor-react` — React + ReactDOM
- `vendor-framer` — Framer Motion
- `vendor-markdown` — react-markdown + rehype-sanitize
- `vendor-icons` — react-icons

Las páginas con carga diferida (`React.lazy`) se cargan bajo demanda: `Settings`, `OnboardingWizard`, `Docs`, `KnowledgeBrowser`.

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
make check
git diff --check  # verifica que no haya espacios en blanco al final
```

Usa un tag semántico como `v1.0.0` y mantenlo igual a las versiones de
`pyproject.toml`, `chat-pwa/package.json`, `chat-pwa/package-lock.json` y
`trinaxai_cli/app.py`. El workflow del tag repite los gates y publica el archivo
fuente, instaladores shell y PowerShell, checksums y procedencia.
