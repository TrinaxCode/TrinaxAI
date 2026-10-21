"""Pin the root-module -> ``trinaxai`` package contract (docs/adr/0001-python-package-layout.md)."""

from __future__ import annotations

import importlib
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# legacy import name -> real module
MOVED = {
    "config": "trinaxai.config",
    "trinaxai_core": "trinaxai.core",
    "trinaxai_errors": "trinaxai.errors",
    "trinaxai_index_documents": "trinaxai.indexing.documents",
    "trinaxai_index_state": "trinaxai.indexing.state",
    "trinaxai_index_storage": "trinaxai.indexing.storage",
    "index": "trinaxai.indexing.indexer",
    "service_manager": "trinaxai.supervisor.service_manager",
    "recovery_server": "trinaxai.supervisor.recovery_server",
}

# Files that installers, units, the CLI and the watcher locate on disk.
RUN_BY_PATH = ("index.py", "service_manager.py", "recovery_server.py", "rag_api.py")


@pytest.mark.parametrize(("legacy", "real"), sorted(MOVED.items()))
def test_legacy_name_is_the_real_module(legacy: str, real: str) -> None:
    assert importlib.import_module(legacy) is importlib.import_module(real)


@pytest.mark.parametrize("legacy", sorted(MOVED))
def test_every_legacy_path_still_exists_at_the_root(legacy: str) -> None:
    assert (ROOT / f"{legacy}.py").is_file()


def test_patching_through_a_legacy_name_affects_the_real_module(monkeypatch: pytest.MonkeyPatch) -> None:
    import config
    from trinaxai import config as real

    monkeypatch.setattr(config, "BASE_DIR", "/patched")
    assert real.BASE_DIR == "/patched"


def test_project_root_is_the_directory_holding_the_launchers() -> None:
    from trinaxai import config, paths

    assert Path(paths.PROJECT_ROOT) == ROOT
    assert ROOT.resolve() == paths.PROJECT_ROOT_RESOLVED
    assert Path(config.BASE_DIR) == ROOT
    for name in RUN_BY_PATH:
        assert (Path(paths.PROJECT_ROOT) / name).is_file()


@pytest.mark.parametrize("script", ["service_manager.py", "recovery_server.py"])
def test_launchers_run_by_path_from_another_directory(script: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--base-dir" in result.stdout


@pytest.mark.parametrize(
    ("script", "module", "entry"),
    [
        ("index.py", "trinaxai.indexing.indexer", "run_index"),
        ("service_manager.py", "trinaxai.supervisor.service_manager", "main"),
        ("recovery_server.py", "trinaxai.supervisor.recovery_server", "main"),
    ],
)
def test_launcher_main_dispatches_to_the_real_entry_point(
    script: str, module: str, entry: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(importlib.import_module(module), entry, lambda *_a, **_k: 7)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / script), run_name="__main__")
    assert exc.value.code == 7


def test_shims_find_the_package_when_the_editable_mapping_predates_it(tmp_path: Path) -> None:
    """A venv whose editable install only maps the old names must still import the shims."""
    probe = """
import importlib.util, sys
root = sys.argv[1]
sys.meta_path[:] = [f for f in sys.meta_path if getattr(f, "__module__", "").startswith("_frozen_importlib")]  # no editable finders
assert root not in sys.path and importlib.util.find_spec("trinaxai") is None
spec = importlib.util.spec_from_file_location("trinaxai_errors", root + "/trinaxai_errors.py")
module = importlib.util.module_from_spec(spec)
sys.modules["trinaxai_errors"] = module
spec.loader.exec_module(module)
assert sys.modules["trinaxai_errors"].__name__ == "trinaxai.errors"
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(ROOT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_package_bootstraps_a_stale_editable_install(tmp_path: Path) -> None:
    """``trinaxai_cli`` mapped by an old editable finder must still reach ``trinaxai``."""
    probe = """
import importlib.machinery, importlib.util, sys
root = sys.argv[1]
sys.meta_path[:] = [f for f in sys.meta_path if getattr(f, "__module__", "").startswith("_frozen_importlib")]  # no editable finders

class OldEditableFinder:
    def find_spec(self, name, path=None, target=None):
        if name == "trinaxai_cli":
            return importlib.machinery.PathFinder.find_spec(name, [root])
        return None

sys.meta_path.insert(0, OldEditableFinder())
assert root not in sys.path and importlib.util.find_spec("trinaxai") is None
import trinaxai_cli
from trinaxai import errors
assert errors.__name__ == "trinaxai.errors"
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(ROOT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
