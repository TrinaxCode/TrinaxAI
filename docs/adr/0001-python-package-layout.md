# ADR 0001 — Move the flat root Python modules into a `trinaxai` package

- **Status:** Accepted, implemented in the same change set (see [Rollout](#rollout)).
- **Date:** 2026-10-20
- **Scope:** `config.py`, `index.py`, `rag_api.py`, `service_manager.py`,
  `trinaxai_core.py`, `trinaxai_errors.py`, `trinaxai_index_documents.py`,
  `trinaxai_index_state.py`, `trinaxai_index_storage.py`, `recovery_server.py`.

## Context

The repository root mixed ten implementation modules with installers, config
files and the real packages (`app/`, `trinaxai_cli/`, `trinaxai_agent/`).
`docs/ARCHITECTURE.md` already described `index.py` and `rag_api.py` as
compatibility facades, so the split into responsibilities exists; only the
file layout is still flat.

The flat layout has concrete costs:

- `config`, `index` and `trinaxai_core` are top-level names. The CLI wheel ships
  a module literally called `config` into `site-packages`.
- Nothing says which root file is a library and which is a launcher run by path.
- `pyproject.toml`, `Dockerfile`, CI, `Makefile`, coverage flags and mypy each
  enumerate root files by hand.

The move is constrained by what **already-installed deployments** do at
runtime. These paths are baked into artifacts that exist on user machines and
are not rewritten by an upgrade:

| Runtime consumer | What it relies on |
|---|---|
| systemd unit / launchd plist / Windows task written by `service_manager` | `python <base>/service_manager.py watch --base-dir …` |
| `service_manager` process detection | command-line substrings such as `service_manager.py watch`, `uvicorn app.main:app`, `rag_api.py` |
| `app/services/system_service.py`, `watcher_service.py`, `trinaxai_cli/commands/index.py` | spawn `<base>/index.py` as a subprocess |
| `service_manager` | spawns `<base>/recovery_server.py` |
| `trinaxai_cli/commands/_system.py`, `trinaxai_cli/runtime.py`, `npm-package/bin/trinaxai.js`, `install.sh` | discover an installation by `service_manager.py` / `rag_api.py` existing on disk |
| `install.sh`, `install.ps1`, `update.sh`, `update.ps1`, `uninstall.sh`, `uninstall.ps1`, `backup.sh`, `startup_ai.sh`, `shutdown_ai.sh`, `chat-pwa/server.mjs`, `chat-pwa/vite.config.ts` | run `<base>/service_manager.py <action> --base-dir <base>` |
| `scripts/with_index_lock.py` (run by `backup.sh`) | `import trinaxai_core` through the venv's editable install |
| `.venv/bin/trinaxai` console script | `config`, `trinaxai_core`, `trinaxai_errors` resolved by the editable-install finder |
| `Dockerfile` | `COPY` of each root file; `BASE_DIR` is the directory holding `config.py` |

## Decision

1. Create the package `trinaxai/` and move implementations into it:

   ```
   trinaxai/__init__.py
   trinaxai/paths.py                  PROJECT_ROOT (single place that knows where the install root is)
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

   The wheel stays CLI-only: only the top-level modules of `trinaxai`
   (`__init__`, `paths`, `config`, `core`, `errors`) are packaged; the
   `indexing` and `supervisor` sub-packages are source-install only. The
   packaging test that proves backend modules do not leak into the wheel is
   extended accordingly.

2. **Every old path stays, as a shim, at the same location.** A shim replaces
   itself in `sys.modules` with the real module:

   ```python
   sys.modules[__name__] = trinaxai.config      # module identity is preserved
   ```

   `import config`, `from config import X`, `monkeypatch.setattr(config, …)`,
   `mock.patch("config.X")` and `importlib.reload(config)` therefore act on the
   one real module object. This matters because the test-suite and downstream
   integrations patch these modules heavily; a re-exporting shim (`from … import
   *`) would make patches silently ineffective.

3. **Launcher files stay at the root by design**: `index.py`,
   `service_manager.py`, `recovery_server.py` and `rag_api.py` are executed *by
   path* (table above), so their location is a runtime contract, not clutter.
   They become ~15-line launchers: when run as `__main__` they call the real
   `main()`; when imported they alias the real module like any other shim.
   `rag_api.py` is *not* moved: it already is only a compatibility module over
   `app.main`/`app.api_runtime` (its module-class trick is the compatibility
   surface) and `uvicorn rag_api:app` plus install detection depend on it.

4. **No installer, updater, uninstaller, Dockerfile entry command, systemd /
   launchd / Task-Scheduler generation or `server.mjs`/`vite.config.ts` launch
   code changes.** They keep calling the same root paths. The only
   non-Python artifacts touched are the ones that *enumerate files to copy or
   check*: `Dockerfile` (adds `COPY trinaxai`), `pyproject.toml`, CI,
   `Makefile`, `CODEOWNERS`, `scripts/public_readiness.py`.

5. `BASE_DIR` keeps its meaning (the install root). It is now computed once in
   `trinaxai/paths.py` as the parent of the `trinaxai` package directory, which
   equals the old "directory containing `config.py`" for source installs,
   Docker (`/app`) and the wheel (`site-packages`).

6. In-repo callers (`app/`, `trinaxai_cli/`, `trinaxai_agent/`, `scripts/`) are
   migrated to the new import paths. Tests keep importing the old names on
   purpose: they exercise the shims and prove identity, and a dedicated
   test (`tests/test_package_layout.py`) pins the contract.

## Upgrade and rollback analysis

`scripts/source_update.py` replaces the whole source tree (everything except
`.env`, `.venv`, `storage`, `logs`, `backups`, `local_sources`, `chat-pwa/dist`,
`chat-pwa/node_modules`, `chat-pwa/certs`) from the signed archive and restores
it from a backup on failure. `update.sh`/`update.ps1` then run
`pip install -e .`. Consequences:

- **Old → new:** all old root paths still exist after the replace, so anything
  started by path keeps working (launchers). Units and tasks written by older
  versions need no regeneration.
- **Stale editable-install mapping.** Between the tree replacement and the
  `pip install -e .` run (and for users who `git pull` without re-running pip),
  the venv's editable finder maps `config`/`trinaxai_core`/`trinaxai_errors` to
  the *root shim files* but knows nothing about `trinaxai`. Two guards make
  that safe: every shim appends its own directory (the install root) to
  `sys.path` before importing `trinaxai`, and `trinaxai_cli/__init__.py` does
  the same when `trinaxai` cannot be found. `scripts/with_index_lock.py`
  inserts the root explicitly instead of relying on the editable install.
- **New → old (rollback):** the backup restores the old tree. A leftover
  editable mapping that mentions `trinaxai` points at a directory that no longer
  exists and is ignored by the finder.
- **Running processes during an upgrade:** services are stopped through the
  *old* `service_manager.py` before the tree is replaced and started through
  the new launcher after. A long-lived old supervisor that lazily imports an
  old module name still resolves through the shim.

## Consequences

- Good: a real import namespace; `config`/`index` stop being top-level names
  for in-repo code; one place (`trinaxai/paths.py`) knows the root layout;
  coverage, mypy and bandit target a package instead of hand-maintained file
  lists.
- Cost: `__file__`-relative code and anything that read the old files as text
  must follow the move (`scripts/public_readiness.py` matrix check,
  `tests/test_scripts.py` assertion on `service_manager.py`, coverage flags).
- Cost: logger names and `__module__` change from `config` to
  `trinaxai.config` (the config logger was already named `trinaxai.config`).
- The shims are permanent for now. They can be removed in a major release once
  the support window for installs that predate this layout has ended; removal
  needs the launchers to stay.

## Verification

Per step: `ruff check`, `ruff format --check`, `mypy`, the full `pytest` suite.
At the end additionally: `chat-pwa` `npm test`, `tests/test_scripts.py`,
`test-installers.sh`, an old-tree → new-tree upgrade simulation with a stale
editable install, and running each launcher by path from a foreign working
directory.

**Not verified here:** macOS and Windows. Nothing in `install.ps1`,
`update.ps1`, `uninstall.ps1`, the launchd or Task Scheduler generation was
modified, but the new launchers and the `sys.modules` aliasing have only been
run on Linux. The Windows/macOS jobs of `.github/workflows/test-installers.yml`
are the first real check.

## Rollout

One step per module, each leaving its shim behind and each ending green:
scaffold → `errors` → `core` → `config` → `indexing/storage` →
`indexing/documents` → `indexing/state` → `indexing/indexer` →
`supervisor/recovery_server` → `supervisor/service_manager` → packaging,
CI, Docker and documentation references.

## Implementation notes

- Coverage, bandit and `py_compile` scopes were translated one to one
  (`--cov=trinaxai.core --cov=trinaxai.supervisor.service_manager
  --cov=trinaxai.indexing.indexer`, bandit on the two former root files)
  rather than widened to the whole package, so the gates measure what they
  measured before. Widening them is a separate decision. On the development
  machine the aggregate stayed at 96.63 % against 96.65 % before the move (the
  8 extra statements are the new `main()` in `recovery_server` and the
  `PROJECT_ROOT` import).
- `.github/CODEOWNERS` gained `trinaxai/config.py` and `/trinaxai/supervisor/`
  so the protection that followed the old paths follows the moved files.
- `pyproject.toml` keeps `py-modules = [config, trinaxai_core, trinaxai_errors]`
  (now the shims) so wheel consumers that import the old names are unaffected.
