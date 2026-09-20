import json
from pathlib import Path
from types import SimpleNamespace

from trinaxai_cli.commands import doctor
from trinaxai_cli.commands.doctor import (
    _find_ollama,
    _frontend_mode_from_command,
    _ollama_api_ok,
    _safe_backend_command,
)


def test_frontend_mode_detects_dev_preview_and_unknown_commands():
    assert _frontend_mode_from_command("node server.mjs") == "serve"
    assert _frontend_mode_from_command("node ./vite preview --host 0.0.0.0") == "preview"
    assert _frontend_mode_from_command("npm run preview") == "preview"
    assert _frontend_mode_from_command("node ./vite --host 0.0.0.0 --port 3334") == "dev"
    assert _frontend_mode_from_command("npm run dev") == "dev"
    assert _frontend_mode_from_command("node unrelated.js") is None


def test_backend_bind_detection_rejects_public_listener():
    assert _safe_backend_command("uvicorn app.main:app --host 0.0.0.0 --port 3333") is False
    assert _safe_backend_command("uvicorn app.main:app --host=0.0.0.0 --port 3333") is False
    assert _safe_backend_command("uvicorn app.main:app --host 127.0.0.1 --port 3333") is True
    assert _safe_backend_command("uvicorn app.main:app --host=127.0.0.1 --port 3333") is True
    assert _safe_backend_command("") is None


def test_ollama_binary_search_checks_common_paths(monkeypatch, tmp_path):
    binary = tmp_path / "ollama"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr("trinaxai_cli.commands.doctor.shutil.which", lambda _: None)
    monkeypatch.setattr("trinaxai_cli.commands.doctor.os.path.isfile", lambda value: value == str(binary))
    monkeypatch.setattr("trinaxai_cli.commands.doctor.os.access", lambda value, mode: value == str(binary))
    monkeypatch.setattr("trinaxai_cli.commands.doctor.os.path.expanduser", lambda value: str(binary))
    assert _find_ollama() == str(binary)


def test_ollama_api_health_is_a_valid_fallback(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("trinaxai_cli.commands.doctor.urllib.request.urlopen", lambda *args, **kwargs: Response())
    assert _ollama_api_ok()


def test_doctor_json_skips_rich_memory_panel(monkeypatch, capsys):
    monkeypatch.setattr(doctor._system, "project_root", lambda: None)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: Path("missing"))
    monkeypatch.setattr(doctor._system, "env_value", lambda _key: "")
    monkeypatch.setattr(doctor, "_find_ollama", lambda: None)
    monkeypatch.setattr(doctor, "_ollama_api_ok", lambda _url: False)

    class Ui:
        def panel(self, *_args, **_kwargs):
            print("Rich panel must not reach JSON stdout")

    client = SimpleNamespace(
        base_url="http://127.0.0.1:3333",
        health=lambda: {"indexed": True, "projects": [], "collections": []},
        stats=lambda: {},
        memory_summary=lambda: {"summary": "private memory"},
    )

    doctor.run(SimpleNamespace(json=True, strict=False), client, Ui(), None)
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]


def test_doctor_marks_fresh_unindexed_install_as_info(monkeypatch, tmp_path):
    manager = tmp_path / "service_manager.py"
    manager.write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: manager)
    monkeypatch.setattr(doctor._system, "env_value", lambda _key: "http://localhost:11434")
    monkeypatch.setattr(doctor._system, "load_dotenv_values", lambda: {"TRINAXAI_FRONTEND_MODE": "serve"})
    monkeypatch.setattr(doctor, "_find_ollama", lambda: "/usr/bin/ollama")
    monkeypatch.setattr(doctor, "_ollama_api_ok", lambda _url: True)
    monkeypatch.setattr(
        doctor,
        "_process_command",
        lambda pid: "node server.mjs" if pid == 10 else "uvicorn rag_api:app --host 127.0.0.1",
    )
    services = [
        {"name": "trinaxai-frontend", "display_name": "Frontend", "running": True, "pid": 10},
        {"name": "rag_api", "display_name": "API", "running": True, "pid": 11},
    ]
    monkeypatch.setattr(
        doctor,
        "run_process_group",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(services), stderr=""),
    )
    client = SimpleNamespace(
        base_url="https://localhost:3333",
        timeout=1,
        health=lambda: {"indexed": False, "projects": [], "collections": []},
        stats=lambda: {"messages_total": 0, "tokens_estimated": 0},
        memory_summary=lambda: {},
    )

    class Ui:
        rows = []

        def table(self, _columns, rows, title=None):
            self.rows = rows

        def panel(self, *_args, **_kwargs):
            pass

    ui = Ui()
    assert doctor.run(SimpleNamespace(json=False, strict=True), client, ui, None) == 0
    index_row = next(row for row in ui.rows if row[0] == "Index built")
    assert index_row[1:] == ["INFO", "run: trinaxai index ."]
