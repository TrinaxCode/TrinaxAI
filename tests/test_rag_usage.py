from __future__ import annotations

from app.generation import build_task_spec
from app.services.rag_service import _estimate_tokens, _stream_quality_payload, _usage_payload


def test_token_estimate_handles_spanish_and_code_without_returning_zero() -> None:
    spanish = _estimate_tokens("¿Cómo funciona la indexación híbrida?")
    code = _estimate_tokens("const answer = items.map((item) => item.id);")

    assert spanish >= 7
    assert code >= 14


def test_usage_payload_is_nonzero_and_explicitly_estimated() -> None:
    usage = _usage_payload(
        [{"role": "user", "content": "Explica el índice"}],
        "El índice combina búsqueda vectorial y léxica.",
    )

    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["estimated"] is True


def test_streaming_generation_reports_quality_as_heuristic() -> None:
    messages = [{
        "role": "user",
        "content": (
            "Crea una landing moderna con glassmorphism, animaciones, chat, FAQ "
            "y diseño responsive premium con varias secciones"
        ),
    }]
    spec = build_task_spec(messages)

    quality = _stream_quality_payload(spec, messages, "respuesta incompleta")

    assert quality["checked"] is True
    assert quality["kind"] == "heuristic"
    assert quality["ok"] is False
