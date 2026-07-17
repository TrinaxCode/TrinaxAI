#!/usr/bin/env python3
"""Install and run TrinaxAI's zero-configuration weekly updater."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

TASK_NAME = "TrinaxAI Weekly Update"
LINUX_SERVICE = "trinaxai-update.service"
LINUX_TIMER = "trinaxai-update.timer"
MAC_LABEL = "com.trinaxcode.trinaxai.update"


def _run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, timeout=60, **kwargs)


def _quote_systemd(value: str | Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _log(base_dir: Path, message: str) -> None:
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with (log_dir / "auto-update.log").open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message.rstrip()}\n")


def enable(base_dir: Path) -> str:
    base_dir = base_dir.resolve()
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable).resolve()
    script = base_dir / "scripts" / "auto_update.py"
    system = platform.system()

    if system == "Linux":
        if shutil.which("systemctl"):
            unit_dir = Path.home() / ".config" / "systemd" / "user"
            unit_dir.mkdir(parents=True, exist_ok=True)
            (unit_dir / LINUX_SERVICE).write_text(
                "[Unit]\nDescription=Check for TrinaxAI updates\nAfter=network-online.target\n\n"
                "[Service]\nType=oneshot\n"
                f"WorkingDirectory={_quote_systemd(base_dir)}\n"
                f"ExecStart={_quote_systemd(python)} {_quote_systemd(script)} run --base-dir {_quote_systemd(base_dir)}\n",
                encoding="utf-8",
            )
            (unit_dir / LINUX_TIMER).write_text(
                "[Unit]\nDescription=Check for TrinaxAI updates every week\n\n"
                "[Timer]\nOnCalendar=Sun *-*-* 03:00:00\nPersistent=true\n"
                "RandomizedDelaySec=2h\nUnit=trinaxai-update.service\n\n"
                "[Install]\nWantedBy=timers.target\n",
                encoding="utf-8",
            )
            reload_result = _run(["systemctl", "--user", "daemon-reload"])
            enable_result = _run(
                ["systemctl", "--user", "enable", "--now", LINUX_TIMER]
            )
            if not reload_result.returncode and not enable_result.returncode:
                return f"weekly systemd timer enabled: {unit_dir / LINUX_TIMER}"
        if shutil.which("crontab"):
            state_dir = base_dir / "storage" / "maintenance"
            state_dir.mkdir(parents=True, exist_ok=True)
            wrapper = state_dir / "weekly-update.sh"
            wrapper.write_text(
                "#!/usr/bin/env sh\n"
                f"cd {shlex.quote(str(base_dir))} || exit 1\n"
                f"exec {shlex.quote(str(python))} {shlex.quote(str(script))} "
                f"run --base-dir {shlex.quote(str(base_dir))}\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o700)
            current = _run(["crontab", "-l"])
            lines = [
                line for line in current.stdout.splitlines()
                if "# TrinaxAI weekly update" not in line
            ]
            lines.append(f"17 3 * * 0 {shlex.quote(str(wrapper))} # TrinaxAI weekly update")
            result = _run(["crontab", "-"], input="\n".join(lines) + "\n")
            if not result.returncode:
                return "weekly cron update enabled"
        raise RuntimeError("could not enable a user systemd timer or cron task")

    if system == "Darwin":
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / f"{MAC_LABEL}.plist"
        payload = {
            "Label": MAC_LABEL,
            "ProgramArguments": [
                str(python), str(script), "run", "--base-dir", str(base_dir)
            ],
            "StartCalendarInterval": {"Weekday": 1, "Hour": 3, "Minute": 0},
            "RunAtLoad": False,
            "WorkingDirectory": str(base_dir),
            "StandardOutPath": str(base_dir / "logs" / "auto-update.log"),
            "StandardErrorPath": str(base_dir / "logs" / "auto-update.log"),
        }
        with plist.open("wb") as handle:
            plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=False)
        _run(["launchctl", "unload", str(plist)])
        result = _run(["launchctl", "load", str(plist)])
        if result.returncode:
            raise RuntimeError((result.stderr or "launchctl failed").strip())
        return f"weekly LaunchAgent enabled: {plist}"

    if system == "Windows":
        state_dir = base_dir / "storage" / "maintenance"
        state_dir.mkdir(parents=True, exist_ok=True)
        command_file = state_dir / "weekly-update.cmd"
        wrapper = state_dir / "weekly-update.vbs"
        command_file.write_text(
            "@echo off\r\n"
            f'cd /d "{base_dir}"\r\n'
            f'"{python}" "{script}" run --base-dir "{base_dir}"\r\n',
            encoding="utf-8",
        )
        escaped_command = str(command_file).replace('"', '""')
        wrapper.write_text(
            'Set shell = CreateObject("WScript.Shell")\r\n'
            f'shell.Run """{escaped_command}""", 0, False\r\n',
            encoding="utf-8",
        )
        result = _run(
            [
                "schtasks", "/Create", "/F", "/SC", "WEEKLY", "/D", "SUN",
                "/ST", "03:00", "/TN", TASK_NAME,
                "/TR", f'wscript.exe //B //Nologo "{wrapper}"',
            ]
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "schtasks failed").strip())
        return f"weekly Windows task enabled: {TASK_NAME}"

    raise RuntimeError(f"automatic updates are not supported on {system}")


def disable(base_dir: Path) -> str:
    system = platform.system()
    if system == "Linux":
        if shutil.which("systemctl"):
            _run(["systemctl", "--user", "disable", "--now", LINUX_TIMER])
            unit_dir = Path.home() / ".config" / "systemd" / "user"
            (unit_dir / LINUX_TIMER).unlink(missing_ok=True)
            (unit_dir / LINUX_SERVICE).unlink(missing_ok=True)
            _run(["systemctl", "--user", "daemon-reload"])
        if shutil.which("crontab"):
            current = _run(["crontab", "-l"])
            lines = [
                line for line in current.stdout.splitlines()
                if "# TrinaxAI weekly update" not in line
            ]
            _run(["crontab", "-"], input="\n".join(lines) + "\n")
        (base_dir / "storage" / "maintenance" / "weekly-update.sh").unlink(
            missing_ok=True
        )
    elif system == "Darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"
        if plist.exists():
            _run(["launchctl", "unload", str(plist)])
            plist.unlink(missing_ok=True)
    elif system == "Windows":
        _run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
        state_dir = base_dir / "storage" / "maintenance"
        (state_dir / "weekly-update.cmd").unlink(missing_ok=True)
        (state_dir / "weekly-update.vbs").unlink(missing_ok=True)
    return "weekly automatic updates disabled"


def run_update(base_dir: Path) -> int:
    base_dir = base_dir.resolve()
    lock = base_dir / "storage" / "maintenance" / "update.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if time.time() - lock.stat().st_mtime < 6 * 60 * 60:
            _log(base_dir, "Another update is already running; skipped.")
            return 0
        lock.unlink(missing_ok=True)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)

    try:
        # Executing a mutable script downloaded from ``main`` is not a secure
        # update channel. Until signed release manifests are available, the
        # scheduled task is deliberately check-only and asks the user to run
        # the installed updater interactively after reviewing the release.
        if not (base_dir / ".git").is_dir() or not shutil.which("git"):
            _log(
                base_dir,
                "Update check skipped: no Git metadata; run 'trinaxai update' manually.",
            )
            return 0
        local = _run(["git", "-C", str(base_dir), "rev-parse", "HEAD"])
        remote = _run(
            [
                "git",
                "ls-remote",
                "https://github.com/TrinaxCode/TrinaxAI.git",
                "refs/heads/main",
            ]
        )
        if local.returncode or remote.returncode or not remote.stdout.strip():
            detail = (remote.stderr or local.stderr or "could not resolve versions").strip()
            raise RuntimeError(detail)
        local_sha = local.stdout.strip()
        remote_sha = remote.stdout.split()[0]
        if local_sha == remote_sha:
            _log(base_dir, f"No update available ({local_sha[:12]}).")
        else:
            _log(
                base_dir,
                f"Update available: {local_sha[:12]} -> {remote_sha[:12]}. "
                "Run 'trinaxai update' interactively.",
            )
        return 0
    except Exception as exc:
        _log(base_dir, f"Automatic update failed safely: {exc}")
        return 1
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="TrinaxAI automatic update manager")
    parser.add_argument("action", choices=("enable", "disable", "run"))
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    base_dir = Path(args.base_dir)
    if args.action == "enable":
        print(enable(base_dir))
        return 0
    if args.action == "disable":
        print(disable(base_dir))
        return 0
    return run_update(base_dir)


if __name__ == "__main__":
    raise SystemExit(main())
