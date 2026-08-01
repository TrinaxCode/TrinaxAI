"""Tests for the local voice fallback services.

Tests para los servicios de voz locales (fallback del modo llamada).
"""

from __future__ import annotations

import builtins
import io
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import config
from app.services import voice_service


class TestVoiceService:
    """Unit tests for voice_service helpers."""

    def test_stt_available_is_boolean(self):
        # The result depends on whether faster-whisper is installed.
        assert isinstance(voice_service.stt_available(), bool)

    def test_backend_availability_detects_installed_modules(self, monkeypatch):
        real_import = builtins.__import__
        available = {"faster_whisper", "pyttsx3", "piper_tts", "TTS.api"}

        def fake_import(name, *args, **kwargs):
            if name in available:
                return types.SimpleNamespace(WhisperModel=object, TTS=object)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        assert voice_service.stt_available() is True
        assert voice_service.tts_available_backends() == ["pyttsx3", "piper", "coqui"]

    def test_tts_available_backends_is_list(self):
        assert isinstance(voice_service.tts_available_backends(), list)

    def test_tts_preferred_is_optional_string(self):
        preferred = voice_service.tts_preferred()
        assert preferred is None or isinstance(preferred, str)

    def test_suffix_from_filename(self):
        assert voice_service._suffix_from_filename("audio.webm") == ".webm"
        assert voice_service._suffix_from_filename("audio.mp4") == ".mp4"
        assert voice_service._suffix_from_filename(None) == ".webm"

    def test_transcribe_bytes_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            voice_service.transcribe_bytes(b"", None, "es")

    def test_temp_audio_limits_suffix_and_cleanup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(voice_service.tempfile, "tempdir", str(tmp_path))
        monkeypatch.setattr(config, "VOICE_MAX_AUDIO_BYTES", 3)

        with pytest.raises(ValueError, match="too large"):
            voice_service._write_temp_audio(b"1234", "../../unsafe.exe")

        path = voice_service._write_temp_audio(b"123", "../../unsafe.exe")
        assert path.endswith(".webm")
        assert os.path.isfile(path)
        voice_service._cleanup_temp(path)
        voice_service._cleanup_temp(path)
        assert not os.path.exists(path)

    def test_transcribe_requires_installed_backend(self, monkeypatch):
        monkeypatch.setattr(voice_service, "stt_available", lambda: False)

        with pytest.raises(RuntimeError, match="not installed"):
            voice_service.transcribe_bytes(b"audio", "clip.wav", "")

    def test_load_stt_uses_configuration_and_caches(self, tmp_path, monkeypatch):
        calls: list[dict] = []

        class WhisperModel:
            def __init__(self, model, **kwargs):
                calls.append({"model": model, **kwargs})

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "faster_whisper":
                return types.SimpleNamespace(WhisperModel=WhisperModel)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        monkeypatch.setattr(voice_service, "_stt_model", None)
        monkeypatch.setattr(config, "PERSIST_DIR", str(tmp_path))
        monkeypatch.setattr(config, "VOICE_STT_MODEL", "tiny")
        monkeypatch.setenv("TRINAXAI_VOICE_DEVICE", "cpu")
        monkeypatch.setenv("TRINAXAI_VOICE_COMPUTE_TYPE", "int8")

        first = voice_service._load_stt()
        second = voice_service._load_stt()

        assert first is second
        assert calls == [
            {
                "model": "tiny",
                "device": "cpu",
                "compute_type": "int8",
                "download_root": str(tmp_path / "whisper"),
            }
        ]

    @patch.object(voice_service, "stt_available", return_value=True)
    @patch.object(voice_service, "_load_stt")
    def test_transcribe_bytes_success(self, mock_load_stt, _mock_stt_available):
        mock_model = MagicMock()
        mock_model.transcribe = MagicMock(
            return_value=([SimpleNamespace(text=" hola "), SimpleNamespace(text="mundo ")], object())
        )
        mock_load_stt.return_value = mock_model

        text = voice_service.transcribe_bytes(b"fake audio", "test.webm", "es")
        assert text == "hola mundo"
        mock_model.transcribe.assert_called_once()

    @patch.object(voice_service, "tts_preferred")
    @patch.object(voice_service, "_tts_pyttsx3")
    def test_synthesize_pyttsx3(self, mock_tts, mock_preferred):
        mock_preferred.return_value = "pyttsx3"
        mock_tts.return_value = (b"fake wav", "audio/wav")

        audio, content_type = voice_service.synthesize("hola", "es")
        assert audio == b"fake wav"
        assert content_type == "audio/wav"

    @pytest.mark.parametrize("backend", ["piper", "coqui"])
    def test_synthesize_dispatches_optional_backends(self, backend, monkeypatch):
        monkeypatch.setattr(voice_service, "tts_preferred", lambda: backend)
        monkeypatch.setattr(
            voice_service, f"_tts_{backend}", lambda text, lang: (f"{text}:{lang}".encode(), "audio/wav")
        )

        assert voice_service.synthesize("hello", "en") == (b"hello:en", "audio/wav")

    def test_tts_preference_honors_config_then_quality_order(self, monkeypatch):
        monkeypatch.setattr(voice_service, "tts_available_backends", lambda: ["pyttsx3", "piper"])
        monkeypatch.setattr(config, "VOICE_TTS_ENGINE", "pyttsx3")
        assert voice_service.tts_preferred() == "pyttsx3"

        monkeypatch.setattr(config, "VOICE_TTS_ENGINE", "missing")
        assert voice_service.tts_preferred() == "piper"

        monkeypatch.setattr(voice_service, "tts_available_backends", lambda: [])
        assert voice_service.tts_preferred() is None

    def test_voice_selection_matches_language(self):
        engine = SimpleNamespace(
            getProperty=lambda _name: [
                SimpleNamespace(id="voice-fr", languages=["fr"]),
                SimpleNamespace(id="voice-es", languages=[b"es"]),
            ]
        )

        assert voice_service._pick_pyttsx3_voice(engine, "es-MX") == "voice-es"
        assert voice_service._pick_pyttsx3_voice(SimpleNamespace(getProperty=lambda _name: []), "en") is None

    def test_piper_requires_a_model_and_synthesizes_bounded_text(self, tmp_path, monkeypatch):
        module = types.SimpleNamespace(find_model=lambda _root, _lang: None)
        monkeypatch.setitem(sys.modules, "piper_tts", module)
        monkeypatch.setattr(config, "PERSIST_DIR", str(tmp_path))
        monkeypatch.delenv("TRINAXAI_PIPER_MODEL", raising=False)

        with pytest.raises(RuntimeError, match="model not found"):
            voice_service._tts_piper("hello", "en")

        model = tmp_path / "voice.onnx"
        model.write_bytes(b"model")
        module.find_model = lambda _root, _lang: str(model)
        module.PiperVoice = lambda _path: SimpleNamespace(synthesize=lambda text: text.encode())
        monkeypatch.setattr(config, "VOICE_TTS_MAX_CHARS", 4)

        assert voice_service._tts_piper("hello", "en") == (b"hell", "audio/wav")

    def test_pyttsx3_writes_audio_and_stops_engine(self, monkeypatch):
        stopped: list[bool] = []

        class Engine:
            def getProperty(self, _name):
                return [SimpleNamespace(id="en-voice", languages=["en"])]

            def setProperty(self, _name, _value):
                return None

            def save_to_file(self, text, path):
                self.text = text
                self.path = path

            def runAndWait(self):
                with open(self.path, "wb") as stream:
                    stream.write(self.text.encode())

            def stop(self):
                stopped.append(True)

        monkeypatch.setitem(sys.modules, "pyttsx3", types.SimpleNamespace(init=Engine))
        monkeypatch.setattr(config, "VOICE_TTS_MAX_CHARS", 4)

        assert voice_service._tts_pyttsx3("hello", "en") == (b"hell", "audio/wav")
        assert stopped == [True]

    def test_coqui_writes_audio_and_cleans_temp_file(self, monkeypatch):
        class TTS:
            def __init__(self, model):
                self.model = model

            def tts_to_file(self, *, text, file_path):
                with open(file_path, "wb") as stream:
                    stream.write(text.encode())

        package = types.ModuleType("TTS")
        api = types.ModuleType("TTS.api")
        api.TTS = TTS
        monkeypatch.setitem(sys.modules, "TTS", package)
        monkeypatch.setitem(sys.modules, "TTS.api", api)
        monkeypatch.setattr(config, "VOICE_TTS_MAX_CHARS", 3)
        monkeypatch.setenv("TRINAXAI_COQUI_MODEL", "test-model")

        assert voice_service._tts_coqui("hello", "en") == (b"hel", "audio/wav")

    def test_synthesize_no_backend(self):
        with patch.object(voice_service, "tts_preferred", return_value=None):
            with pytest.raises(RuntimeError, match="No local TTS"):
                voice_service.synthesize("hola", "es")


class TestVoiceRoutes:
    """Tests for the FastAPI voice endpoints."""

    @pytest.fixture(scope="module")
    def client(self):
        # Import app once; do not reload modules to avoid numpy issues.
        from fastapi.testclient import TestClient

        from rag_api import app

        yield TestClient(app, client=("127.0.0.1", 50000))

    def test_capabilities(self, client):
        response = client.get("/v1/voice/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "stt" in data
        assert "tts" in data
        assert isinstance(data["stt"]["available"], bool)
        assert isinstance(data["tts"]["available"], bool)

    def test_stt_empty(self, client):
        response = client.post(
            "/v1/voice/stt",
            data={"lang": "es"},
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400

    def test_stt_rejects_oversized_audio(self, client, monkeypatch):
        import app.routes.voice as voice_routes

        monkeypatch.setattr(voice_routes.config, "VOICE_MAX_AUDIO_BYTES", 4)
        response = client.post(
            "/v1/voice/stt",
            data={"lang": "es"},
            files={"file": ("large.wav", b"12345", "audio/wav")},
        )
        assert response.status_code == 413

    def test_stt_with_audio(self, client):
        # Without Whisper installed the endpoint should return 501.
        # Con Whisper instalado debería devolver 200; si no, 501.
        fake_wav = io.BytesIO(b"RIFF\x00\x00\x00\x00WAVE")
        response = client.post(
            "/v1/voice/stt",
            data={"lang": "es"},
            files={"file": ("test.wav", fake_wav, "audio/wav")},
        )
        assert response.status_code in (200, 400, 501)

    def test_tts(self, client):
        response = client.post(
            "/v1/voice/tts",
            json={"text": "hola", "lang": "es"},
        )
        # 200 if a TTS backend is installed, 501 otherwise.
        assert response.status_code in (200, 501)

    def test_voice_routes_hide_backend_errors(self, client, monkeypatch):
        import app.routes.voice as voice_routes

        monkeypatch.setattr(
            voice_routes,
            "transcribe_bytes",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("/private/model/path failed")),
        )
        stt = client.post(
            "/v1/voice/stt",
            data={"lang": "es"},
            files={"file": ("test.wav", b"RIFFaudio", "audio/wav")},
        )
        monkeypatch.setattr(
            voice_routes,
            "synthesize",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("/private/voice/path failed")),
        )
        tts = client.post("/v1/voice/tts", json={"text": "hello", "lang": "en"})

        assert stt.status_code == 501
        assert stt.json()["detail"]["recovery"]
        assert "/private" not in stt.text
        assert tts.status_code == 501
        assert tts.json()["detail"]["recovery"]
        assert "/private" not in tts.text
