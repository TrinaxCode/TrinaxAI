"""Inspect or refresh TrinaxAI after the host changes local networks."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any

from trinaxai_cli import network
from trinaxai_cli.commands import _system


def _show_trust_certificate(root: Any, ui: Any) -> None:
    certificate = network.trust_certificate(root)
    if not certificate:
        return
    path, kind = certificate
    if kind == "mkcert":
        ui.info(f"LAN trust CA for phones: {path}")
        ui.info("Install this CA only on devices you control; never share the private key.")
    else:
        ui.info(f"LAN certificate for phones: {path}")
        ui.info("Import this certificate only on devices you control; never share the private key.")


def _turn_off(args: Any, root: Any, ui: Any) -> int:
    """Keep TrinaxAI on this computer only, undoing "allow other devices"."""
    if not network.lan_access_enabled(root):
        ui.info("Already limited to this computer; nothing to change.")
        return 0
    if not getattr(args, "yes", False) and not ui.confirm("Keep TrinaxAI on this computer only?", default=True):
        ui.info("Cancelled.")
        return 0
    try:
        network.disable_lan_access(root)
    except (OSError, RuntimeError) as exc:
        ui.failure("Network change", exc)
        return 1
    ui.success("TrinaxAI is now limited to this computer.")
    if getattr(args, "no_restart", False):
        ui.warn("Restart TrinaxAI to apply it.")
        return 0
    rc = _system.run_service_action("reload-network", ui, timeout=180)
    if rc != 0:
        ui.warn("Configuration saved. Restart the PWA and RAG services to apply it.")
    return rc


def run(args: Any, _client: Any, ui: Any, _config: Any) -> int:
    root = _system.project_root()
    if root is None:
        ui.error("Cannot locate the TrinaxAI installation. Set TRINAXAI_HOME or run this command there.")
        return 1
    if getattr(args, "network_command", None) == "off":
        return _turn_off(args, root, ui)
    addresses = network.lan_addresses()
    urls = network.pwa_urls(addresses)
    if getattr(args, "network_command", None) != "refresh":
        if not network.lan_access_enabled(root):
            # LAN addresses would only mislead here: nothing listens on them.
            ui.info("Access from other devices: this computer only")
            ui.print("https://localhost:3334")
            ui.info("To open TrinaxAI from a phone or another computer, run: trinaxai network refresh")
            return 0
        ui.info("Access from other devices: allowed (each device must be paired)")
        ui.info("Use 'trinaxai network off' to keep TrinaxAI on this computer only.")
        ui.info(f"Host: {network.local_hostname()}")
        ui.info(f"LAN addresses: {', '.join(addresses) if addresses else '(none detected)'}")
        for url in urls:
            ui.print(url)
        _show_trust_certificate(root, ui)
        ui.info("Use 'trinaxai network refresh' after changing Wi-Fi or router.")
        return 0

    if not addresses:
        ui.error("No private LAN address was detected. Connect the host to Wi-Fi or Ethernet and try again.")
        return 1
    if not getattr(args, "yes", False) and not ui.confirm(
        "Refresh HTTPS and allow the current local network?", default=False
    ):
        ui.info("Cancelled.")
        return 0
    try:
        network.refresh_certificate(root, addresses)
        network.update_env(root, addresses)
    except (OSError, RuntimeError) as exc:
        ui.failure("Network refresh", exc)
        return 1
    ui.success("Current network added and local HTTPS certificate renewed.")
    for url in urls:
        ui.print(url)
    _show_trust_certificate(root, ui)
    if getattr(args, "no_restart", False):
        ui.warn("Restart TrinaxAI before opening the new address.")
        return 0
    rc = _system.run_service_action("reload-network", ui, timeout=180)
    if rc != 0 and platform.system() == "Linux" and shutil.which("systemctl") and shutil.which("sudo"):
        ui.info("Administrator approval is required once to restart the HTTPS services.")
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "ai-rag.service", "trinaxai-frontend.service"],
            check=False,
        )
        if result.returncode == 0:
            return 0
    if rc != 0:
        ui.warn("Configuration is ready. Restart the PWA and RAG services to activate it.")
    return rc


__all__ = ["run"]
