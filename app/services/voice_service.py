"""TrinaxAI — local voice services (STT + TTS).

Servicios de voz locales para el fallback del modo llamada. Se cargan de forma
perezosa (lazy) para no ralentizar el arranque de la API cuando no se usan.

Local voice services for the call-mode fallback. They are loaded lazily so the
API startup is not slowed down when voice is not used.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

import config

LOG = logging.getLogger("trinaxai.voice_service")

# Lazy model cache / caché perezosa de modelos
_stt_model: Any | None = None


def stt_available() -> bool:
    """Return True if the local Whisper backend is importable."""
    try:
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


def _load_stt() -> Any:
    """Load Whisper once and cache it."""
    global _stt_model
    if _stt_model is not None:
        return _stt_model
    import whisper

    model_name = config.VOICE_STT_MODEL
    _stt_model = whisper.load_model(model_name)
    LOG.info("Whisper STT loaded: %s", model_name)
    return _stt_model


def _suffix_from_filename(filename: str | None) -> str:
    """Pick a safe temp suffix from the uploaded filename."""
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in {".webm",".mp3",".mp4",".m4a",".ogg",".wav",".flac"}:
            return ext
    return ".webm"


def _write_temp_audio(data: bytes, filename: str | None) -> str:
    """Write uploaded audio to a temp file and return its path."""
    if not data:
        raise ValueError("Empty audio payload")
    if len(data) > config.VOICE_MAX_AUDIO_BYTES:
        raise ValueError(f"Audio too large: {len(data)} bytes")
    suffix = _suffix_from_filename(filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        return tmp.name


def _cleanup_temp(path: str) -> None:
    """Remove a temp file, ignoring errors."""
    try:
        os.remove(path)
    except OSError:
        pass


def transcribe_bytes(data: bytes, filename: str | None, lang: str) -> str:
    """Transcribe audio bytes to text using local Whisper.

    Args:
        data: Raw audio bytes from the client.
        filename: Optional original filename for extension guessing.
        lang: Language hint (e.g. 'es', 'en'). Whisper accepts it for the
            'language' argument. Pass empty string to let it auto-detect.

    Returns:
        Transcribed text, stripped.
    """
    if not data:
        raise ValueError("Empty audio payload")
    if not stt_available():
        raise RuntimeError("Whisper STT is not installed")
    path = _write_temp_audio(data, filename)
    try:
        model = _load_stt()
        kwargs: dict[str, Any] = {}
        if lang:
            kwargs["language"] = lang
        result = model.transcribe(path, **kwargs)
        return result.get("text", "").strip()
    finally:
        _cleanup_temp(path)


# ── TTS backends / motores de TTS ──


def tts_available_backends() -> list[str]:
    """Return the list of installed local TTS backends."""
    backends = []
    try:
        import pyttsx3  # noqa: F401

        backends.append("pyttsx3")
    except ImportError:
        pass
    try:
        import piper_tts  # noqa: F401

        backends.append("piper")
    except ImportError:
        pass
    try:
        from TTS.api import TTS  # noqa: F401

        backends.append("coqui")
    except ImportError:
        pass
    return backends


def tts_preferred() -> str | None:
    """Pick the preferred backend according to the config and availability."""
    available = tts_available_backends()
    requested = config.VOICE_TTS_ENGINE
    if requested and requested in available:
        return requested
    # Piper = best quality/weight ratio · Coqui = best quality · pyttsx3 = universal
    for b in ("piper", "coqui", "pyttsx3"):
        if b in available:
            return b
    return None


def _pick_pyttsx3_voice(engine: Any, lang: str) -> str | None:
    """Choose a voice matching the requested language."""
    voices = engine.getProperty("voices")
    if not voices:
        return None
    base = lang.lower()[:2]
    for v in voices:
        voice_id = getattr(v, "id", "").lower()
        voice_languages = getattr(v, "languages", []) or []
        voice_languages = [str(l).lower() for l in voice_languages]
        if base in voice_id or base in voice_languages:
            return v.id
    return None


def _tts_pyttsx3(text: str, lang: str) -> tuple[bytes, str]:
    """Synthesize speech with pyttsx3 and return WAV bytes."""
    import pyttsx3

    if len(text) > config.VOICE_TTS_MAX_CHARS:
        text = text[: config.VOICE_TTS_MAX_CHARS]

    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    voice_id = _pick_pyttsx3_voice(engine, lang)
    if voice_id:
        engine.setProperty("voice", voice_id)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name
    try:
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        with open(out_path, "rb") as f:
            return f.read(), "audio/wav"
    finally:
        _cleanup_temp(out_path)
        engine.stop()


def _tts_piper(text: str, lang: str) -> tuple[bytes, str]:
    """Synthesize speech with Piper (lightweight ONNX TTS)."""
    import piper_tts

    if len(text) > config.VOICE_TTS_MAX_CHARS:
        text = text[: config.VOICE_TTS_MAX_CHARS]

    # Piper voice models live in storage/piper or are configured via env.
    model_dir = os.path.join(config.PERSIST_DIR, "piper")
    model_path = os.getenv("TRINAXAI_PIPER_MODEL") or piper_tts.find_model(model_dir, lang)
    if not model_path or not os.path.exists(model_path):
        raise RuntimeError(f"Piper model not found for language {lang}")
    synthesizer = piper_tts.PiperVoice(model_path)
    audio = synthesizer.synthesize(text)
    return audio, "audio/wav"


def _tts_coqui(text: str, lang: str) -> tuple[bytes, str]:
    """Synthesize speech with Coqui TTS (heavier, higher quality)."""
    from TTS.api import TTS

    if len(text) > config.VOICE_TTS_MAX_CHARS:
        text = text[: config.VOICE_TTS_MAX_CHARS]

    model_name = os.getenv("TRINAXAI_COQUI_MODEL", "tts_models/es/mai/tacotron2-DDC")
    if not model_name:
        # Fall back to English model if no specific model is configured.
        model_name = "tts_models/en/ljspeech/tacotron2-DDC"
    tts = TTS(model_name)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name
    try:
        tts.tts_to_file(text=text, file_path=out_path)
        with open(out_path, "rb") as f:
            return f.read(), "audio/wav"
    finally:
        _cleanup_temp(out_path)


def synthesize(text: str, lang: str = "es") -> tuple[bytes, str]:
    """Synthesize text to audio using the preferred local backend.

    Args:
        text: Text to speak.
        lang: Target language (e.g. 'es', 'en').

    Returns:
        Tuple of (audio bytes, content type).
    """
    preferred = tts_preferred()
    if preferred == "piper":
        return _tts_piper(text, lang)
    if preferred == "coqui":
        return _tts_coqui(text, lang)
    if preferred == "pyttsx3":
        return _tts_pyttsx3(text, lang)
    raise RuntimeError("No local TTS backend available")
