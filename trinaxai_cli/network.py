"""Local-network discovery and HTTPS refresh helpers."""

from __future__ import annotations

import ipaddress
import os
import platform
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


def lan_addresses() -> list[str]:
    """Return private, non-loopback addresses for this host."""
    resolved: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_DGRAM):
            resolved.add(str(item[4][0]).split("%", 1)[0])
    except OSError:
        pass
    routed: set[str] = set()
    for family, target in ((socket.AF_INET, ("192.0.2.1", 9)), (socket.AF_INET6, ("2001:db8::1", 9))):
        try:
            with socket.socket(family, socket.SOCK_DGRAM) as probe:
                probe.connect(target)
                routed.add(str(probe.getsockname()[0]).split("%", 1)[0])
        except OSError:
            pass

    def usable(value: str) -> bool:
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError:
            return False
        return parsed.is_private and not parsed.is_loopback and not parsed.is_link_local

    candidates = routed or resolved
    return sorted(filter(usable, candidates), key=lambda item: (":" in item, item))


def local_hostname() -> str:
    hostname = socket.gethostname().strip().rstrip(".") or "trinaxai"
    return hostname.split(".", 1)[0]


def pwa_urls(addresses: list[str] | None = None, *, port: int = 3334) -> list[str]:
    addresses = lan_addresses() if addresses is None else addresses
    hostname = local_hostname()
    hosts = [*addresses, f"{hostname}.local"]
    return [f"https://{f'[{host}]' if ':' in host else host}:{port}" for host in hosts]


def cors_origins(addresses: list[str] | None = None) -> str:
    addresses = lan_addresses() if addresses is None else addresses
    hosts = ["localhost", "127.0.0.1", "::1", local_hostname(), f"{local_hostname()}.local", *addresses]
    origins: list[str] = []
    for host in hosts:
        rendered = f"[{host}]" if ":" in host else host
        for scheme in ("https", "http"):
            for port in (3334, 3335):
                origin = f"{scheme}://{rendered}:{port}"
                if origin not in origins:
                    origins.append(origin)
    return ",".join(origins)


def trust_certificate(root: Path) -> tuple[Path, str] | None:
    """Return the public certificate a LAN device must trust, if available."""
    mkcert = shutil.which("mkcert")
    if mkcert:
        try:
            result = subprocess.run(
                [mkcert, "-CAROOT"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result and result.returncode == 0:
            ca_file = Path(getattr(result, "stdout", "").strip()) / "rootCA.pem"
            if ca_file.is_file():
                return ca_file, "mkcert"

    certificate = root / "chat-pwa" / "certs" / "trinaxai-local.crt"
    if certificate.is_file():
        return certificate, "self-signed"
    return None


def update_env(root: Path, addresses: list[str]) -> None:
    path = root / ".env"
    if not path.is_file():
        raise FileNotFoundError(f"Missing TrinaxAI environment file: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    replacement = f"TRINAXAI_CORS_ORIGINS={cors_origins(addresses)}"
    updated = False
    for index, raw in enumerate(lines):
        if raw.startswith("TRINAXAI_CORS_ORIGINS="):
            lines[index] = replacement
            updated = True
            break
    if not updated:
        lines.append(replacement)
    temporary = path.with_suffix(".env.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(temporary, path.stat().st_mode & 0o777)
    os.replace(temporary, path)


def refresh_certificate(root: Path, addresses: list[str]) -> None:
    cert_dir = root / "chat-pwa" / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    names = ["localhost", local_hostname(), f"{local_hostname()}.local", "127.0.0.1", "::1", *addresses]
    names = list(dict.fromkeys(names))
    mkcert = shutil.which("mkcert")
    openssl = shutil.which("openssl")
    if not mkcert and not openssl:
        raise RuntimeError("mkcert or OpenSSL is required to refresh local HTTPS")

    with tempfile.TemporaryDirectory(dir=cert_dir) as temporary:
        temp_dir = Path(temporary)
        cert = temp_dir / "localhost.pem"
        key = temp_dir / "localhost-key.pem"
        if mkcert:
            command = [mkcert, "-cert-file", str(cert), "-key-file", str(key), *names]
        else:
            san = ",".join(f"IP:{name}" if _is_ip(name) else f"DNS:{name}" for name in names)
            command = [
                openssl or "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-sha256",
                "-days",
                "1825",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-subj",
                "/CN=TrinaxAI Local HTTPS",
                "-addext",
                f"subjectAltName={san}",
            ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "certificate generation failed").strip())

        pfx: Path | None = None
        if platform.system() == "Windows" and openssl:
            pfx = temp_dir / "trinaxai-local.pfx"
            result = subprocess.run(
                [
                    openssl,
                    "pkcs12",
                    "-export",
                    "-out",
                    str(pfx),
                    "-inkey",
                    str(key),
                    "-in",
                    str(cert),
                    "-passout",
                    "pass:trinaxai-local",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError((result.stderr or "PFX generation failed").strip())

        os.chmod(key, 0o600)
        os.chmod(cert, 0o644)
        os.replace(key, cert_dir / "localhost-key.pem")
        os.replace(cert, cert_dir / "localhost.pem")
        shutil.copy2(cert_dir / "localhost.pem", cert_dir / "trinaxai-local.crt")
        if pfx:
            os.replace(pfx, cert_dir / "trinaxai-local.pfx")
        elif platform.system() == "Windows":
            (cert_dir / "trinaxai-local.pfx").unlink(missing_ok=True)


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
