"""``trinaxai pair`` — create and revoke scoped LAN device credentials."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse


def _pairing_url(api_base: str, code: str, explicit: str | None) -> str:
    if explicit:
        origin = explicit.rstrip("/")
    else:
        parsed = urlparse(api_base)
        host = parsed.hostname or "localhost"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = f"{host}:3334"
        origin = urlunparse((parsed.scheme or "https", netloc, "", "", "", "")).rstrip("/")
    return f"{origin}/#settings?pair={code}"


def run(args: Any, client: Any, ui: Any, _config: Any) -> int:
    action = getattr(args, "pair_command", None) or "start"
    try:
        if action == "start":
            scopes = [scope.strip() for scope in str(getattr(args, "scopes", "")).split(",") if scope.strip()]
            result = client.start_pairing(
                scopes,
                ttl_seconds=int(getattr(args, "ttl", 300)),
                device_ttl_days=getattr(args, "device_ttl_days", None),
            )
            code = str(result.get("code") or "")
            ui.success(f"One-time pairing code: {code}")
            ui.info(f"Expires at Unix time {result.get('expires_at')}")
            ui.info(_pairing_url(client.base_url, code, getattr(args, "pwa_url", None)))
            ui.warn("The code is single-use. Verify the device name after it connects.")
            return 0
        if action == "list":
            devices = client.list_paired_devices()
            if not devices:
                ui.info("No paired devices.")
                return 0
            ui.table(
                ["id", "name", "scopes", "status"],
                [[
                    item.get("id", ""),
                    item.get("name", ""),
                    ",".join(item.get("scopes") or []),
                    "revoked" if item.get("revoked_at") is not None else "active",
                ] for item in devices],
                title="Paired devices",
            )
            return 0
        if action == "revoke":
            device = client.revoke_paired_device(str(args.device_id))
            ui.success(f"Revoked {device.get('name') or device.get('id') or args.device_id}.")
            return 0
        ui.error(f"Unknown pair action: {action}")
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI boundary renders API errors
        ui.error(f"pair {action}: {exc}")
        return 1


__all__ = ["run"]
