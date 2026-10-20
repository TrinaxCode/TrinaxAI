"""``trinaxai pair`` — create and revoke scoped LAN device credentials."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

# Mirrors app.security.device_auth.ELEVATED_DEVICE_SCOPES without importing the API.
_ELEVATED_SCOPES = ("index", "agent", "modify")


def _parse_scopes(raw: Any) -> list[str]:
    return [scope.strip() for scope in str(raw or "").split(",") if scope.strip()]


def _warn_if_elevated(ui: Any, scopes: list[str]) -> None:
    granted = [scope for scope in scopes if scope in _ELEVATED_SCOPES]
    if granted:
        ui.warn(f"Elevated permissions granted: {', '.join(granted)}. This device can change this host.")


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
    return f"{origin}/#/settings/advanced?pair={code}"


def run(args: Any, client: Any, ui: Any, _config: Any) -> int:
    action = getattr(args, "pair_command", None) or "start"
    try:
        if action == "start":
            scopes = _parse_scopes(getattr(args, "scopes", ""))
            result = client.start_pairing(
                scopes,
                ttl_seconds=int(getattr(args, "ttl", 300)),
                device_ttl_days=getattr(args, "device_ttl_days", None),
            )
            code = str(result.get("code") or "")
            ui.success(f"One-time pairing code: {code}")
            ui.info(f"Expires at Unix time {result.get('expires_at')}")
            ui.info(_pairing_url(client.base_url, code, getattr(args, "pwa_url", None)))
            _warn_if_elevated(ui, scopes)
            ui.warn("The code is single-use. Verify the device name after it connects.")
            return 0
        if action == "list":
            devices = client.list_paired_devices()
            if not devices:
                ui.info("No paired devices.")
                return 0
            ui.table(
                ["id", "name", "scopes", "status"],
                [
                    [
                        item.get("id", ""),
                        item.get("name", ""),
                        ",".join(item.get("scopes") or []),
                        "revoked" if item.get("revoked_at") is not None else "active",
                    ]
                    for item in devices
                ],
                title="Paired devices",
            )
            return 0
        if action == "set":
            scopes = _parse_scopes(getattr(args, "scopes", ""))
            device = client.set_paired_device_scopes(str(args.device_id), scopes)
            granted = ",".join(device.get("scopes") or scopes)
            ui.success(f"Updated {device.get('name') or device.get('id') or args.device_id}: {granted}.")
            _warn_if_elevated(ui, list(device.get("scopes") or scopes))
            return 0
        if action == "revoke":
            device = client.revoke_paired_device(str(args.device_id))
            ui.success(f"Revoked {device.get('name') or device.get('id') or args.device_id}.")
            return 0
        ui.error(f"Unknown pair action: {action}")
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI boundary renders API errors
        ui.failure(f"Pair {action}", exc)
        return 1


__all__ = ["run"]
