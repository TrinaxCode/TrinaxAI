from __future__ import annotations

import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import service_manager as sm


class _FakeBackend:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []

    def start(self, name: str, *, command: list[str], cwd: str | None = None,
              env: dict[str, str] | None = None, log_file: str | None = None) -> sm.ProcessState:
        self.started.append(name)
        return sm.ProcessState(name=name, running=True, pid=1234, detail="started")

    def stop(self, name: str) -> sm.ProcessState:
        self.stopped.append(name)
        return sm.ProcessState(name=name, running=False, detail="stopped")

    def status(self, name: str) -> sm.ProcessState:
        return sm.ProcessState(name=name, running=False, detail="not running")


class ServiceManagerPersistenceTests(unittest.TestCase):
    def test_rag_command_uses_https_only_when_pem_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            env = {"TRINAXAI_RAG_HTTPS": "1", "TRINAXAI_PORT": "3333"}

            command = sm._rag_command("python", str(base_dir), env)
            self.assertNotIn("--ssl-keyfile", command)
            self.assertEqual(sm._rag_health_url(str(base_dir), env), "http://127.0.0.1:3333/health")

            cert_dir = base_dir / "chat-pwa" / "certs"
            cert_dir.mkdir(parents=True)
            (cert_dir / "localhost-key.pem").write_text("key", encoding="utf-8")
            (cert_dir / "localhost.pem").write_text("cert", encoding="utf-8")

            command = sm._rag_command("python", str(base_dir), env)
            self.assertIn("--ssl-keyfile", command)
            self.assertEqual(sm._rag_health_url(str(base_dir), env), "https://127.0.0.1:3333/health")

    def test_stop_ai_disables_boot_and_start_ai_reenables_it(self) -> None:
        fake_backend = _FakeBackend()
        systemctl_calls: list[list[str]] = []

        def fake_run(cmd, **_kwargs):  # noqa: ANN001
            if isinstance(cmd, list) and cmd and cmd[0].endswith("systemctl"):
                systemctl_calls.append(cmd)
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            with (
                patch.object(sm, "_backend", fake_backend),
                patch.object(sm.platform, "system", return_value="Linux"),
                patch.object(sm.shutil, "which", side_effect=lambda name: "/usr/bin/systemctl" if name == "systemctl" else None),
                patch.object(sm.subprocess, "run", side_effect=fake_run),
            ):
                stop_results = sm.stop_ai(str(base_dir))
                state = json.loads((base_dir / "storage" / "service_state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["ai_enabled"], False)
                self.assertEqual([item.name for item in stop_results], ["ollama", "rag_api"])
                self.assertEqual(fake_backend.stopped, ["ollama", "rag_api"])
                self.assertEqual(
                    systemctl_calls,
                    [
                        ["/usr/bin/systemctl", "disable", "ollama.service"],
                        ["/usr/bin/systemctl", "disable", "rag_api.service"],
                        ["/usr/bin/systemctl", "disable", "ai-rag.service"],
                    ],
                )

                systemctl_calls.clear()
                fake_backend.started.clear()

                start_results = sm.start_ai(str(base_dir))
                state = json.loads((base_dir / "storage" / "service_state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["ai_enabled"], True)
                self.assertEqual([item.name for item in start_results], ["ollama", "rag_api", "trinaxai-frontend"])
                self.assertEqual(fake_backend.started, ["ollama", "rag_api", "trinaxai-frontend"])
                self.assertEqual(
                    systemctl_calls,
                    [
                        ["/usr/bin/systemctl", "enable", "ollama.service"],
                        ["/usr/bin/systemctl", "enable", "rag_api.service"],
                        ["/usr/bin/systemctl", "enable", "ai-rag.service"],
                    ],
                )

    def test_macos_autostart_plist_handles_spaces_and_xml_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "User & Family"
            base_dir = home / "Application Support" / "TrinaxAI"
            base_dir.mkdir(parents=True)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with (
                patch.object(sm.platform, "system", return_value="Darwin"),
                patch.object(sm.Path, "home", return_value=home),
                patch.object(sm.subprocess, "run", return_value=completed),
            ):
                result = sm.enable_autostart(str(base_dir))

            plist = home / "Library" / "LaunchAgents" / "com.trinaxcode.trinaxai.plist"
            with plist.open("rb") as handle:
                payload = plistlib.load(handle)
            self.assertTrue(result.running)
            self.assertEqual(payload["WorkingDirectory"], str(base_dir))
            self.assertEqual(payload["ProgramArguments"][-1], str(base_dir))


if __name__ == "__main__":
    unittest.main()
