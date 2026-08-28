#!/usr/bin/env python3
"""Small native manager for installing, updating, and uninstalling TrinaxAI."""

from __future__ import annotations

import argparse
import hashlib
import locale
import math
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from tkinter import (
    BOTH,
    DISABLED,
    LEFT,
    NORMAL,
    Button,
    Canvas,
    Frame,
    Label,
    PhotoImage,
    StringVar,
    Tk,
    messagebox,
    ttk,
)
from urllib.parse import urlsplit

RELEASE_VERSION = "1.2.0"
ARCHIVE_NAME = f"TrinaxAI-{RELEASE_VERSION}.tar.gz"
ARCHIVE_URL = f"https://github.com/TrinaxCode/TrinaxAI/releases/download/v{RELEASE_VERSION}/{ARCHIVE_NAME}"
CHECKSUM_URL = f"https://github.com/TrinaxCode/TrinaxAI/releases/download/v{RELEASE_VERSION}/SHA256SUMS"
DOWNLOAD_TIMEOUT = 30
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
LOGO_RESOURCE = Path("branding/android-chrome-512x512.png")
COLORS = {
    "background": "#020406",
    "panel": "#09141f",
    "panel_alt": "#0d1d2b",
    "border": "#17344a",
    "text": "#f5f9fc",
    "muted": "#8ea5b8",
    "blue": "#168de2",
    "blue_dark": "#006bbd",
    "success": "#4be0a3",
    "danger": "#ff8394",
}
TEXT = {
    "en": {
        "title": "TrinaxAI Manager",
        "tagline": "Private AI, ready in minutes.",
        "eyebrow": "DESKTOP INSTALLER",
        "headline": "Your local AI starts here.",
        "ready": "TrinaxAI is installed and ready.",
        "missing": "TrinaxAI is not installed yet.",
        "ready_detail": "Everything is ready. Open the chat at https://localhost:3334.",
        "missing_detail": "The Manager will download the verified release and guide the setup.",
        "location": "Installation folder",
        "actions": "Choose an action",
        "version": f"v{RELEASE_VERSION}",
        "privacy": "Local-first  •  No Git required  •  Your data stays yours",
        "install": "Install",
        "update": "Update",
        "uninstall": "Uninstall",
        "intro": "Everything is configured automatically. You do not need Git or terminal commands.",
        "installing": "Downloading and installing TrinaxAI…",
        "updating": "Updating TrinaxAI…",
        "uninstalling": "Uninstalling TrinaxAI…",
        "launched": "The process is running automatically. Keep the system window open; it may ask for your password.",
        "completed": "Finished. You can close this window or open TrinaxAI.",
        "busy_detail": "A system progress window is open. Keep it open until the process finishes.",
        "confirm": "Uninstall TrinaxAI? Your indexes, personal files, and Ollama models will be kept.",
        "error": "We could not start the process. Check your internet connection and try again.\n\nDetails: {error}",
        "terminal": "We could not open the system progress window. Open your system's Terminal application once and try again.",
    },
    "es": {
        "title": "Gestor de TrinaxAI",
        "tagline": "IA privada, lista en minutos.",
        "eyebrow": "INSTALADOR DE ESCRITORIO",
        "headline": "Tu IA local empieza aquí.",
        "ready": "TrinaxAI está instalado y listo.",
        "missing": "TrinaxAI todavía no está instalado.",
        "ready_detail": "Todo está listo. Abre el chat en https://localhost:3334.",
        "missing_detail": "El Gestor descargará el release verificado y guiará la configuración.",
        "location": "Carpeta de instalación",
        "actions": "Elige una acción",
        "version": f"v{RELEASE_VERSION}",
        "privacy": "Local-first  •  Sin Git  •  Tus datos siguen siendo tuyos",
        "install": "Instalar",
        "update": "Actualizar",
        "uninstall": "Desinstalar",
        "intro": "Todo se configura automáticamente. No necesitas Git ni escribir comandos.",
        "installing": "Descargando e instalando TrinaxAI…",
        "updating": "Actualizando TrinaxAI…",
        "uninstalling": "Desinstalando TrinaxAI…",
        "launched": "El proceso continúa automáticamente. Mantén abierta la ventana del sistema; puede pedir tu contraseña.",
        "completed": "Listo. Puedes cerrar esta ventana o abrir TrinaxAI.",
        "busy_detail": "Hay una ventana de progreso del sistema abierta. Déjala abierta hasta terminar.",
        "confirm": "¿Desinstalar TrinaxAI? Se conservarán tus índices, archivos personales y modelos de Ollama.",
        "error": "No pudimos iniciar el proceso. Comprueba tu conexión a Internet e inténtalo de nuevo.\n\nDetalles: {error}",
        "terminal": "No pudimos abrir la ventana de progreso del sistema. Abre una vez la aplicación Terminal de tu sistema e inténtalo de nuevo.",
    },
}


def language() -> str:
    values = [os.environ.get(name, "") for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")]
    values.append(locale.getlocale()[0] or "")
    return "es" if any(value.lower().startswith("es") for value in values if value) else "en"


def install_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "TrinaxAI"
    if system == "Darwin":
        return Path.home() / "Library/Application Support/TrinaxAI"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "trinaxai"


def is_installed(root: Path) -> bool:
    return root.is_dir() and not root.is_symlink() and (root / "pyproject.toml").is_file()


def logo_path() -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / LOGO_RESOURCE
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parent / "chat-pwa" / "public" / "android-chrome-512x512.png"


def _validate_archive(bundle: zipfile.ZipFile) -> str:
    roots: set[str] = set()
    seen: set[str] = set()
    total_size = 0
    for member in bundle.infolist():
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if (
            not name
            or not path.parts
            or "\x00" in name
            or path.is_absolute()
            or any(part == ".." for part in path.parts)
        ):
            raise RuntimeError("The downloaded package contains an unsafe path.")
        if len(name) > 1 and name[1] == ":" and name[0].isalpha():
            raise RuntimeError("The downloaded package contains an unsafe path.")
        if stat.S_ISLNK((member.external_attr >> 16) & 0o177777):
            raise RuntimeError("The downloaded package contains an unsafe link.")
        size = 0 if member.is_dir() else int(member.file_size)
        if size < 0 or size > MAX_MEMBER_BYTES or total_size + size > MAX_TOTAL_BYTES:
            raise RuntimeError("The downloaded package is too large.")
        total_size += size
        normalized = path.as_posix().rstrip("/")
        if normalized in seen:
            raise RuntimeError("The downloaded package contains duplicate entries.")
        seen.add(normalized)
        roots.add(path.parts[0])

    if len(roots) != 1:
        raise RuntimeError("The downloaded package must contain one source folder.")
    root = next(iter(roots))
    if not root.startswith("TrinaxAI-"):
        raise RuntimeError("The downloaded package has an unexpected root folder.")
    return root


def _validate_tar_archive(bundle: tarfile.TarFile) -> str:
    roots: set[str] = set()
    seen: set[str] = set()
    total_size = 0
    for member in bundle.getmembers():
        name = member.name.replace("\\", "/")
        path = PurePosixPath(name)
        if (
            not name
            or not path.parts
            or "\x00" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise RuntimeError("The downloaded package contains an unsafe path.")
        normalized = path.as_posix().rstrip("/")
        if normalized in seen:
            raise RuntimeError("The downloaded package contains duplicate entries.")
        seen.add(normalized)
        if not (member.isdir() or member.isreg()):
            raise RuntimeError("The downloaded package contains an unsafe link or file type.")
        size = 0 if member.isdir() else int(member.size)
        if size < 0 or size > MAX_MEMBER_BYTES or total_size + size > MAX_TOTAL_BYTES:
            raise RuntimeError("The downloaded package is too large.")
        total_size += size
        roots.add(path.parts[0])
    if len(roots) != 1:
        raise RuntimeError("The downloaded package must contain one source folder.")
    root = next(iter(roots))
    if not root.startswith("TrinaxAI-"):
        raise RuntimeError("The downloaded package has an unexpected root folder.")
    return root


def _release_checksum() -> str:
    try:
        # CHECKSUM_URL is the fixed official HTTPS release manifest.
        with urllib.request.urlopen(  # nosec B310
            CHECKSUM_URL, timeout=DOWNLOAD_TIMEOUT
        ) as response:
            payload = response.read(1024 * 1024 + 1)
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
        raise RuntimeError(f"The release checksum manifest could not be downloaded: {error}") from error
    if len(payload) > 1024 * 1024:
        raise RuntimeError("The release checksum manifest is too large.")
    text = payload.decode("utf-8", errors="strict")
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1].lstrip("*") == ARCHIVE_NAME:
            digest = fields[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                return digest
    raise RuntimeError(f"The release checksum manifest has no valid entry for {ARCHIVE_NAME}.")


def _extract_archive(archive: Path, destination: Path) -> str:
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            root = _validate_archive(bundle)
            for member in bundle.infolist():
                target = destination.joinpath(*PurePosixPath(member.filename.replace("\\", "/")).parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output)
                mode = (member.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(target, mode)
            return root
    try:
        with tarfile.open(archive, mode="r:*") as bundle:
            root = _validate_tar_archive(bundle)
            for member in bundle.getmembers():
                target = destination.joinpath(*PurePosixPath(member.name.replace("\\", "/")).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                stream = bundle.extractfile(member)
                if stream is None:
                    raise RuntimeError("The downloaded package contains an unreadable file.")
                target.parent.mkdir(parents=True, exist_ok=True)
                with stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output)
            return root
    except tarfile.TarError as error:
        raise RuntimeError("The downloaded package is not a valid archive.") from error


def _download_archive(archive: Path) -> None:
    scheme = urlsplit(ARCHIVE_URL).scheme.lower()
    if scheme not in {"https", "file"}:
        raise RuntimeError("The download URL must use HTTPS.")
    try:
        # ARCHIVE_URL is restricted to HTTPS in production; file URLs are test-only.
        with (
            urllib.request.urlopen(  # nosec B310
                ARCHIVE_URL, timeout=DOWNLOAD_TIMEOUT
            ) as response,
            archive.open("wb") as output,
        ):
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("The downloaded package is too large.")
                output.write(chunk)
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
        raise RuntimeError(f"The TrinaxAI download failed: {error}") from error
    if archive.stat().st_size == 0:
        raise RuntimeError("The TrinaxAI download was empty.")
    if not zipfile.is_zipfile(archive) and not tarfile.is_tarfile(archive):
        raise RuntimeError("The downloaded package is not a valid ZIP or TAR archive.")
    if f"https://github.com/TrinaxCode/TrinaxAI/releases/download/v{RELEASE_VERSION}/{ARCHIVE_NAME}" == ARCHIVE_URL:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != _release_checksum():
            raise RuntimeError("The downloaded package failed SHA-256 verification.")


def download_source(target: Path) -> None:
    target = Path(target)
    if is_installed(target):
        return
    if target.is_symlink():
        raise RuntimeError(f"The installation folder must not be a symbolic link: {target}")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError(f"The installation folder is already in use: {target}")
    with tempfile.TemporaryDirectory(prefix="trinaxai-manager-") as temporary:
        temp = Path(temporary)
        archive = temp / ARCHIVE_NAME
        _download_archive(archive)
        try:
            destination = (temp / "source").resolve()
            root_name = _extract_archive(archive, destination)
        except zipfile.BadZipFile as error:
            raise RuntimeError("The downloaded package is not a valid archive.") from error
        except OSError as error:
            raise RuntimeError(f"The downloaded package could not be extracted: {error}") from error

        candidate = destination / root_name
        required_script = "install.ps1" if platform.system() == "Windows" else "install.sh"
        if (
            not candidate.is_dir()
            or candidate.is_symlink()
            or not (candidate / "pyproject.toml").is_file()
            or (candidate / "pyproject.toml").is_symlink()
            or not (candidate / required_script).is_file()
            or (candidate / required_script).is_symlink()
        ):
            raise RuntimeError("The downloaded package is invalid.")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            try:
                target.rmdir()
            except OSError as error:
                raise RuntimeError(f"The installation folder is already in use: {target}") from error
        shutil.move(str(candidate), str(target))
        (target / ".trinaxai-managed").write_text("Managed by TrinaxAI Manager.\n", encoding="utf-8")


def launch_terminal(root: Path, action: str, lang: str) -> subprocess.Popen:
    if action not in {"install", "update", "uninstall"}:
        raise ValueError(f"Unsupported lifecycle action: {action}")
    if lang not in TEXT:
        raise ValueError(f"Unsupported language: {lang}")
    root = Path(root).expanduser().resolve()
    system = platform.system()
    if system == "Windows":
        script = (root / f"{action}.ps1").resolve()
        if root not in script.parents:
            raise RuntimeError("The lifecycle script is outside the installation folder.")
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        args += ["-NonInteractive", "-Language", lang]
        if action == "update":
            args += ["-Restart"]
        elif action == "uninstall":
            args += ["-Yes", "-RemoveApp"]
        return subprocess.Popen(args, cwd=root, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))

    script = (root / f"{action}.sh").resolve()
    if root not in script.parents:
        raise RuntimeError("The lifecycle script is outside the installation folder.")
    args = ["--non-interactive"]
    if action == "update":
        args.append("--restart")
    elif action == "uninstall":
        args += ["--yes", "--remove-app"]
    command_args = " ".join(shlex.quote(value) for value in ["bash", str(script), *args])
    command = (
        f"TRINAXAI_LANG={shlex.quote(lang)} {command_args}; status=$?; "
        "printf '\\nPress Enter to close / Pulsa Enter para cerrar'; read -r; exit \"$status\""
    )
    if system == "Darwin":
        apple_command = command.replace("\\", "\\\\").replace('"', '\\"')
        return subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "{apple_command}"'],
            cwd=root,
        )
    terminals = (
        ("x-terminal-emulator", ["-e", "bash", "-lc", command]),
        ("gnome-terminal", ["--", "bash", "-lc", command]),
        ("konsole", ["-e", "bash", "-lc", command]),
        ("xterm", ["-e", "bash", "-lc", command]),
    )
    for executable, args in terminals:
        if shutil.which(executable):
            return subprocess.Popen([executable, *args], cwd=root)
    raise RuntimeError(TEXT[lang]["terminal"])


class Manager:
    def __init__(self) -> None:
        self.lang = language()
        self.text = TEXT[self.lang]
        self.root = install_dir()
        self._action_lock = threading.Lock()
        self._busy = False
        self.window = Tk()
        self.window.title(self.text["title"])
        self.window.geometry("620x700")
        self.window.resizable(False, False)
        self.window.configure(bg=COLORS["background"])
        self.status = StringVar()
        self.status_detail = StringVar()
        self._build_ui()
        self.refresh()

    def _draw_background(self, _event=None) -> None:
        width = max(620, self.background.winfo_width())
        height = max(700, self.background.winfo_height())
        self.background.delete("background")
        bands = ("#020406", "#03080d", "#040b12", "#05101a", "#061522", "#071a2a")
        band_height = max(1, math.ceil(height / len(bands)))
        for index, color in enumerate(bands):
            top = index * band_height
            self.background.create_rectangle(
                0, top, width, top + band_height + 1, fill=color, outline="", tags="background"
            )
        for inset, color in ((0, "#061b2d"), (22, "#08213a"), (44, "#0a2947"), (66, "#0c3154")):
            self.background.create_oval(
                width - 260 + inset,
                -170 + inset,
                width + 170 - inset,
                250 - inset,
                fill=color,
                outline="",
                tags="background",
            )
        for layer, color in enumerate(("#0a2c48", "#0b3556", "#0d3d62")):
            points = []
            for x in range(-30, width + 50, 18):
                y = height * (0.80 + layer * 0.035) + math.sin(x * 0.012 + layer) * 18 + math.cos(x * 0.006) * 9
                points.extend((x, y))
            points.extend((width + 40, height + 10, -30, height + 10))
            self.background.create_polygon(*points, fill=color, outline="", tags="background")
        self.background.create_line(34, 196, width - 34, 196, fill="#0b2639", width=1, tags="background")
        self.background.create_line(34, 516, width - 34, 516, fill="#0b2639", width=1, tags="background")
        self.background.tag_lower("background")

    def _build_ui(self) -> None:
        self.background = Canvas(
            self.window,
            background=COLORS["background"],
            borderwidth=0,
            highlightthickness=0,
        )
        self.background.pack(fill=BOTH, expand=True)
        self.background.bind("<Configure>", self._draw_background)
        self._draw_background()

        header = Frame(self.background, bg=COLORS["background"])
        self.background.create_window(34, 28, anchor="nw", window=header, width=552, height=58)
        logo = Canvas(header, width=46, height=46, bg=COLORS["background"], highlightthickness=0)
        try:
            self.logo_image = PhotoImage(file=str(logo_path())).subsample(8, 8)
            logo.create_image(23, 23, image=self.logo_image)
        except Exception:
            self.logo_image = None
            logo.create_text(23, 23, text="AI", fill=COLORS["blue"], font=("TkDefaultFont", 10, "bold"))
        logo.pack(side=LEFT, padx=(0, 12))
        brand = Frame(header, bg=COLORS["background"])
        brand.pack(side=LEFT, anchor="w")
        Label(
            brand, text="TrinaxAI", fg=COLORS["text"], bg=COLORS["background"], font=("TkDefaultFont", 19, "bold")
        ).pack(anchor="w")
        Label(
            brand, text=self.text["tagline"], fg=COLORS["muted"], bg=COLORS["background"], font=("TkDefaultFont", 9)
        ).pack(anchor="w")
        Label(
            header,
            text=self.text["version"],
            fg=COLORS["blue"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side="right", anchor="center")

        hero = Frame(self.background, bg=COLORS["background"])
        self.background.create_window(34, 106, anchor="nw", window=hero, width=552, height=86)
        Label(
            hero,
            text=self.text["eyebrow"],
            fg=COLORS["blue"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 9, "bold"),
        ).pack(anchor="w")
        Label(
            hero,
            text=self.text["headline"],
            fg=COLORS["text"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 22, "bold"),
        ).pack(anchor="w", pady=(4, 5))
        Label(
            hero, text=self.text["intro"], fg=COLORS["muted"], bg=COLORS["background"], font=("TkDefaultFont", 10)
        ).pack(anchor="w")

        status_area = Frame(self.background, bg=COLORS["background"])
        self.background.create_window(34, 210, anchor="nw", window=status_area, width=552, height=96)
        self.status_dot = Canvas(status_area, width=14, height=14, bg=COLORS["background"], highlightthickness=0)
        self.status_dot.pack(side=LEFT, padx=(0, 12), pady=(1, 0), anchor="n")
        self.status_dot.create_oval(2, 2, 12, 12, fill=COLORS["blue"], outline="")
        status_info = Frame(status_area, bg=COLORS["background"])
        status_info.pack(side=LEFT, fill="both", expand=True)
        Label(
            status_info,
            textvariable=self.status,
            fg=COLORS["text"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w")
        Label(
            status_info,
            textvariable=self.status_detail,
            fg=COLORS["muted"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 9),
            wraplength=430,
            justify=LEFT,
        ).pack(anchor="w", pady=(4, 0))
        self.location_label = Label(status_info, fg=COLORS["blue"], bg=COLORS["background"], font=("TkDefaultFont", 8))
        self.location_label.pack(anchor="w", pady=(7, 0))

        actions = Frame(self.background, bg=COLORS["background"])
        self.background.create_window(34, 324, anchor="nw", window=actions, width=552, height=176)
        Label(
            actions,
            text=self.text["actions"],
            fg=COLORS["muted"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 9, "bold"),
        ).pack(anchor="w")
        buttons = Frame(actions, bg=COLORS["background"])
        buttons.pack(fill="x", pady=(13, 14))
        button_options = {
            "font": ("TkDefaultFont", 10, "bold"),
            "relief": "flat",
            "borderwidth": 0,
            "padx": 12,
            "pady": 10,
            "takefocus": True,
            "cursor": "hand2",
            "highlightthickness": 2,
            "highlightbackground": COLORS["background"],
            "highlightcolor": COLORS["blue"],
        }
        self.install_button = Button(
            buttons,
            text=self.text["install"],
            command=self.install,
            bg=COLORS["blue"],
            fg=COLORS["text"],
            activebackground="#2aa0ef",
            activeforeground=COLORS["text"],
            **button_options,
        )
        self.update_button = Button(
            buttons,
            text=self.text["update"],
            command=lambda: self.run("update"),
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"],
            **button_options,
        )
        self.uninstall_button = Button(
            buttons,
            text=self.text["uninstall"],
            command=self.uninstall,
            bg=COLORS["panel_alt"],
            fg=COLORS["danger"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["danger"],
            **button_options,
        )
        for button in (self.install_button, self.update_button, self.uninstall_button):
            button.pack(side=LEFT, expand=True, fill="x", padx=4)
        Label(
            actions,
            text=self.text["launched"],
            fg=COLORS["muted"],
            bg=COLORS["background"],
            font=("TkDefaultFont", 8),
            wraplength=500,
            justify=LEFT,
        ).pack(anchor="w")

        progress_style = ttk.Style(self.window)
        try:
            progress_style.theme_use("clam")
        except Exception:
            pass
        progress_style.configure(
            "Trinax.Horizontal.TProgressbar",
            background=COLORS["blue"],
            troughcolor=COLORS["panel_alt"],
            bordercolor=COLORS["panel"],
            lightcolor=COLORS["blue"],
            darkcolor=COLORS["blue"],
        )
        self.progress = ttk.Progressbar(
            self.background, mode="indeterminate", style="Trinax.Horizontal.TProgressbar", length=552
        )
        self.background.create_window(34, 526, anchor="nw", window=self.progress, width=552, height=8)
        footer = Frame(self.background, bg=COLORS["background"])
        self.background.create_window(34, 620, anchor="nw", window=footer, width=552, height=34)
        Label(
            footer, text=self.text["privacy"], fg=COLORS["muted"], bg=COLORS["background"], font=("TkDefaultFont", 8)
        ).pack(anchor="w")

    def _set_status(self, title: str, detail: str | None = None) -> None:
        self.status.set(title)
        if detail is not None and hasattr(self, "status_detail"):
            self.status_detail.set(detail)

    def _short_path(self) -> str:
        value = str(self.root)
        return value if len(value) <= 76 else f"…{value[-75:]}"

    def refresh(self) -> None:
        installed = is_installed(self.root)
        with self._action_lock:
            busy = self._busy
        if not busy:
            self._set_status(
                self.text["ready"] if installed else self.text["missing"],
                self.text["ready_detail"] if installed else self.text["missing_detail"],
            )
            if hasattr(self, "status_dot"):
                self.status_dot.itemconfig(1, fill=COLORS["success"] if installed else COLORS["blue"])
            if hasattr(self, "location_label"):
                self.location_label.config(text=f"{self.text['location']}: {self._short_path()}")
        self.install_button.config(state=DISABLED if busy or installed else NORMAL)
        self.update_button.config(state=DISABLED if busy or not installed else NORMAL)
        self.uninstall_button.config(state=DISABLED if busy or not installed else NORMAL)

    def set_busy(self, busy: bool) -> None:
        with self._action_lock:
            self._busy = busy
        for button in (self.install_button, self.update_button, self.uninstall_button):
            button.config(state=DISABLED if busy else NORMAL)
        if hasattr(self, "progress"):
            if busy:
                self.progress.start(12)
            else:
                self.progress.stop()
        if not busy:
            self.refresh()

    def _start_action(self, action: str, worker) -> bool:
        if action not in {"install", "update", "uninstall"}:
            raise ValueError(f"Unsupported lifecycle action: {action}")
        with self._action_lock:
            if self._busy:
                return False
            self._busy = True
        self.set_busy(True)
        self._set_status(
            self.text[{"install": "installing", "update": "updating", "uninstall": "uninstalling"}[action]],
            self.text["busy_detail"],
        )
        threading.Thread(target=worker, daemon=True).start()
        return True

    def install(self) -> bool:
        return self._start_action("install", self._install)

    def _install(self) -> None:
        self._execute("install")

    def _execute(self, action: str) -> None:
        launched = False
        error = None
        try:
            if action == "install":
                download_source(self.root)
            elif not is_installed(self.root):
                raise RuntimeError("TrinaxAI is not installed.")
            process = launch_terminal(self.root, action, self.lang)
            launched = True
            self.window.after(0, lambda: self._set_status(self.text["launched"], self.text["busy_detail"]))
            if process is not None:
                return_code = process.wait()
                if isinstance(return_code, int) and return_code != 0:
                    raise RuntimeError(f"The {action} process exited with code {return_code}.")
        except Exception as caught:
            error = caught
        self.window.after(0, lambda: self._action_finished(action, launched, error))

    def _action_finished(self, action: str, launched: bool, error=None) -> None:
        self.set_busy(False)
        if error is not None:
            message = self.text["error"].format(error=error)
            messagebox.showerror(self.text["title"], message)
        elif launched:
            self._set_status(self.text["launched"], self.text["completed"])

    def run(self, action: str) -> bool:
        return self._start_action(action, lambda: self._execute(action))

    def uninstall(self) -> bool:
        with self._action_lock:
            if self._busy:
                return False
        if messagebox.askyesno(self.text["title"], self.text["confirm"]):
            return self.run("uninstall")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install, update, and uninstall TrinaxAI.")
    parser.add_argument("--version", action="version", version=f"TrinaxAI Manager {RELEASE_VERSION}")
    parser.parse_args(argv)
    Manager().window.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
