from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _string_array(manifest: str, table: str, key: str) -> list[str]:
    table_body = manifest.split(f"[{table}]", 1)[1].split("\n[", 1)[0]
    match = re.search(rf"(?ms)^{re.escape(key)}\s*=\s*\[(.*?)^\]", table_body)
    assert match is not None
    return re.findall(r'"([^"]+)"', match.group(1))


def test_wheel_declares_cli_only_contents() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")
    expected = {"config", "trinaxai_core", "trinaxai_errors"}

    assert set(_string_array(manifest, "tool.setuptools", "py-modules")) == expected
    assert all((root / f"{module}.py").is_file() for module in expected)
    assert _string_array(manifest, "tool.setuptools.packages.find", "include") == ["trinaxai_cli*"]


def test_manifest_exposes_only_cli_and_development_dependencies() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert _string_array(manifest, "project", "dependencies") == [
        "defusedxml>=0.7.1",
        "httpx>=0.28.1",
        "prompt-toolkit>=3.0.48",
        "rich>=13.0",
    ]
    optional = manifest.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
    assert re.findall(r"(?m)^([A-Za-z0-9_-]+)\s*=", optional) == ["dev"]
    assert "Development Status :: 5 - Production/Stable" in manifest
    assert "Development Status :: 4 - Beta" not in manifest


def test_built_wheel_is_an_isolated_cli_not_a_full_runtime(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(root / name, source / name)
    for module in root.glob("*.py"):
        shutil.copy2(module, source / module.name)
    shutil.copytree(root / "app", source / "app")
    shutil.copytree(root / "trinaxai_cli", source / "trinaxai_cli")

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(source),
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
        ],
        cwd=source,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr or build.stdout
    wheels = list(wheelhouse.glob("*.whl"))
    assert len(wheels) == 1

    target = tmp_path / "site-packages"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheels[0])],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr or install.stdout

    probe = """
import importlib
import importlib.metadata
import importlib.util
import pkgutil
import sys

target = sys.argv[1]
sys.path.insert(0, target)
for name in ("config", "trinaxai_core", "trinaxai_errors", "trinaxai_cli.app"):
    module = importlib.import_module(name)
    assert target in module.__file__, (name, module.__file__)

blocked = {
    "app",
    "index",
    "rag_api",
    "recovery_server",
    "service_manager",
    "trinaxai_index_documents",
    "trinaxai_index_state",
    "trinaxai_index_storage",
}

class BlockExcludedRuntime:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise ModuleNotFoundError(f"excluded runtime import attempted: {fullname}")
        return None

sys.meta_path.insert(0, BlockExcludedRuntime())
for name in blocked:
    try:
        importlib.import_module(name)
    except ImportError:
        pass
    else:
        raise AssertionError(f"backend module leaked into CLI wheel: {name}")

import trinaxai_cli.commands
for command in pkgutil.iter_modules(trinaxai_cli.commands.__path__):
    importlib.import_module(f"trinaxai_cli.commands.{command.name}")

metadata = next(importlib.metadata.distributions(path=[target])).metadata
assert metadata.get_all("Provides-Extra") == ["dev"]
assert "Development Status :: 5 - Production/Stable" in metadata.get_all("Classifier")
assert "Development Status :: 4 - Beta" not in metadata.get_all("Classifier")

from trinaxai_cli import runtime
from trinaxai_cli.commands import _lifecycle, _system

assert runtime.find_install_root() is None

class UI:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)

ui = UI()
assert _system.run_service_action("status", ui) == 1
assert _lifecycle.run_script("update", [], ui) == 1
assert len(ui.errors) == 2
assert all("Cannot locate the TrinaxAI installation" in message for message in ui.errors)
"""
    probe_env = env.copy()
    probe_env.pop("TRINAXAI_HOME", None)
    probe_env["HOME"] = str(tmp_path)
    probe_env["XDG_DATA_HOME"] = str(tmp_path / "xdg")
    imported = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(target)],
        cwd=tmp_path,
        env=probe_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr or imported.stdout


def test_project_has_one_canonical_cli() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert 'trinaxai = "trinaxai_cli.app:main"' in manifest
    assert not (root / "trinaxai_cli.py").exists()
