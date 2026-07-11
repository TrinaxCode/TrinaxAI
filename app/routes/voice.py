"""TrinaxAI — voice endpoints for the call-mode fallback.

Endpoints de voz para el fallback del modo llamada: capabilities, STT y TTS.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config
from app.security.rate_limit import enforce_rate_limit
from app.services.voice_service import (
    stt_available,
    synthesize,
    transcribe_bytes,
    tts_available_backends,
    tts_preferred,
)
from trinaxai_core import _positive_int

router = APIRouter(prefix="/voice", tags=["voice"])
_voice_slots = threading.BoundedSemaphore(
    _positive_int(os.getenv("TRINAXAI_VOICE_MAX_CONCURRENCY"), 1, minimum=1, maximum=4)
)


def _run_voice_task(function, *args):
    with _voice_slots:
        return function(*args)


class TTSRequest(BaseModel):
    """Text-to-speech request body. / Cuerpo de la petición TTS."""

    text: str = Field(..., min_length=1, max_length=1200)
    lang: str = Field(default="es", min_length=2, max_length=5)


@router.get("/capabilities")
async def voice_capabilities() -> dict[str, Any]:
    """Return which local voice engines are available.

    Devuelve qué motores de voz locales están disponibles.
    """
    return {
        "stt": {
            "available": stt_available(),
            "engine": "openai-whisper",
            "model": None if not stt_available() else "local",
        },
        "tts": {
            "available": bool(tts_preferred()),
            "preferred": tts_preferred(),
            "backends": tts_available_backends(),
        },
    }


@router.post("/stt")
async def voice_stt(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    lang: str = Form(default="es"),
) -> dict[str, str]:
    """Speech-to-text: upload an audio file and get the transcription.

    Speech-to-text: sube un archivo de audio y recibe la transcripción.
    """
    enforce_rate_limit(request, bucket="voice_stt")
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > config.VOICE_MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="Audio file is too large")
            chunks.append(chunk)
    finally:
        await file.close()
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    try:
        text = await run_in_threadpool(
            _run_voice_task, transcribe_bytes, data, file.filename, lang
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"text": text}


@router.post("/tts")
async def voice_tts(request: Request, req: TTSRequest) -> Response:
    """Text-to-speech: send text and receive an audio WAV.

    Text-to-speech: envía texto y recibe un audio WAV.
    """
    enforce_rate_limit(request, bucket="voice_tts")
    try:
        audio_bytes, content_type = await run_in_threadpool(
            _run_voice_task, synthesize, req.text, req.lang
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    return Response(audio_bytes, media_type=content_type)
