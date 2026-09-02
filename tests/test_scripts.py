from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_evaluate_rag_reports_invalid_saved_results(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    results.write_text("[]", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "evaluate_rag.py"), "--results", str(results)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "--results must contain a JSON object" in completed.stderr


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
    assert "TrinaxAI RAG API: running" in script
    assert "could not confirm the API stopped" in script
    assert "TRINAXAI_BACKUP_QUIESCE" in script
    assert "with_index_lock.py" in script
    assert "exclusive_process_lock" in helper


@pytest.mark.skipif(os.name == "nt", reason="Bash scripts are validated on POSIX runners")
def test_backup_stops_the_display_named_api_before_archive_and_restores_it(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(ROOT / "backup.sh", repo / "backup.sh")
    (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (repo / "storage").mkdir()
    (repo / "storage" / "state.json").write_text("{}", encoding="utf-8")
    (repo / "service_manager.py").write_text(
        """
import sys
from pathlib import Path

root = Path(__file__).parent
state = root / "service.state"
log = root / "service.log"
action = sys.argv[1]
log.open("a", encoding="utf-8").write(action + "\\n")
if action == "status":
    print(f"TrinaxAI RAG API: {'running' if state.read_text() == 'running' else 'stopped'}")
elif action == "stop-ai":
    state.write_text("stopped", encoding="utf-8")
elif action == "start-ai":
    state.write_text("running", encoding="utf-8")
""".strip(),
        encoding="utf-8",
    )
    (repo / "service.state").write_text("running", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(repo / "backup.sh"), "create"],
        cwd=repo,
        env={**os.environ, "TRINAXAI_BACKUP_DIR": str(tmp_path / "backups")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / "service.log").read_text(encoding="utf-8").splitlines() == [
        "status",
        "stop-ai",
        "status",
        "start-ai",
        "status",
    ]
    assert (repo / "service.state").read_text(encoding="utf-8") == "running"
    assert Path(result.stdout.strip()).is_file()


def test_windows_backup_pauses_and_restores_the_api_around_compression() -> None:
    script = (ROOT / "update.ps1").read_text(encoding="utf-8")

    assert "Get-TrinaxAIServiceStatus" in script
    assert "Test-TrinaxAIRagApiRunning" in script
    assert 'Invoke-ServiceManager "stop-ai"' in script
    assert 'Invoke-ServiceManager "start-ai"' in script
    assert "Compress-Archive" in script
    assert "finally" in script
    assert script.index('Invoke-ServiceManager "stop-ai"') < script.index("Compress-Archive")


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
    assert (
        'default_source_archive_url="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${release_version}/${source_archive_name}"'
        in posix
    )
    assert "releases/download/v$ReleaseVersion/$DefaultSourceArchiveName" in windows
    assert "Git\\usr\\bin\\openssl.exe" not in windows
    assert "TRINAXAI_HOME=" in windows


def test_user_install_docs_reject_unpinned_trinaxai_bootstraps() -> None:
    paths = (
        "install.sh",
        "install.ps1",
        "README.md",
        "README.es.md",
        "TESTING.md",
        "TESTING.es.md",
        "docs/README.md",
        "docs/README.es.md",
        "docs/INSTALL_LINUX.md",
        "docs/INSTALL_LINUX.es.md",
        "docs/INSTALL_MACOS.md",
        "docs/INSTALL_MACOS.es.md",
        "docs/INSTALL_WINDOWS.md",
        "docs/INSTALL_WINDOWS.es.md",
    )
    forbidden = (
        "raw.githubusercontent.com/TrinaxCode/TrinaxAI/main",
        "github.com/TrinaxCode/TrinaxAI/archive/refs/heads/main",
    )
    for path in paths:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert not any(marker in text for marker in forbidden), path


def test_release_installer_guides_verify_exact_asset_before_execution() -> None:
    paths = (
        "install.sh",
        "install.ps1",
        "README.md",
        "README.es.md",
        "TESTING.md",
        "TESTING.es.md",
        "docs/README.md",
        "docs/README.es.md",
        "docs/INSTALL_LINUX.md",
        "docs/INSTALL_LINUX.es.md",
        "docs/INSTALL_MACOS.md",
        "docs/INSTALL_MACOS.es.md",
        "docs/INSTALL_WINDOWS.md",
        "docs/INSTALL_WINDOWS.es.md",
    )
    for path in paths:
        text = (ROOT / path).read_text(encoding="utf-8")
        if "installer.sh" in text:
            download = text.index("TrinaxAI-${version}-installer.sh")
            execution = text.index('bash "$installer"', download)
            assert download < text.index("SHA256SUMS", download) < execution, path
            assert text.index('awk -v asset="TrinaxAI-${version}-installer.sh"', download) < execution, path
            assert any(marker in text[download:execution] for marker in ("sha256sum", "shasum -a 256")), path
        if "installer.ps1" in text:
            download = text.index("TrinaxAI-$version-installer.ps1")
            execution = text.index("& $installer", download)
            assert download < text.index("SHA256SUMS", download) < execution, path
            assert text.index("Get-FileHash -Algorithm SHA256", download) < execution, path


def test_installers_only_advertise_live_urls_after_runtime_readiness() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")

    posix_done = posix[posix.index("# ── Done ──") :]
    assert 'if [ "$START_NOW" = "1" ]; then' in posix_done
    assert "Installation prepared; TrinaxAI is not running." in posix_done
    assert posix_done.index('if [ "$START_NOW" = "1" ]; then') < posix_done.index("https://localhost:3334")

    windows_done = windows[windows.rindex("if ($NoStart) {") :]
    assert "Installation prepared; TrinaxAI is not running." in windows_done
    assert windows_done.index("} else {") < windows_done.index("https://localhost:3334")


def test_no_models_contract_requires_preinstalled_configured_models() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "checking the configured models already installed" in posix
    assert "installed models will still be verified" in windows
    assert "every configured Ollama model" in readme
    assert "already be installed" in readme


def test_installers_use_persisted_models_and_never_autostart_with_no_start() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "configured_models()" in posix
    assert 'for model in "${MODELS[@]}"; do' in posix
    posix_guard = 'if [ "$START_NOW" = "1" ] && [ "$ENABLE_AUTOSTART" = "1" ]; then'
    posix_autostart = posix.rsplit(posix_guard, 1)[1].split("\n", 4)[0:4]
    assert "python service_manager.py enable-autostart" in "\n".join(posix_autostart)

    assert "function Get-ConfiguredModels" in windows
    assert "$Models = @(Get-ConfiguredModels)" in windows
    windows_guard = "if (-not $NoStart -and -not $NoAutostart) {"
    windows_autostart = windows.rsplit(windows_guard, 1)[1].split("\n", 4)[0:4]
    assert '"enable-autostart"' in "\n".join(windows_autostart)


def test_installer_release_version_docs_match_versioned_default() -> None:
    docs = (ROOT / "docs" / "ENVIRONMENT_VARIABLES.md").read_text(encoding="utf-8")

    release_row = next(line for line in docs.splitlines() if "`TRINAXAI_RELEASE_VERSION`" in line)
    assert "| `1.2.1` |" in release_row
    assert "never falls back to `main`" in release_row


def test_desktop_manager_is_removed_from_the_product() -> None:
    assert not (ROOT / "trinaxai_manager.py").exists()
    assert not (ROOT / "scripts" / "build_manager.py").exists()
    assert not (ROOT / "tests" / "test_manager.py").exists()
    assert not (ROOT / ".github" / "workflows" / "build-manager.yml").exists()


def test_installers_never_advertise_or_forward_lan_host_administration() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "Enable LAN system-control endpoints" not in posix
    assert "Activar endpoints de control LAN" not in posix
    assert "ENABLE_LAN_SYSTEM=0" in posix
    assert 'PS_ARGS+=("-LanSystem")' not in posix
    assert 'if ($LanSystem) { $Forward += "-LanSystem" }' not in windows
    assert "$EnableLanSystem = 0" in windows
    assert "TRINAXAI_ALLOW_LAN_SYSTEM=1" not in windows


def test_installers_share_conservative_profile_thresholds_and_preserve_models() -> None:
    posix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
    setup = (ROOT / "setup_trinaxai.sh").read_text(encoding="utf-8")

    for script in (posix, windows):
        assert "detect_hardware" in script
        assert "model_recommendations" in script
        assert '"8gb", "16gb", "32gb", "64gb"' in script
    assert "qwen3.5:35b qwen3-coder:30b" in setup
    assert "qwen3.5:4b qwen3.5:9b" in setup
    assert "qwen3-embedding:4b qwen3.5:4b" in setup
    assert "ollama rm" not in setup


def test_windows_installer_uses_canonical_profiles_and_embedding_fleet() -> None:
    windows = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert 'ValidateSet("8gb", "16gb", "32gb", "64gb"' in windows
    assert '"detected_profile"' in windows
    assert "select_profile" in windows
    assert "TRINAXAI_PROFILE=$Profile" in windows
    assert "qwen3-embedding:8b" not in windows


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
    assert "if ($RemoveOllamaApp) { Remove-OllamaModelsAndState }" in windows


def test_uninstallers_default_to_guided_mode() -> None:
    posix = (ROOT / "uninstall.sh").read_text(encoding="utf-8")
    windows = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert 'INTERACTIVE="${TRINAXAI_INTERACTIVE:-1}"' in posix
    assert "if (-not ($Interactive -or $Yes -or $NonInteractive))" in windows
    assert "Type UNINSTALL to continue" in windows
    assert "[switch]$RemoveEnv" in windows
    assert "$RemoveEnvRequested = [bool]$RemoveEnv -and -not $KeepEnv" in windows
    assert "Non-interactive uninstall requires -Yes." in windows
    assert "$RemoveEnv = -not $KeepEnv" not in windows


def test_windows_installer_configures_rag_transport_and_lan_firewall() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "function Sync-RagTransportFromCertificate" in script
    assert "TRINAXAI_RAG_HTTPS" in script
    assert "http://127.0.0.1:3333" in script
    assert "New-NetFirewallRule" in script
    assert "3333" in script and "3334" in script


def test_installers_delegate_light_models_to_canonical_profile_matrix() -> None:
    for script_name in ("install.ps1", "install.sh"):
        script = (ROOT / script_name).read_text(encoding="utf-8")
        assert "model_recommendations" in script
        assert "qwen3-embedding:0.6b" in script


def test_profile_model_fallback_lists_do_not_repeat_models() -> None:
    setup = (ROOT / "setup_trinaxai.sh").read_text(encoding="utf-8")
    update = (ROOT / "update.sh").read_text(encoding="utf-8")
    update_ps1 = (ROOT / "update.ps1").read_text(encoding="utf-8")
    assert "qwen3.5:2b qwen3.5:2b" not in setup
    assert "qwen3.5:2b qwen3.5:2b" not in update
    assert '"qwen3.5:2b", "qwen3.5:2b"' not in update_ps1


def test_release_model_matrix_is_synced_to_updates_env_and_continue() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    updates = (ROOT / "update.sh").read_text(encoding="utf-8") + (ROOT / "update.ps1").read_text(encoding="utf-8")
    continue_config = (ROOT / "continue-config.yaml").read_text(encoding="utf-8")

    assert "qwen3.5:4b" in env and "qwen2.5-coder:0.5b" not in env
    assert "TRINAXAI_MODEL_CODE" in updates
    assert "qwen3-coder:30b" in continue_config


def test_windows_update_and_uninstall_scripts_exist() -> None:
    update = (ROOT / "update.ps1").read_text(encoding="utf-8")
    uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert "Sync-TrinaxRepository" in update
    assert "scripts\\source_update.py" in update
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


def test_updaters_use_archives_and_scheduled_mode_is_check_only() -> None:
    posix = (ROOT / "update.sh").read_text(encoding="utf-8")
    windows = (ROOT / "update.ps1").read_text(encoding="utf-8")

    assert "--scheduled" in posix
    assert "git init -q" not in posix
    assert 'scripts/source_update.py" update --root' in posix
    assert "git fetch --prune origin main" not in posix
    assert "check-only" in posix
    assert "scripts/auto_update.py run" in posix
    assert "[switch]$Scheduled" in windows
    assert "git init -q" not in windows
    assert '"update", "--root", $Repo' in windows
    assert "git fetch --prune origin main" not in windows
    assert "no remote code execution" in windows


@pytest.mark.skipif(os.name == "nt", reason="Bash wrapper is validated on POSIX runners")
def test_updater_wrappers_reject_unchecksummed_custom_file_urls(tmp_path: Path) -> None:
    posix = (ROOT / "update.sh").read_text(encoding="utf-8")
    windows = (ROOT / "update.ps1").read_text(encoding="utf-8")
    assert 'SOURCE_UPDATE_URL" != file://' not in posix
    assert "$SourceUpdateUrl -and -not $IsReleaseSourceUrl" in windows

    result = subprocess.run(
        ["bash", str(ROOT / "update.sh"), "--dry-run"],
        cwd=ROOT,
        env={**os.environ, "TRINAXAI_UPDATE_SOURCE_URL": (tmp_path / "source.tar.gz").as_uri()},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SHA-256 checksum is required" in result.stderr


def test_archive_update_rolls_back_after_partial_failure() -> None:
    updater = (ROOT / "update.sh").read_text(encoding="utf-8")

    assert 'scripts/source_update.py" rollback --root' in updater
    assert "ROLLBACK_ACTIVE=1" in updater
    windows = (ROOT / "update.ps1").read_text(encoding="utf-8")
    assert "Restore-FailedUpdate" in windows
    assert '"rollback", "--root", $Repo' in windows
    assert "$script:RollbackActive = $true" in windows


def test_tagged_releases_publish_a_simple_verified_release() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'tags:\n      - "v*.*.*"' in workflow
    assert "Verify package versions" in workflow
    assert "Build release assets" in workflow
    assert "pip wheel . --no-deps" in workflow
    assert "installer.sh" in workflow
    assert "installer.ps1" in workflow
    assert "SHA256SUMS" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow
    assert "--generate-notes" in workflow
    assert "docker/setup-buildx-action@37fe631027851001ddb9b187196cc803df7f5f0e" in workflow
    assert "actions/attest@v4" not in workflow


def test_system_setup_never_sudo_executes_user_writable_repo_scripts() -> None:
    script = (ROOT / "setup_trinaxai.sh").read_text(encoding="utf-8")
    hardened = (ROOT / "scripts" / "harden_systemd_units.sh").read_text(encoding="utf-8")
    assert "NOPASSWD: $PROJ/startup_ai.sh" not in script
    assert "/usr/local/libexec/trinaxai" in script
    assert "chown root:root" in script
    assert 'Environment="OLLAMA_HOST=127.0.0.1:11434"' in script
    assert "--host 127.0.0.1" in script
    for text in (script, hardened):
        assert "After=network.target ai-rag.service" not in text
        assert "Wants=ai-rag.service" not in text


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
    assert "resolve_latest_release" in updater
    assert "git" not in updater
