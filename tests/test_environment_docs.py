from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIABLE_PATTERN = re.compile(r"\b(?:VITE_)?TRINAXAI_[A-Z0-9_]+\b")


def _production_configuration_files() -> list[Path]:
    files = [
        *ROOT.glob("*.py"),
        *ROOT.glob("*.sh"),
        *ROOT.glob("*.ps1"),
        *ROOT.glob("app/**/*.py"),
        *ROOT.glob("scripts/**/*.py"),
        *ROOT.glob("trinaxai_cli/**/*.py"),
        ROOT / "chat-pwa" / "vite.config.ts",
        ROOT / "chat-pwa" / "src" / "lib" / "config.ts",
        ROOT / "chat-pwa" / "src" / "lib" / "api.ts",
    ]
    return sorted({path for path in files if path.is_file()})


def test_all_production_trinaxai_variables_are_in_the_canonical_inventory() -> None:
    documented = set(VARIABLE_PATTERN.findall((ROOT / "docs" / "ENVIRONMENT_VARIABLES.md").read_text(encoding="utf-8")))
    used: set[str] = set()
    for path in _production_configuration_files():
        used.update(VARIABLE_PATTERN.findall(path.read_text(encoding="utf-8")))

    assert used <= documented, f"Undocumented environment variables: {sorted(used - documented)}"


def test_readmes_link_the_canonical_environment_inventory() -> None:
    for name in ("README.md", "README.es.md"):
        assert "docs/ENVIRONMENT_VARIABLES.md" in (ROOT / name).read_text(encoding="utf-8")
