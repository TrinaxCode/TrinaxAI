from __future__ import annotations

import os
import plistlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import auto_update


def test_macos_weekly_update_uses_calendar_and_handles_spaces(tmp_path: Path) -> None:
    home = tmp_path / "User & Family"
    base_dir = home / "Application Support" / "TrinaxAI"
    (base_dir / "scripts").mkdir(parents=True)
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")

    with (
        patch.object(auto_update.platform, "system", return_value="Darwin"),
        patch.object(auto_update.Path, "home", return_value=home),
        patch.object(auto_update, "_run", return_value=completed),
    ):
        detail = auto_update.enable(base_dir)

    plist = home / "Library" / "LaunchAgents" / (auto_update.MAC_LABEL + ".plist")
    with plist.open("rb") as handle:
        payload = plistlib.load(handle)
    assert "weekly LaunchAgent" in detail
    assert payload["WorkingDirectory"] == str(base_dir)
    assert payload["StartCalendarInterval"]["Weekday"] == 1
    assert payload["ProgramArguments"][-1] == str(base_dir)


@pytest.mark.skipif(os.name == "nt", reason="systemd paths require POSIX semantics")
def test_linux_weekly_update_creates_persistent_timer(tmp_path: Path) -> None:
    home = tmp_path / "home"
    base_dir = tmp_path / "TrinaxAI"
    (base_dir / "scripts").mkdir(parents=True)
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")

    with (
        patch.object(auto_update.platform, "system", return_value="Linux"),
        patch.object(auto_update.Path, "home", return_value=home),
        patch.object(auto_update.shutil, "which", return_value="/usr/bin/systemctl"),
        patch.object(auto_update, "_run", return_value=completed),
    ):
        auto_update.enable(base_dir)

    unit_dir = home / ".config" / "systemd" / "user"
    timer = (unit_dir / auto_update.LINUX_TIMER).read_text(encoding="utf-8")
    service = (unit_dir / auto_update.LINUX_SERVICE).read_text(encoding="utf-8")
    assert "OnCalendar=Sun" in timer
    assert "Persistent=true" in timer
    assert "auto_update.py" in service
    assert str(base_dir) in service
