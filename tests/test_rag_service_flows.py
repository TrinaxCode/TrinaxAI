from __future__ import annotations

import asyncio
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.generation.spec import Regime
from app.schemas import ChatRequest
from app.services import rag_service


def _spec(*, use_rag: bool, stream_mode: str = "auto"):
    return SimpleNamespace(
        use_rag=use_rag,
        model="test-model",
        regime=Regime.EXPLAIN if not use_rag else Regime.GROUNDED_QA,
        validate=False,
        max_fix_passes=0,
        retrieval_mode=stream_mode,
        llm_kwargs=lambda: {},
        describe=lambda: "test plan",
    )


class _Llm:
    def stream_complete(self, _prompt):
        yield SimpleNamespace(delta="local ")
        yield SimpleNamespace(delta="answer")


def test_run_rag_generates_without_retrieval_for_ordinary_chat(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: _Llm())
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = rag_service.run_rag(
        [{"role": "user", "content": "Explain dependency injection"}],
        stream=False,
    )

    assert str(response) == "local answer"
    assert nodes == []
    assert model == "test-model"
    assert project is None


def test_run_rag_uses_retrieved_nodes_and_hides_private_metadata(monkeypatch) -> None:
    node = SimpleNamespace(
        metadata={"file_path": "/private/project.py", "rel_path": "project.py"},
        excluded_llm_metadata_keys=[],
    )
    scored = SimpleNamespace(node=node, metadata=node.metadata, score=0.8, get_content=lambda: "trusted passage")
    synthesized = rag_service._TextResponse(text="grounded answer")
    synthesizer = SimpleNamespace(synthesize=lambda query, nodes: synthesized)
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [scored])
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "get_response_synthesizer", lambda **_kwargs: synthesizer)
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, _project = rag_service.run_rag(
        [{"role": "user", "content": "According to my files, what is configured?"}],
        stream=False,
        retrieval_mode="knowledge",
    )

    assert str(response) == "grounded answer"
    assert nodes == [scored]
    assert model == "test-model"
    assert "file_path" in node.excluded_llm_metadata_keys


def test_generate_stream_emits_plan_tokens_sources_usage_and_done(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_model_slots", SimpleNamespace(acquire=lambda: None, release=lambda: None))
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(
        rag_service,
        "run_rag",
        lambda *_args, **_kwargs: (rag_service._TextResponse(gen=iter(["one", " two"])), [], "test-model", None),
    )

    events = list(
        rag_service.generate_stream(
            [{"role": "user", "content": "hello"}],
            request_id="request-1",
        )
    )

    payload = "".join(events)
    assert '"phase":"generating"' in payload
    assert '"content":"one"' in payload
    assert "trinaxai_usage" in payload
    assert "data: [DONE]" in payload


def test_nonstream_rag_consumes_provider_generator_inside_inference_scope(monkeypatch) -> None:
    closed = False

    def tokens():
        nonlocal closed
        try:
            yield "grounded "
            yield "answer"
        finally:
            closed = True

    response = SimpleNamespace(response_gen=tokens())
    monkeypatch.setattr(
        rag_service,
        "_run_model_task",
        lambda *_args, **_kwargs: (response, ["node"], "test-model", "project"),
    )
    request = ChatRequest(messages=[{"role": "user", "content": "question"}], stream=False)

    result, nodes, model, project = rag_service._run_rag_nonstream(request, threading.Event())

    assert str(result) == "grounded answer"
    assert closed is True
    assert (nodes, model, project) == (["node"], "test-model", "project")


def test_chat_nonstream_returns_openai_shape(monkeypatch) -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="request-2"),
        is_disconnected=lambda: asyncio.sleep(0, result=False),
    )
    req = ChatRequest(messages=[{"role": "user", "content": "hello"}], stream=False)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(
        rag_service,
        "_run_rag_nonstream",
        lambda *_args: (rag_service._TextResponse(text="answer"), [], "test-model", None),
    )

    result = asyncio.run(rag_service.chat(req, request))

    assert result["id"] == "chatcmpl-request-2"
    assert result["choices"][0]["message"]["content"] == "answer"
    assert result["trinaxai"]["rag_used"] is False
    assert result["usage"]["estimated"] is True


def test_chat_disconnect_signals_worker_and_unloads_model(monkeypatch) -> None:
    observed = threading.Event()

    def worker(_req, cancel_event):
        assert cancel_event.wait(2)
        observed.set()
        return rag_service._TextResponse(text="ignored"), [], "test-model", None

    request = SimpleNamespace(
        state=SimpleNamespace(request_id="request-3"),
        is_disconnected=lambda: asyncio.sleep(0, result=True),
    )
    req = ChatRequest(messages=[{"role": "user", "content": "hello"}], stream=False)
    cancelled_models = []
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "_run_rag_nonstream", worker)
    monkeypatch.setattr(rag_service, "_cancel_ollama_model", cancelled_models.append)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(rag_service.chat(req, request))

    assert observed.is_set()
    assert cancelled_models == ["test-model"]
