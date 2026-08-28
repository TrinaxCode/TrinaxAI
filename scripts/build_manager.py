#!/usr/bin/env python3
"""Build and package the native TrinaxAI Manager for its host platform."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "TrinaxAI-Manager"
LOGO_DEST = "branding"
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "manager"


def project_version() -> str:
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"$', manifest, re.MULTILINE)
    if not match:
        raise RuntimeError("The project version is missing from pyproject.toml")
    return match.group(1)


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def pyinstaller_command() -> list[str]:
    executable = shutil.which("pyinstaller")
    return [executable] if executable else [sys.executable, "-m", "PyInstaller"]


def manager_binary() -> Path:
    system = platform.system()
    if system == "Windows":
        return DIST / f"{NAME}.exe"
    if system == "Darwin":
        return DIST / f"{NAME}.app"
    return DIST / NAME


def build() -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    icon = ROOT / "chat-pwa" / "public" / "favicon.ico"
    logo = ROOT / "chat-pwa" / "public" / "android-chrome-512x512.png"
    icon_args = ["--icon", str(icon)] if platform.system() == "Windows" and icon.is_file() else []
    data_args = ["--add-data", f"{logo}{os.pathsep}{LOGO_DEST}"] if logo.is_file() else []
    run(
        pyinstaller_command()
        + [
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            NAME,
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD / "work"),
            "--specpath",
            str(BUILD),
            *icon_args,
            *data_args,
            str(ROOT / "trinaxai_manager.py"),
        ]
    )
    binary = manager_binary()
    valid_output = binary.is_dir() if platform.system() == "Darwin" else binary.is_file()
    if not valid_output:
        raise RuntimeError(f"PyInstaller did not produce {binary}")
    return binary


def _zip_file(source: Path, target: Path, arcname: str) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(source, arcname)


def _package_linux(binary: Path, output: Path, version: str) -> None:
    tarball = output / f"{NAME}-Linux.tar.gz"
    with tarfile.open(tarball, "w:gz") as bundle:
        bundle.add(binary, arcname=NAME)

    architecture = subprocess.run(
        ["dpkg", "--print-architecture"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if not architecture:
        raise RuntimeError("dpkg did not report a package architecture")
    deb = output / f"{NAME}-Linux.deb"
    with tempfile.TemporaryDirectory(prefix="trinaxai-manager-deb-") as temporary:
        package = Path(temporary)
        control = package / "DEBIAN"
        payload = package / "usr" / "lib" / "trinaxai-manager"
        applications = package / "usr" / "share" / "applications"
        icons = package / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
        control.mkdir(parents=True)
        payload.mkdir(parents=True)
        applications.mkdir(parents=True)
        icons.mkdir(parents=True)
        (control / "control").write_text(
            "\n".join(
                (
                    "Package: trinaxai-manager",
                    f"Version: {version}",
                    "Section: utils",
                    "Priority: optional",
                    f"Architecture: {architecture}",
                    "Maintainer: TrinaxCode <hello@trinaxai.app>",
                    "Description: TrinaxAI graphical installer",
                    " Install, update, and remove TrinaxAI without a terminal.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        installed_binary = payload / NAME
        shutil.copy2(binary, installed_binary)
        installed_binary.chmod(0o755)
        shutil.copy2(ROOT / "chat-pwa" / "public" / "android-chrome-512x512.png", icons / "trinaxai-manager.png")
        launcher = package / "usr" / "bin"
        launcher.mkdir(parents=True)
        os.symlink(f"../lib/trinaxai-manager/{NAME}", launcher / "trinaxai-manager")
        (applications / "trinaxai-manager.desktop").write_text(
            "\n".join(
                (
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=TrinaxAI Manager",
                    "Comment=Install, update, and remove TrinaxAI",
                    "Exec=trinaxai-manager",
                    "Icon=trinaxai-manager",
                    "Terminal=false",
                    "Categories=Utility;Development;",
                    "",
                )
            ),
            encoding="utf-8",
        )
        run(["dpkg-deb", "--build", "--root-owner-group", "-Zgzip", str(package), str(deb)])


def package(output: Path) -> tuple[Path, ...]:
    output = output if output.is_absolute() else ROOT / output
    output.mkdir(parents=True, exist_ok=True)
    binary = manager_binary()
    if not binary.exists():
        raise RuntimeError(f"Build the Manager first; missing {binary}")
    version = project_version()
    system = platform.system()
    if system == "Windows":
        executable = output / f"{NAME}-Windows.exe"
        shutil.copy2(binary, executable)
        archive = output / f"{NAME}-Windows.zip"
        _zip_file(binary, archive, f"{NAME}.exe")
    elif system == "Darwin":
        archive = output / f"{NAME}-macOS.zip"
        dmg = output / f"{NAME}-macOS.dmg"
        run(["ditto", "-c", "-k", "--keepParent", str(binary), str(archive)])
        run(
            [
                "hdiutil",
                "create",
                "-volname",
                "TrinaxAI Manager",
                "-srcfolder",
                str(binary),
                "-ov",
                "-format",
                "UDZO",
                str(dmg),
            ]
        )
    elif system == "Linux":
        _package_linux(binary, output, version)
    else:
        raise RuntimeError(f"Unsupported Manager platform: {system}")
    return verify(output)


def artifact_names(system: str | None = None) -> tuple[str, ...]:
    system = system or platform.system()
    if system == "Windows":
        return (f"{NAME}-Windows.exe", f"{NAME}-Windows.zip")
    if system == "Darwin":
        return (f"{NAME}-macOS.dmg", f"{NAME}-macOS.zip")
    if system == "Linux":
        return (f"{NAME}-Linux.deb", f"{NAME}-Linux.tar.gz")
    raise RuntimeError(f"Unsupported Manager platform: {system}")


def verify(output: Path) -> tuple[Path, ...]:
    artifacts = tuple(output / name for name in artifact_names())
    missing = [str(path) for path in artifacts if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"Manager packaging did not produce: {', '.join(missing)}")
    print("Manager artifacts:", ", ".join(path.name for path in artifacts))
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build-only", action="store_true", help="Build the host binary without packaging it")
    mode.add_argument("--package-only", action="store_true", help="Package an existing host binary")
    parser.add_argument("--output", type=Path, default=ROOT / "manager-release", help="Artifact output directory")
    args = parser.parse_args(argv)
    if not args.package_only:
        build()
    if not args.build_only:
        package(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
