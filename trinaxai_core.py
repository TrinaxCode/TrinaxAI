"""Small pure helpers shared by backend, CLI and tests."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VALID_PROFILES = frozenset(
    {
        "8gb",
        "16gb",
        "32gb",
        "64gb",
    }
)

_GB = 1024**3
_DECIMAL_GB = 10**9


def normalize_profile(value: Any, *, fallback: str = "") -> str:
    """Return one canonical profile, migrating persisted legacy values once."""
    text = str(value or "").strip().lower()
    legacy = {
        bytes((109, 97, 120)).decode("ascii"): "32gb",
        bytes((117, 108, 116, 114, 97)).decode("ascii"): "64gb",
        bytes((108, 111, 119)).decode("ascii"): "8gb",
    }
    return legacy.get(text, text if text in VALID_PROFILES else fallback)


def migrate_profile_env(path: str | os.PathLike[str], *, fallback: str = "") -> bool:
    """Rewrite a legacy profile in a dotenv file and return whether it changed."""
    target = Path(path)
    try:
        original = target.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = original.splitlines(keepends=True)
    changed = False
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*TRINAXAI_PROFILE\s*=\s*)([^#\r\n]*)(.*)$", line)
        if not match:
            continue
        raw_field = match.group(2)
        raw = raw_field.strip().strip("\"'")
        migrated = normalize_profile(raw, fallback=fallback)
        if migrated and migrated != raw:
            leading = raw_field[: len(raw_field) - len(raw_field.lstrip())]
            trailing = raw_field[len(raw_field.rstrip()) :]
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = (
                f"{match.group(1)}{leading}{migrated}{trailing}{match.group(3).rstrip(chr(10) + chr(13))}{newline}"
            )
            changed = True
        break
    if not changed:
        return False
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text("".join(lines), encoding="utf-8")
        os.replace(temporary, target)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return False
    return True


def load_hardware_profile(path: str | os.PathLike[str], *, fallback: str = "") -> dict[str, Any] | None:
    """Load and migrate a persisted hardware profile without returning legacy data."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_profile = str(payload.get("profile") or "").strip().lower()
    profile = normalize_profile(raw_profile, fallback=fallback)
    hardware = payload.get("hardware")
    if not profile or not isinstance(hardware, dict):
        return None
    raw_detected = str(payload.get("detected_profile") or "").strip().lower()
    detected_profile = normalize_profile(raw_detected, fallback=select_profile(hardware))
    if profile != raw_profile or detected_profile != raw_detected:
        save_hardware_profile(path, hardware, profile)
    return {
        "profile": profile,
        "detected_profile": detected_profile,
        "hardware": hardware,
        "updated_at": payload.get("updated_at"),
    }


def _command_output(args: list[str], *, timeout: float = 1.5) -> str:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _parse_size(value: Any, *, default_unit: str = "bytes") -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    match = re.search(r"(-?[0-9]+(?:\.[0-9]+)?)\s*(b|bytes|kib|kb|mib|mb|gib|gb|tib|tb)?", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or default_unit).lower()
    multipliers = {
        "b": 1,
        "bytes": 1,
        "kib": 1024,
        "kb": 1000,
        "mib": 1024**2,
        "mb": 1000**2,
        "gib": 1024**3,
        "gb": 1000**3,
        "tib": 1024**4,
        "tb": 1000**4,
    }
    return max(0, int(number * multipliers.get(unit, 1)))


def _cpu_model() -> str:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
                if (
                    ":" in line
                    and line.lower().split(":", 1)[0].strip() in {"model name", "hardware"}
                    and line.split(":", 1)[1].strip()
                ):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    if sys.platform == "darwin":
        model = _command_output(["sysctl", "-n", "machdep.cpu.brand_string"])
        if model:
            return model
    if os.name == "nt":
        model = _command_output(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        )
        if model:
            return model
    return platform.processor() or platform.uname().processor or platform.machine() or "Unknown CPU"


def _cpu_cores() -> int:
    try:
        import psutil

        physical = psutil.cpu_count(logical=False)
        if physical:
            return max(1, int(physical))
    except (ImportError, AttributeError, OSError):
        pass
    if sys.platform == "darwin":
        raw = _command_output(["sysctl", "-n", "hw.physicalcpu"])
        if raw.isdigit():
            return max(1, int(raw))
    return max(1, int(os.cpu_count() or 1))


def _ram_bytes() -> int:
    try:
        import psutil

        total = int(psutil.virtual_memory().total)
        if total > 0:
            return total
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        pass
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii", errors="replace").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
        except (OSError, IndexError, ValueError):
            pass
    if sys.platform == "darwin":
        raw = _command_output(["sysctl", "-n", "hw.memsize"])
        if raw.isdigit():
            return int(raw)
    if os.name == "nt":
        try:
            import ctypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_uint32),
                    ("dwMemoryLoad", ctypes.c_uint32),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError, TypeError):
            pass
    return 0


def _gpu(vendor: str, name: str, vram_bytes: int | None, *, unified_memory: bool = False) -> dict[str, Any]:
    return {
        "vendor": vendor,
        "name": name.strip() or f"{vendor.title()} GPU",
        "vram_bytes": vram_bytes if vram_bytes and vram_bytes > 0 else None,
        "unified_memory": unified_memory,
    }


def _nvidia_gpus() -> list[dict[str, Any]]:
    output = _command_output(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        timeout=2.0,
    )
    gpus = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",", 1)]
        if not parts or not parts[0]:
            continue
        vram = _parse_size(parts[1], default_unit="mib") if len(parts) > 1 else None
        gpus.append(_gpu("nvidia", parts[0], vram))
    return gpus


def _windows_gpus() -> list[dict[str, Any]]:
    command = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    output = _command_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command])
    if not output:
        return []
    try:
        rows = json.loads(output)
    except (TypeError, ValueError):
        return []
    if isinstance(rows, dict):
        rows = [rows]
    gpus = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("Name"):
            continue
        name = str(row["Name"])
        lower = name.lower()
        vendor = "nvidia" if "nvidia" in lower else "amd" if any(x in lower for x in ("amd", "radeon")) else "other"
        vram = _parse_size(row.get("AdapterRAM"))
        if vram in {4_294_967_295, 18_446_744_073_709_551_615}:
            vram = None
        gpus.append(_gpu(vendor, name, vram))
    return gpus


def _mac_gpus(*, apple_silicon: bool, ram_bytes: int) -> list[dict[str, Any]]:
    output = _command_output(["system_profiler", "SPDisplaysDataType", "-json"], timeout=3.0)
    try:
        rows = json.loads(output).get("SPDisplaysDataType", [])
    except (AttributeError, TypeError, ValueError):
        rows = []
    if isinstance(rows, dict):
        rows = [rows]
    gpus = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("sppci_model") or row.get("_name") or "")
        vendor_text = str(row.get("spdisplays_vendor") or "").lower()
        vendor = "apple" if apple_silicon or "apple" in vendor_text or "apple" in name.lower() else "other"
        vram = None if vendor == "apple" else _parse_size(row.get("spdisplays_vram"))
        gpus.append(_gpu(vendor, name, vram, unified_memory=vendor == "apple"))
    if apple_silicon and not any(gpu["vendor"] == "apple" for gpu in gpus):
        gpus.append(_gpu("apple", "Apple Silicon GPU", None, unified_memory=True))
    return gpus


def _linux_gpus() -> list[dict[str, Any]]:
    vendor_names = {"0x10de": "nvidia", "0x1002": "amd", "0x8086": "other"}
    gpus = []
    for device in sorted(Path("/sys/class/drm").glob("card*/device")):
        try:
            vendor = vendor_names.get(device.joinpath("vendor").read_text().strip().lower())
        except OSError:
            continue
        if not vendor:
            continue
        name = ""
        for filename in ("product_name", "uevent"):
            try:
                text = device.joinpath(filename).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = re.search(r"(?:PRODUCT_NAME|PCI_ID|DRIVER)=([^\n]+)", text)
            if match:
                name = match.group(1).strip()
                break
        try:
            vram = int(device.joinpath("mem_info_vram_total").read_text().strip())
        except (OSError, ValueError):
            vram = None
        gpus.append(_gpu(vendor, name or f"{vendor.title()} GPU", vram))
    if not gpus:
        output = _command_output(["lspci", "-nn"], timeout=2.0)
        for line in output.splitlines():
            lower = line.lower()
            if not any(kind in lower for kind in ("vga compatible", "3d controller", "display controller")):
                continue
            vendor = (
                "nvidia"
                if "nvidia" in lower
                else "amd"
                if any(x in lower for x in ("amd", "ati", "radeon"))
                else "other"
            )
            gpus.append(_gpu(vendor, line.split(": ", 1)[-1], None))
    return gpus


def detect_hardware() -> dict[str, Any]:
    """Detect the hardware needed to tune local Ollama inference."""
    system = platform.system()
    machine = platform.machine().lower()
    ram_bytes = _ram_bytes()
    if system == "Darwin":
        gpus = _mac_gpus(apple_silicon=machine in {"arm64", "aarch64"}, ram_bytes=ram_bytes)
    elif system == "Windows":
        gpus = _nvidia_gpus() or _windows_gpus()
    else:
        gpus = _nvidia_gpus() or _linux_gpus()
    unique = []
    seen = set()
    for gpu in gpus:
        key = (gpu["vendor"], gpu["name"], gpu["vram_bytes"])
        if key not in seen:
            unique.append(gpu)
            seen.add(key)
    primary = max(
        (gpu for gpu in unique if gpu["vendor"] in {"nvidia", "amd", "apple"}),
        key=lambda gpu: gpu.get("vram_bytes") or (ram_bytes if gpu.get("unified_memory") else 0),
        default=None,
    )
    primary = primary or (unique[0] if unique else _gpu("none", "No dedicated GPU", None))
    return {
        "platform": system.lower() or sys.platform,
        "architecture": machine or "unknown",
        "cpu": {"model": _cpu_model(), "cores": _cpu_cores()},
        "ram": {"total_bytes": ram_bytes},
        "gpu": primary,
        "gpus": unique,
    }


def select_profile(hardware: dict[str, Any]) -> str:
    # Hardware vendors label RAM in decimal GB; using GiB would misclassify a
    # normal 16 GB machine as 8 GB because the OS reports roughly 14.9 GiB.
    ram_gb = float(hardware.get("ram", {}).get("total_bytes") or 0) / _DECIMAL_GB
    if ram_gb >= 64:
        profile = "64gb"
    elif ram_gb >= 32:
        profile = "32gb"
    elif ram_gb >= 16:
        profile = "16gb"
    else:
        profile = "8gb"
    vram_gb = _dedicated_vram_gb(hardware)
    if vram_gb >= 24:
        return "64gb"
    if vram_gb >= 12 and profile in {"8gb", "16gb"}:
        return "32gb"
    if vram_gb >= 8 and profile == "8gb":
        return "16gb"

    gpu = hardware.get("gpu") or {}
    gpus = hardware.get("gpus") or [gpu]
    cores = int((hardware.get("cpu") or {}).get("cores") or 0)
    has_usable_gpu = any(item.get("vendor") in {"nvidia", "amd", "apple"} for item in gpus if isinstance(item, dict))
    if not has_usable_gpu and cores:
        if cores < 4:
            return "8gb"
        if cores < 8 and profile in {"32gb", "64gb"}:
            return "16gb"
    return profile


def _dedicated_vram_gb(hardware: dict[str, Any]) -> float:
    gpus = hardware.get("gpus") or [hardware.get("gpu") or {}]
    return max(
        (
            float(gpu.get("vram_bytes") or 0) / _GB
            for gpu in gpus
            if gpu.get("vendor") in {"nvidia", "amd"} and not gpu.get("unified_memory")
        ),
        default=0.0,
    )


def model_recommendations(hardware: dict[str, Any], *, profile: str | None = None) -> dict[str, Any]:
    """Pick a known Ollama fleet within the selected hardware profile."""
    profile = normalize_profile(profile)
    profile = profile if profile in VALID_PROFILES else select_profile(hardware)
    gpu = hardware.get("gpu") or {}
    tier = {
        "8gb": "qwen3.5:2b",
        "16gb": "qwen3.5:4b",
        "32gb": "qwen3.5:9b",
        "64gb": "qwen3.5:35b",
    }[profile]
    reason = "El perfil activo limita el modelo al presupuesto de CPU, RAM y memoria de GPU disponible."
    fast = "qwen3.5:4b" if tier in {"qwen3.5:9b", "qwen3.5:35b"} else "qwen3.5:2b"
    code = "qwen3-coder:30b" if tier == "qwen3.5:35b" else tier
    return {
        "general": tier,
        "code": code,
        "deep": tier,
        "fast": fast,
        "reason": reason,
        "profile": profile,
        "gpu_vendor": gpu.get("vendor", "none"),
        "gpu_vram_bytes": gpu.get("vram_bytes"),
    }


def recommended_ollama_gpu_layers(hardware: dict[str, Any]) -> int:
    gpu = hardware.get("gpu") or {}
    dedicated = hardware.get("gpus") or [gpu]
    has_known_gpu = any(
        item.get("vendor") in {"nvidia", "amd"} and item.get("vram_bytes") is not None
        for item in dedicated
        if isinstance(item, dict)
    )
    has_unknown_gpu = any(
        item.get("vendor") in {"nvidia", "amd"} and item.get("vram_bytes") is None
        for item in dedicated
        if isinstance(item, dict)
    )
    if gpu.get("unified_memory") or has_unknown_gpu or has_known_gpu:
        return 999  # Ollama clamps this to all layers that fit on the device.
    return 0


def save_hardware_profile(path: str | os.PathLike[str], hardware: dict[str, Any], profile: str) -> None:
    """Persist the detected snapshot so Settings and diagnostics see one source of truth."""
    target = Path(path)
    canonical = normalize_profile(profile, fallback=select_profile(hardware))
    stable_payload = {
        "profile": canonical,
        "detected_profile": select_profile(hardware),
        "hardware": hardware,
    }
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        existing = None
    if isinstance(existing, dict) and all(existing.get(key) == value for key, value in stable_payload.items()):
        return
    payload = {**stable_payload, "updated_at": time.time()}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


def normalize_http_base_url(value: Any, fallback: str = "") -> str:
    """Return a normalized HTTP(S) base URL or the supplied safe fallback."""
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and not any(char.isspace() for char in parsed.netloc)
        )
        if valid:
            _ = parsed.port  # Validate malformed ports while parsing.
    except ValueError:
        valid = False
    return text.rstrip("/") if valid else str(fallback).rstrip("/")


def sanitize_collection_id(value: str | None, *, fallback: str = "collection") -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    return (slug or fallback)[:48]


def source_id_for_root(root: str, *, explicit_id: str | None = None) -> str:
    """Return the stable source id shared by indexer and backend deletion."""
    canonical_root = os.path.realpath(os.path.abspath(os.path.expanduser(root)))
    identity_path = os.path.normcase(canonical_root).replace("\\", "/")
    root_digest = hashlib.sha256(identity_path.encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
    basename = os.path.basename(canonical_root.rstrip(os.sep)) or "root"
    generated_id = f"{sanitize_collection_id(basename, fallback='root')[:24]}-{root_digest}"
    return sanitize_collection_id(explicit_id, fallback=generated_id) if explicit_id else generated_id


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        if sys.platform == "win32":
            try:
                os.kill(pid, 0)
            except PermissionError:
                return True
            except OSError:
                pass
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                process_query_limited_information,
                False,
                pid,
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                return True
            return False
        except (AttributeError, OSError):
            pass
    # ``os.kill(pid, 0)`` is portable and lets the OS report process state.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def exclusive_process_lock(
    path: str | os.PathLike[str],
    *,
    timeout: float = 3600.0,
    poll_interval: float = 0.25,
):
    """Portable inter-process lock based on atomic directory creation.

    The owner PID is recorded so locks left by a crashed indexer can be safely
    reclaimed. A directory is used instead of platform-specific flock APIs so
    the same index store behaves consistently on Linux, macOS, and Windows.
    """
    lock_dir = Path(path)
    owner_file = lock_dir / "owner.json"
    deadline = time.monotonic() + max(0.0, timeout)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            lock_dir.mkdir()
            owner_file.write_text(
                json.dumps({"pid": os.getpid(), "created_at": time.time()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            stale = False
            try:
                owner = json.loads(owner_file.read_text(encoding="utf-8"))
                stale = not _process_is_alive(int(owner.get("pid", 0)))
            except (OSError, ValueError, TypeError):
                try:
                    stale = time.time() - lock_dir.stat().st_mtime > 24 * 60 * 60
                except OSError:
                    stale = False
            if stale:
                claimed = lock_dir.with_name(f".{lock_dir.name}.stale-{uuid.uuid4().hex}")
                try:
                    os.replace(lock_dir, claimed)
                except OSError:
                    continue
                try:
                    shutil.rmtree(claimed)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for process lock: {lock_dir}") from None
            time.sleep(max(0.01, poll_interval))

    try:
        yield
    finally:
        try:
            owner = json.loads(owner_file.read_text(encoding="utf-8"))
            if int(owner.get("pid", -1)) == os.getpid():
                shutil.rmtree(lock_dir)
        except (OSError, ValueError, TypeError):
            pass


def _positive_int(value: Any, fallback: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _positive_float(value: Any, fallback: float, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed
