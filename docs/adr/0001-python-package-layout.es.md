# ADR 0001 — Mover los módulos Python planos de la raíz a un paquete `trinaxai`

[English](0001-python-package-layout.md) · **Español**

- **Estado:** Aceptado, implementado en el mismo conjunto de cambios (ver [Despliegue](#despliegue)).
- **Fecha:** 2026-10-20
- **Alcance:** `config.py`, `index.py`, `rag_api.py`, `service_manager.py`,
  `trinaxai_core.py`, `trinaxai_errors.py`, `trinaxai_index_documents.py`,
  `trinaxai_index_state.py`, `trinaxai_index_storage.py`, `recovery_server.py`.

## Contexto

La raíz del repositorio mezclaba diez módulos de implementación con instaladores,
archivos de configuración y los paquetes reales (`app/`, `trinaxai_cli/`,
`trinaxai_agent/`). `docs/ARCHITECTURE.es.md` ya describía `index.py` y
`rag_api.py` como fachadas de compatibilidad, así que la separación por
responsabilidades existe; solo la disposición de archivos sigue siendo plana.

La disposición plana tiene costes concretos:

- `config`, `index` y `trinaxai_core` son nombres de nivel superior. El wheel de la
  CLI instala en `site-packages` un módulo llamado literalmente `config`.
- Nada indica qué archivo de la raíz es una biblioteca y cuál es un lanzador que se
  ejecuta por ruta.
- `pyproject.toml`, `Dockerfile`, CI, `Makefile`, las opciones de cobertura y mypy
  enumeran a mano los archivos de la raíz.

El movimiento está condicionado por lo que hacen en ejecución las **instalaciones
ya desplegadas**. Estas rutas están incrustadas en artefactos que existen en las
máquinas de los usuarios y que una actualización no reescribe:

| Consumidor en ejecución | De qué depende |
|---|---|
| Unidad systemd / plist de launchd / tarea de Windows escrita por `service_manager` | `python <base>/service_manager.py watch --base-dir …` |
| Detección de procesos de `service_manager` | subcadenas de la línea de comandos como `service_manager.py watch`, `uvicorn app.main:app`, `rag_api.py` |
| `app/services/system_service.py`, `watcher_service.py`, `trinaxai_cli/commands/index.py` | lanzan `<base>/index.py` como subproceso |
| `service_manager` | lanza `<base>/recovery_server.py` |
| `trinaxai_cli/commands/_system.py`, `trinaxai_cli/runtime.py`, `npm-package/bin/trinaxai.js`, `install.sh` | descubren una instalación porque `service_manager.py` / `rag_api.py` existen en disco |
| `install.sh`, `install.ps1`, `update.sh`, `update.ps1`, `uninstall.sh`, `uninstall.ps1`, `backup.sh`, `startup_ai.sh`, `shutdown_ai.sh`, `chat-pwa/server.mjs`, `chat-pwa/vite.config.ts` | ejecutan `<base>/service_manager.py <acción> --base-dir <base>` |
| `scripts/with_index_lock.py` (lo ejecuta `backup.sh`) | `import trinaxai_core` mediante la instalación editable del venv |
| Script de consola `.venv/bin/trinaxai` | `config`, `trinaxai_core`, `trinaxai_errors` resueltos por el buscador de la instalación editable |
| `Dockerfile` | `COPY` de cada archivo de la raíz; `BASE_DIR` es el directorio que contiene `config.py` |

## Decisión

1. Crear el paquete `trinaxai/` y mover las implementaciones a él:

   ```
   trinaxai/__init__.py
   trinaxai/paths.py                  PROJECT_ROOT (único lugar que sabe dónde está la raíz de la instalación)
   trinaxai/config.py                 ← config.py
   trinaxai/core.py                   ← trinaxai_core.py
   trinaxai/errors.py                 ← trinaxai_errors.py
   trinaxai/indexing/documents.py     ← trinaxai_index_documents.py
   trinaxai/indexing/state.py         ← trinaxai_index_state.py
   trinaxai/indexing/storage.py       ← trinaxai_index_storage.py
   trinaxai/indexing/indexer.py       ← index.py
   trinaxai/supervisor/service_manager.py  ← service_manager.py
   trinaxai/supervisor/recovery_server.py  ← recovery_server.py
   ```

   El wheel sigue siendo solo de CLI: únicamente se empaquetan los módulos de nivel
   superior de `trinaxai` (`__init__`, `paths`, `config`, `core`, `errors`); los
   subpaquetes `indexing` y `supervisor` existen solo en instalaciones desde el
   código fuente. La prueba de empaquetado que demuestra que los módulos del
   backend no se filtran al wheel se amplía en consecuencia.

2. **Cada ruta antigua permanece, como shim, en el mismo lugar.** Un shim se
   sustituye a sí mismo en `sys.modules` por el módulo real:

   ```python
   sys.modules[__name__] = trinaxai.config  # se conserva la identidad del módulo
   ```

   Por eso `import config`, `from config import X`, `monkeypatch.setattr(config, …)`,
   `mock.patch("config.X")` e `importlib.reload(config)` actúan sobre el único
   objeto de módulo real. Esto importa porque la suite de pruebas y las
   integraciones externas parchean intensamente estos módulos; un shim que
   reexporte (`from … import *`) haría que los parches resultaran ineficaces sin
   avisar.

3. **Los archivos lanzadores se quedan en la raíz por diseño**: `index.py`,
   `service_manager.py`, `recovery_server.py` y `rag_api.py` se ejecutan *por
   ruta* (tabla anterior), así que su ubicación es un contrato de ejecución, no
   desorden. Pasan a ser lanzadores de unas 15 líneas: cuando se ejecutan como
   `__main__` llaman al `main()` real; cuando se importan, crean un alias del
   módulo real como cualquier otro shim. `rag_api.py` *no* se mueve: ya es solo un
   módulo de compatibilidad sobre `app.main`/`app.api_runtime` (su truco de clase
   de módulo es la superficie de compatibilidad) y tanto `uvicorn rag_api:app`
   como la detección de la instalación dependen de él.

4. **No cambia ningún instalador, actualizador, desinstalador, comando de entrada
   del Dockerfile, generación de systemd / launchd / Programador de tareas ni el
   código de lanzamiento de `server.mjs`/`vite.config.ts`.** Siguen llamando a las
   mismas rutas de la raíz. Los únicos artefactos que no son Python y se tocan son
   los que *enumeran archivos que copiar o comprobar*: `Dockerfile` (añade
   `COPY trinaxai`), `pyproject.toml`, CI, `Makefile`, `CODEOWNERS` y
   `scripts/public_readiness.py`.

5. `BASE_DIR` conserva su significado (la raíz de la instalación). Ahora se calcula
   una sola vez en `trinaxai/paths.py` como el directorio padre del directorio del
   paquete `trinaxai`, lo que equivale al antiguo «directorio que contiene
   `config.py`» en instalaciones desde el código fuente, Docker (`/app`) y el
   wheel (`site-packages`).

6. Los llamadores dentro del repositorio (`app/`, `trinaxai_cli/`,
   `trinaxai_agent/`, `scripts/`) migran a las nuevas rutas de importación. Las
   pruebas siguen importando los nombres antiguos a propósito: ejercitan los shims
   y demuestran la identidad, y una prueba específica
   (`tests/test_package_layout.py`) fija el contrato.

## Análisis de actualización y reversión

`scripts/source_update.py` sustituye todo el árbol de código fuente (todo salvo
`.env`, `.venv`, `storage`, `logs`, `backups`, `local_sources`, `chat-pwa/dist`,
`chat-pwa/node_modules`, `chat-pwa/certs`) a partir del archivo firmado y lo
restaura desde una copia si algo falla. Después, `update.sh`/`update.ps1` ejecutan
`pip install -e .`. Consecuencias:

- **Antiguo → nuevo:** todas las rutas antiguas de la raíz siguen existiendo tras
  la sustitución, de modo que cualquier cosa iniciada por ruta sigue funcionando
  (lanzadores). Las unidades y tareas escritas por versiones anteriores no
  necesitan regenerarse.
- **Mapeo obsoleto de la instalación editable.** Entre la sustitución del árbol y
  la ejecución de `pip install -e .` (y para quienes hacen `git pull` sin volver a
  ejecutar pip), el buscador editable del venv asigna `config`/`trinaxai_core`/
  `trinaxai_errors` a los *archivos shim de la raíz*, pero no sabe nada de
  `trinaxai`. Dos salvaguardas lo hacen seguro: cada shim añade su propio
  directorio (la raíz de la instalación) a `sys.path` antes de importar
  `trinaxai`, y `trinaxai_cli/__init__.py` hace lo mismo cuando no encuentra
  `trinaxai`. `scripts/with_index_lock.py` inserta la raíz de forma explícita en
  lugar de depender de la instalación editable.
- **Nuevo → antiguo (reversión):** la copia restaura el árbol antiguo. Un mapeo
  editable residual que mencione `trinaxai` apunta a un directorio que ya no existe
  y el buscador lo ignora.
- **Procesos en ejecución durante una actualización:** los servicios se detienen
  con el `service_manager.py` *antiguo* antes de sustituir el árbol y se inician
  con el nuevo lanzador después. Un supervisor antiguo de larga duración que
  importe perezosamente un nombre de módulo antiguo sigue resolviéndolo mediante
  el shim.

## Consecuencias

- Bueno: un espacio de nombres de importación real; `config`/`index` dejan de ser
  nombres de nivel superior para el código del repositorio; un único lugar
  (`trinaxai/paths.py`) conoce la disposición de la raíz; cobertura, mypy y bandit
  apuntan a un paquete en vez de a listas de archivos mantenidas a mano.
- Coste: el código relativo a `__file__` y todo lo que leyera los archivos antiguos
  como texto debe seguir el movimiento (comprobación de la matriz de
  `scripts/public_readiness.py`, aserción de `tests/test_scripts.py` sobre
  `service_manager.py`, opciones de cobertura).
- Coste: los nombres de logger y `__module__` cambian de `config` a
  `trinaxai.config` (el logger de configuración ya se llamaba `trinaxai.config`).
- Los shims son permanentes por ahora. Pueden eliminarse en una versión mayor
  cuando termine la ventana de soporte de las instalaciones anteriores a esta
  disposición; la eliminación exige conservar los lanzadores.

## Verificación

En cada paso: `ruff check`, `ruff format --check`, `mypy` y la suite completa de
`pytest`. Al final, además: `npm test` de `chat-pwa`, `tests/test_scripts.py`,
`test-installers.sh`, una simulación de actualización de árbol antiguo → árbol
nuevo con una instalación editable obsoleta y la ejecución de cada lanzador por
ruta desde un directorio de trabajo ajeno.

**No verificado aquí:** macOS y Windows. No se modificó nada de `install.ps1`,
`update.ps1`, `uninstall.ps1` ni de la generación de launchd o del Programador de
tareas, pero los nuevos lanzadores y el alias de `sys.modules` solo se han
ejecutado en Linux. Los trabajos de Windows/macOS de
`.github/workflows/test-installers.yml` son la primera comprobación real.

## Despliegue

Un paso por módulo, cada uno dejando su shim y terminando en verde:
andamiaje → `errors` → `core` → `config` → `indexing/storage` →
`indexing/documents` → `indexing/state` → `indexing/indexer` →
`supervisor/recovery_server` → `supervisor/service_manager` → empaquetado, CI,
Docker y referencias en la documentación.

## Notas de implementación

- Los alcances de cobertura, bandit y `py_compile` se tradujeron uno a uno
  (`--cov=trinaxai.core --cov=trinaxai.supervisor.service_manager
  --cov=trinaxai.indexing.indexer`, bandit sobre los dos antiguos archivos de la
  raíz) en lugar de ampliarlos a todo el paquete, de modo que las barreras miden lo
  mismo que antes. Ampliarlas es una decisión aparte. En la máquina de desarrollo
  el agregado se mantuvo en 96,63 % frente a 96,65 % antes del movimiento (las 8
  sentencias adicionales son el nuevo `main()` de `recovery_server` y la
  importación de `PROJECT_ROOT`).
- `.github/CODEOWNERS` incorporó `trinaxai/config.py` y `/trinaxai/supervisor/`
  para que la protección que seguía a las rutas antiguas siga a los archivos
  movidos.
- `pyproject.toml` conserva `py-modules = [config, trinaxai_core, trinaxai_errors]`
  (ahora los shims) para que los consumidores del wheel que importan los nombres
  antiguos no se vean afectados.
