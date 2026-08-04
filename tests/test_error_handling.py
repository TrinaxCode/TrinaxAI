from __future__ import annotations

import asyncio
import json

from fastapi import HTTPException
from starlette.requests import Request

from app.errors import http_exception_handler
from trinaxai_errors import ERROR_DEFINITIONS, ErrorCategory, classify_error


def test_every_error_category_has_a_complete_safe_contract() -> None:
    assert set(ERROR_DEFINITIONS) == set(ErrorCategory)
    for definition in ERROR_DEFINITIONS.values():
        assert definition.code.startswith("ERR_")
        assert definition.message and definition.recovery and definition.developer_log


def test_classification_never_returns_exception_text_to_clients() -> None:
    info = classify_error(RuntimeError("secret token /private/key"), status_code=500)

    assert info.category is ErrorCategory.INTERNAL_SERVER_ERROR
    payload = info.to_client_dict()
    assert "secret token" not in str(payload)
    assert info.code == "ERR_INTERNAL_SERVER_ERROR"


def test_common_boundary_failures_are_classified_once() -> None:
    assert classify_error(PermissionError()).category is ErrorCategory.PERMISSION_DENIED
    assert classify_error(FileNotFoundError()).category is ErrorCategory.FILE_NOT_FOUND
    assert classify_error(TimeoutError()).category is ErrorCategory.NETWORK_TIMEOUT
    assert classify_error(MemoryError()).category is ErrorCategory.MEMORY_LIMIT_REACHED


def test_http_boundary_masks_raw_exception_detail() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/test", "headers": []})
    response = asyncio.run(http_exception_handler(request, HTTPException(status_code=500, detail="secret token")))

    assert "secret token" not in response.body.decode()
    assert json.loads(response.body)["error"]["code"] == "ERR_INTERNAL_SERVER_ERROR"


def test_http_boundary_localizes_canonical_errors_from_accept_language() -> None:
    spanish_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"accept-language", b"es-MX, en;q=0.8")],
        }
    )
    english_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"accept-language", b"en-US, es;q=0.8")],
        }
    )

    spanish = json.loads(
        asyncio.run(
            http_exception_handler(
                spanish_request,
                HTTPException(status_code=503, detail="AI unavailable"),
            )
        ).body
    )
    english = json.loads(
        asyncio.run(
            http_exception_handler(
                english_request,
                HTTPException(status_code=503, detail="AI unavailable"),
            )
        ).body
    )

    assert spanish["error"]["message"] == "Un servicio externo no está disponible."
    assert english["error"]["message"] == "An external service is unavailable."
    assert spanish["error"]["message"] != english["error"]["message"]
