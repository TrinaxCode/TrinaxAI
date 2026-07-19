from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="Bash scripts are validated on POSIX runners")
def test_bash_scripts_parse() -> None:
    for script in [
        "install.sh",
        "backup.sh",
        "update.sh",
        "uninstall.sh",
        "startup_ai.sh",
        "shutdown_ai.sh",
        "setup_trinaxai.sh",
    ]:
        result = subprocess.run(
            ["bash", "-n", str(ROOT / script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"


@pytest.mark.skipif(os.name == "nt", reason="Bash scripts are validated on POSIX runners")
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


@pytest.mark.skipif(os.name == "nt", reason="Bash scripts are validated on POSIX runners")
def test_backup_is_private_and_restore_rejects_links(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(ROOT / "backup.sh", repo / "backup.sh")
    (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (repo / "storage" / ".inference.lock").mkdir(parents=True)
    (repo / "storage" / ".inference.lock" / "owner.json").write_text("{}", encoding="utf-8")
    (repo / "storage" / "state.json").write_text("{}", encoding="utf-8")
    backup_dir = tmp_path / "archives"
    result = subprocess.run(
        ["bash", str(repo / "backup.sh"), "create"],
        cwd=repo,
        env={**os.environ, "TRINAXAI_BACKUP_DIR": str(backup_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    archive = Path(result.stdout.strip())
    assert archive.stat().st_mode & 0o077 == 0
    assert backup_dir.stat().st_mode & 0o077 == 0
    with tarfile.open(archive, "r:gz") as handle:
        names = handle.getnames()
    assert "storage/state.json" in names
    assert not any(".inference.lock" in name for name in names)

    bad = tmp_path / "link.tar.gz"
    info = tarfile.TarInfo("storage/escape")
    info.type = tarfile.SYMTYPE
    info.linkname = "/etc/passwd"
    with tarfile.open(bad, "w:gz") as handle:
        handle.addfile(info)
    restored = subprocess.run(
        ["bash", str(repo / "backup.sh"), "restore", str(bad)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored.returncode != 0
    assert "unsafe entry type" in restored.stderr.lower()


def test_backup_quiesces_services_and_takes_index_lock() -> None:
    script = (ROOT / "backup.sh").read_text(encoding="utf-8")
    helper = (ROOT / "scripts" / "with_index_lock.py").read_text(encoding="utf-8")

    assert "stop-ai" in script and "start-ai" in script
    assert "TRINAXAI_BACKUP_QUIESCE" in script
    assert "with_index_lock.py" in script
    assert "exclusive_process_lock" in helper


def test_windows_installer_has_automatic_ollama_fallback() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "function Require-Ollama" in script
    assert "https://ollama.com/install.ps1" in script
    assert "https://ollama.com/download/OllamaSetup.exe" in script
    assert "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" in script
    assert "O=Ollama Inc\\." in script


def test_installers_support_client_first_install_locations() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "--install-dir" in posix
    assert "TRINAXAI_HOME" in posix
    assert "XDG_DATA_HOME" in posix
    assert "Application Support" in posix
    assert "[string]$InstallDir" in windows
    assert "TrinaxAI/archive/refs/heads/main.zip" in windows
    assert "TRINAXAI_HOME=" in windows


def test_installers_share_conservative_profile_thresholds_and_preserve_models() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
    setup = (ROOT / "setup_trinaxai.sh").read_text(encoding="utf-8")

    assert '"${ram_gb:-0}" -ge 64' in posix
    assert '"${ram_gb:-0}" -ge 32' in posix
    assert "$RamGb -ge 64" in windows
    assert "$RamGb -ge 32" in windows
    assert "qwen3-vl:30b-a3b-instruct" in setup
    assert "qwen3.5:27b qwen2.5-coder:14b qwen3-vl:8b-instruct" in setup
    assert "ollama rm" not in setup


def test_git_bash_installer_forwards_custom_install_directory_to_powershell() -> None:
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert script.count('PS_ARGS+=("-InstallDir" "$INSTALL_DIR")') == 2


def test_uninstallers_remove_cli_registration_and_trusted_certificates() -> None:
    posix = (ROOT / "uninstall.sh").read_text(encoding="utf-8")
    windows = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert ".local/bin/trinaxai" in posix
    assert "trinaxai-local.crt" in posix
    assert "Remove-UserPath" in windows
    assert "Remove-TrinaxAICertificates" in windows


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
        assert "qwen3.5:0.8b" in script
        assert "qwen2.5-coder:1.5b" in script
        assert "bge-m3" in script
        assert "qwen3-vl:2b-instruct" in script


def test_release_model_matrix_is_synced_to_updates_env_and_continue() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    updates = (ROOT / "update.sh").read_text(encoding="utf-8") + (ROOT / "update.ps1").read_text(encoding="utf-8")
    continue_config = (ROOT / "continue-config.yaml").read_text(encoding="utf-8")

    assert "qwen2.5-coder:1.5b" in env and "qwen2.5-coder:0.5b" not in env
    assert all(model in updates for model in ("granite4:3b", "qwen3.5:2b", "qwen2.5-coder:1.5b", "bge-m3"))
    assert all(model in continue_config for model in ("qwen2.5-coder:1.5b", "qwen2.5-coder:14b", "qwen3-coder:30b"))


def test_windows_update_and_uninstall_scripts_exist() -> None:
    update = (ROOT / "update.ps1").read_text(encoding="utf-8")
    uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert "Sync-TrinaxRepository" in update
    assert "git fetch --prune origin main" in update
    assert "npm run build" in update
    assert "service_manager.py" in update
    assert "Type UNINSTALL to continue" in uninstall
    assert "Remove-TrinaxAIFirewallRules" in uninstall
    assert "service_manager.py" in uninstall


def test_installers_manage_weekly_automatic_updates() -> None:
    posix_install = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows_install = (ROOT / "install.ps1").read_text(encoding="utf-8")
    posix_uninstall = (ROOT / "uninstall.sh").read_text(encoding="utf-8")
    windows_uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert "scripts/auto_update.py enable" in posix_install
    assert '"scripts\\auto_update.py" "enable"' in windows_install
    assert "trinaxai-update.timer" in posix_uninstall
    assert "TrinaxAI Weekly Update" in windows_uninstall


def test_updaters_fail_closed_for_archives_and_scheduled_mode_is_check_only() -> None:
    posix = (ROOT / "update.sh").read_text(encoding="utf-8")
    windows = (ROOT / "update.ps1").read_text(encoding="utf-8")

    assert "--scheduled" in posix
    assert "git init -q" not in posix
    assert "git fetch --prune origin main" in posix
    assert "check-only" in posix
    assert "scripts/auto_update.py run" in posix
    assert "[switch]$Scheduled" in windows
    assert "git init -q" not in windows
    assert "git fetch --prune origin main" in windows
    assert "no remote code execution" in windows


def test_posix_update_rolls_back_a_clean_tree_after_partial_failure() -> None:
    updater = (ROOT / "update.sh").read_text(encoding="utf-8")

    assert 'PRE_UPDATE_COMMIT="$(git rev-parse HEAD)"' in updater
    assert 'git reset --hard "$PRE_UPDATE_COMMIT"' in updater
    assert "ROLLBACK_ACTIVE=1" in updater
    assert "PWA_DIST_BACKUP" in updater
    windows = (ROOT / "update.ps1").read_text(encoding="utf-8")
    assert "Restore-FailedUpdate" in windows
    assert "git reset --hard $script:PreUpdateCommit" in windows
    assert "$script:RollbackActive = $true" in windows


def test_tagged_releases_have_checksums_and_signed_provenance() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "actions/attest@v4" in workflow
    assert "sha256sum" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow


def test_system_setup_never_sudo_executes_user_writable_repo_scripts() -> None:
    script = (ROOT / "setup_trinaxai.sh").read_text(encoding="utf-8")
    assert "NOPASSWD: $PROJ/startup_ai.sh" not in script
    assert "/usr/local/libexec/trinaxai" in script
    assert "chown root:root" in script
    assert 'Environment="OLLAMA_HOST=127.0.0.1:11434"' in script
    assert "--host 127.0.0.1" in script


def test_installers_bind_privileged_backends_to_loopback() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
    manager = (ROOT / "service_manager.py").read_text(encoding="utf-8")

    for text in (posix, windows):
        assert "TRINAXAI_HOST=127.0.0.1" in text
        assert "OLLAMA_HOST=127.0.0.1:11434" in text
    assert 'env.get("TRINAXAI_HOST", "127.0.0.1")' in manager


def test_weekly_updater_never_downloads_or_executes_remote_scripts() -> None:
    updater = (ROOT / "scripts" / "auto_update.py").read_text(encoding="utf-8")
    assert "urllib.request" not in updater
    assert "raw.githubusercontent.com" not in updater
    assert '"ls-remote"' in updater
