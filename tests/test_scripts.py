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


def test_windows_installer_has_automatic_ollama_fallback() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "function Require-Ollama" in script
    assert "https://ollama.com/install.ps1" in script
    assert "https://ollama.com/download/OllamaSetup.exe" in script
    assert "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" in script
    assert "O=Ollama Inc\\." in script


def test_windows_installer_configures_rag_transport_and_lan_firewall() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "function Sync-RagTransportFromCertificate" in script
    assert "TRINAXAI_RAG_HTTPS" in script
    assert "http://127.0.0.1:3333" in script
    assert "New-NetFirewallRule" in script
    assert "3333" in script and "3334" in script


def test_installers_use_light_models_for_8gb_profile() -> None:
    for script_name in ("install.ps1", "install.sh"):
        script = (ROOT / script_name).read_text(encoding="utf-8")
        assert "llama3.2:1b" in script
        assert "qwen2.5-coder:1.5b" in script
        assert "nomic-embed-text" in script
        assert "moondream" in script


def test_windows_update_and_uninstall_scripts_exist() -> None:
    update = (ROOT / "update.ps1").read_text(encoding="utf-8")
    uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert "git pull --ff-only" in update
    assert "npm run build" in update
    assert "service_manager.py" in update
    assert "Type UNINSTALL to continue" in uninstall
    assert "Remove-TrinaxAIFirewallRules" in uninstall
    assert "service_manager.py" in uninstall
