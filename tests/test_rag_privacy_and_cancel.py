from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import rag_service


def test_private_absolute_metadata_is_excluded_from_llm_context() -> None:
    node = SimpleNamespace(
        metadata={"file_path": "/home/user/private/document.md", "rel_path": "document.md"},
        excluded_llm_metadata_keys=[],
    )

    rag_service._hide_private_node_metadata([SimpleNamespace(node=node)])

    assert "file_path" in node.excluded_llm_metadata_keys
    assert "rel_path" not in node.excluded_llm_metadata_keys


def test_cancel_ollama_unloads_selected_model() -> None:
    response = MagicMock()
    response.__enter__.return_value = response
    with patch.object(rag_service.urllib.request, "urlopen", return_value=response) as urlopen:
        rag_service._cancel_ollama_model("code-model")

    request = urlopen.call_args.args[0]
    assert json.loads(request.data) == {"model": "code-model", "keep_alive": 0}


def test_stream_errors_do_not_expose_exception_details() -> None:
    payload = rag_service._sse_error(RuntimeError("secret path /private/token"))

    assert "secret path" not in payload
    assert "Please retry" in payload
