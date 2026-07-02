from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bash_scripts_parse() -> None:
    for script in [
        "install.sh",
        "backup.sh",
        "update.sh",
        "uninstall.sh",
        "unistall.sh",
        "startup_ai.sh",
        "shutdown_ai.sh",
    ]:
        result = subprocess.run(
            ["bash", "-n", str(ROOT / script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"


def test_backup_restore_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("bad", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="../escape.txt")

    result = subprocess.run(
        ["bash", str(ROOT / "backup.sh"), "restore", str(archive)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "path traversal" in result.stderr.lower()
