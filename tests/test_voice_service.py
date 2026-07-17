"""Tests for the local voice fallback services.

Tests para los servicios de voz locales (fallback del modo llamada).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import voice_service


class TestVoiceService:
    """Unit tests for voice_service helpers."""

    def test_stt_available_is_boolean(self):
        # The result depends on whether faster-whisper is installed.
        assert isinstance(voice_service.stt_available(), bool)

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
