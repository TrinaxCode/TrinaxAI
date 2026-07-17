from trinaxai_cli.commands.doctor import (
    _frontend_mode_from_command,
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
