from trinaxai_cli.commands.doctor import (
    _find_ollama,
    _frontend_mode_from_command,
    _ollama_api_ok,
    _safe_backend_command,
)


def test_frontend_mode_detects_dev_preview_and_unknown_commands():
    assert _frontend_mode_from_command("node ./vite preview --host 0.0.0.0") == "preview"
    assert _frontend_mode_from_command("npm run preview") == "preview"
    assert _frontend_mode_from_command("node ./vite --host 0.0.0.0 --port 3334") == "dev"
    assert _frontend_mode_from_command("npm run dev") == "dev"
    assert _frontend_mode_from_command("node unrelated.js") is None


def test_backend_bind_detection_rejects_public_listener():
    assert _safe_backend_command("uvicorn app.main:app --host 0.0.0.0 --port 3333") is False
    assert _safe_backend_command("uvicorn app.main:app --host 127.0.0.1 --port 3333") is True
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
