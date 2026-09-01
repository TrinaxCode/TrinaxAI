from __future__ import annotations

import asyncio
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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


def test_freeform_generation_keeps_provider_thinking_out_of_content() -> None:
    seen = []

    class ThinkingLlm:
        def stream_complete(self, _prompt):
            yield SimpleNamespace(delta="", additional_kwargs={"thinking_delta": "paso"})
            yield SimpleNamespace(delta="respuesta", additional_kwargs={})

    response = rag_service._freeform_generate(ThinkingLlm(), "prompt", stream=True, on_thinking=seen.append)

    assert list(response.response_gen) == ["", "respuesta"]
    assert seen == ["paso"]


def test_social_greeting_still_uses_the_model_without_thinking(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **kwargs: captured.update(kwargs) or _Llm())
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, _model, project = rag_service.run_rag(
        [{"role": "user", "content": "hola bro"}],
        stream=False,
    )

    assert str(response) == "local answer"
    assert nodes == []
    assert project is None
    assert captured["thinking"] is False


def test_freeform_generation_preserves_ollama_length_reason() -> None:
    class LengthLimitedLlm:
        def stream_complete(self, _prompt):
            yield SimpleNamespace(delta="partial", raw={"done": True, "done_reason": "length"})

    response = rag_service._freeform_generate(LengthLimitedLlm(), "prompt", stream=False)

    assert str(response) == "partial"
    assert response.finish_reason == "length"


def test_completion_metadata_marks_length_and_open_markdown_as_pending() -> None:
    metadata = rag_service._completion_metadata("stop", "```python\nprint('unfinished')")

    assert metadata == {
        "reason": "length",
        "status": "pending",
        "can_continue": True,
        "max_continuations": rag_service.config.MAX_CONTINUATIONS,
    }


def test_rag_abstention_signal_is_limited_to_deterministic_messages() -> None:
    assert rag_service._is_rag_abstention(rag_service.NO_RELEVANT_RESULTS_MSG, rag_requested=True)
    assert rag_service._is_rag_abstention("I am unable to answer from the provided context.", rag_requested=True)
    assert rag_service._is_rag_abstention("No se ha encontrado información en los archivos.", rag_requested=True)
    assert not rag_service._is_rag_abstention(rag_service.NO_RELEVANT_RESULTS_MSG, rag_requested=False)
    assert not rag_service._is_rag_abstention("The model chose these words.", rag_requested=True)


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


def test_run_rag_abstains_when_auto_rag_has_no_candidates(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [])
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = rag_service.run_rag(
        [{"role": "user", "content": "What is in my indexed files?"}],
        stream=False,
        retrieval_mode="auto",
    )

    assert str(response) == rag_service.NO_RELEVANT_RESULTS_MSG
    assert nodes == []
    assert (model, project) == ("test-model", None)


def test_run_rag_abstains_when_auto_rag_candidates_are_below_min_score(monkeypatch) -> None:
    node = SimpleNamespace(
        metadata={},
        excluded_llm_metadata_keys=[],
        score=0.001,
        get_content=lambda: "untrusted passage",
    )
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "RAG_MIN_SCORE", 0.015)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [node])
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)
    monkeypatch.setattr(
        rag_service,
        "get_response_synthesizer",
        lambda **_kwargs: pytest.fail("low-score evidence must not reach the synthesizer"),
    )

    response, nodes, model, project = rag_service.run_rag(
        [{"role": "user", "content": "What is in my indexed files?"}],
        stream=False,
        retrieval_mode="auto",
    )

    assert str(response) == rag_service.NO_RELEVANT_RESULTS_MSG
    assert nodes == []
    assert (model, project) == ("test-model", None)


@pytest.mark.asyncio
async def test_sync_and_async_rag_paths_share_request_context(monkeypatch) -> None:
    spec = _spec(use_rag=False)
    prepared_calls = []

    def prepare(_messages, **_kwargs):
        prepared_calls.append(True)
        return (
            _messages,
            _messages,
            "hello",
            False,
            "retrieval",
            "synthesis",
            None,
            "Answer in English.",
            False,
            spec,
        )

    async def async_tokens():
        yield "async answer"

    monkeypatch.setattr(rag_service, "_prepare_rag_context", prepare)
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "build_generation_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(
        rag_service, "_freeform_generate", lambda *_args, **_kwargs: rag_service._TextResponse(text="sync answer")
    )
    monkeypatch.setattr(
        rag_service,
        "_freeform_generate_async",
        lambda *_args, **_kwargs: asyncio.sleep(0, result=rag_service._AsyncTextResponse(async_tokens())),
    )
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    sync_response, _, _, _ = rag_service.run_rag([{"role": "user", "content": "hello"}], stream=False)
    async_response, _, _, _ = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "hello"}],
    )

    assert str(sync_response) == "sync answer"
    assert [token async for token in async_response.async_response_gen()] == ["async answer"]
    assert prepared_calls == [True, True]


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
    assert '"trinaxai_finish"' in payload
    assert "trinaxai_usage" in payload
    assert "data: [DONE]" in payload


def test_generate_stream_emits_thinking_on_its_own_sse_channel(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_model_slots", SimpleNamespace(acquire=lambda: None, release=lambda: None))
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))

    def run(*_args, **kwargs):
        kwargs["on_thinking"]("paso")
        return rag_service._TextResponse(gen=iter(["respuesta"])), [], "test-model", None

    monkeypatch.setattr(rag_service, "run_rag", run)
    payload = "".join(rag_service.generate_stream([{"role": "user", "content": "hello"}]))

    assert '"trinaxai_thinking":"paso"' in payload
    assert '"content":"respuesta"' in payload
    assert payload.index("trinaxai_thinking") < payload.index('"content":"respuesta"')
    assert '"thinking_duration_ms"' in payload


@pytest.mark.asyncio
async def test_async_ollama_stream_closes_provider_response() -> None:
    class DumpItem:
        def __init__(self, value):
            self.value = value

        def model_dump(self):
            return self.value

    class StreamResponse:
        def __init__(self):
            self.items = iter(
                [
                    DumpItem({"message": {"content": None, "thinking": "hidden"}}),
                    {"message": {"content": "answer", "thinking": "thought"}, "done_reason": "stop"},
                    {"message": {"content": None}, "done_reason": "length"},
                ]
            )
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self):
            self.closed = True

    response = StreamResponse()

    class Client:
        def __init__(self):
            self.closed = False

        async def chat(self, **_kwargs):
            return response

        async def close(self):
            self.closed = True

    client = Client()
    llm = SimpleNamespace(
        async_client=client,
        _async_client=client,
        model="test-model",
        _convert_to_ollama_messages=lambda messages: messages,
        json_mode=False,
        thinking=True,
        _model_kwargs={},
        keep_alive=None,
    )

    chunks = [chunk async for chunk in rag_service._ollama_async_chat_stream(llm, [{"role": "user"}])]

    assert chunks == [
        ("", "hidden", {"message": {"content": None, "thinking": "hidden"}}),
        ("answer", "thought", {"message": {"content": "answer", "thinking": "thought"}, "done_reason": "stop"}),
        ("", "", {"message": {"content": None}, "done_reason": "length"}),
    ]
    assert response.closed is True
    assert client.closed is False
    assert llm._async_client is client


@pytest.mark.asyncio
async def test_async_ollama_stream_closes_client_when_iterator_is_cancelled() -> None:
    class StreamResponse:
        def __init__(self):
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.Event().wait()
            raise StopAsyncIteration

        async def aclose(self):
            self.closed = True

    class Client:
        def __init__(self, response):
            self.response = response
            self.closed = False

        async def chat(self, **_kwargs):
            return self.response

        async def close(self):
            self.closed = True

    response = StreamResponse()
    client = Client(response)
    llm = SimpleNamespace(
        async_client=client,
        _async_client=client,
        model="test-model",
        _convert_to_ollama_messages=lambda messages: messages,
        json_mode=False,
        thinking=False,
        _model_kwargs={},
        keep_alive=None,
    )
    stream = rag_service._ollama_async_chat_stream(llm, [])
    task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await stream.aclose()

    assert response.closed is True
    assert client.closed is True
    assert llm._async_client is None


@pytest.mark.asyncio
async def test_thinking_llm_async_stream_reports_thinking_and_finish() -> None:
    response = SimpleNamespace(
        items=iter([{"message": {"content": "answer", "thinking": "thought"}, "done_reason": "stop"}])
    )

    class Client:
        async def chat(self, **_kwargs):
            class Iterator:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    try:
                        return next(response.items)
                    except StopIteration as exc:
                        raise StopAsyncIteration from exc

                async def aclose(self):
                    return None

            return Iterator()

        async def close(self):
            return None

    llm = SimpleNamespace(
        async_client=Client(),
        _async_client=None,
        model="test-model",
        _get_messages=lambda prompt, **_kwargs: [{"role": "user", "content": prompt}],
        _convert_to_ollama_messages=lambda messages: messages,
        json_mode=False,
        thinking=True,
        _model_kwargs={},
        keep_alive=None,
    )
    seen = []
    tracker = rag_service._ThinkingLLM(llm, seen.append)

    stream = await tracker.astream("prompt")
    assert [token async for token in stream] == ["answer"]
    assert seen == ["thought"]
    assert tracker.finish_reason == "stop"


@pytest.mark.asyncio
async def test_freeform_async_generation_preserves_provider_thinking() -> None:
    class Stream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "done", False):
                raise StopAsyncIteration
            self.done = True
            return {"message": {"content": "answer", "thinking": "thought"}, "done_reason": "stop"}

        async def aclose(self):
            return None

    class Client:
        async def chat(self, **_kwargs):
            return Stream()

        async def close(self):
            return None

    llm = SimpleNamespace(
        async_client=Client(),
        _async_client=None,
        model="test-model",
        _convert_to_ollama_messages=lambda messages: messages,
        json_mode=False,
        thinking=True,
        _model_kwargs={},
        keep_alive=None,
    )
    seen = []
    response = await rag_service._freeform_generate_async(llm, "prompt", on_thinking=seen.append)

    assert [token async for token in response.async_response_gen()] == ["answer"]
    assert seen == ["thought"]
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_async_text_response_emits_text() -> None:
    response = rag_service._async_text_response("plain text")

    assert [token async for token in response.async_response_gen()] == ["plain text"]


@pytest.mark.asyncio
async def test_async_rag_stream_synthesizes_lazily(monkeypatch) -> None:
    node = SimpleNamespace(
        metadata={"rel_path": "notes.md", "collection_id": "default"},
        excluded_llm_metadata_keys=[],
        get_content=lambda: "grounded passage",
    )

    class Synthesizer:
        async def asynthesize(self, _query, nodes):
            assert nodes == [node]

            async def tokens():
                yield "grounded"
                yield " answer"

            return rag_service._AsyncTextResponse(tokens())

    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("retrieval", "synthesis"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: "project")
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "Answer in English.")
    monkeypatch.setattr(rag_service, "wants_creator_bio", lambda _text: False)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [node])
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "get_response_synthesizer", lambda **_kwargs: Synthesizer())
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "What is in my notes?"}],
    )

    assert response._finish_tracker is not None
    assert [token async for token in response.async_response_gen()] == ["grounded", " answer"]
    assert nodes == [node]
    assert (model, project) == ("test-model", "project")


@pytest.mark.asyncio
async def test_async_rag_stream_accepts_materialized_synthesizer_response(monkeypatch) -> None:
    node = SimpleNamespace(
        metadata={"rel_path": "notes.md", "collection_id": "default"},
        excluded_llm_metadata_keys=[],
        get_content=lambda: "grounded passage",
    )

    class Synthesizer:
        async def asynthesize(self, _query, nodes):
            assert nodes == [node]
            return SimpleNamespace(response="grounded answer")

    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("retrieval", "synthesis"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "Answer in English.")
    monkeypatch.setattr(rag_service, "wants_creator_bio", lambda _text: False)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [node])
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "get_response_synthesizer", lambda **_kwargs: Synthesizer())
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "What is in my notes?"}],
    )

    assert [token async for token in response.async_response_gen()] == ["grounded answer"]
    assert nodes == [node]
    assert (model, project) == ("test-model", None)


@pytest.mark.asyncio
async def test_async_rag_stream_abstains_when_no_candidates(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("retrieval", "synthesis"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "Answer in English.")
    monkeypatch.setattr(rag_service, "wants_creator_bio", lambda _text: False)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [])
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "What is in my notes?"}],
    )

    assert [token async for token in response.async_response_gen()] == [rag_service.NO_RELEVANT_RESULTS_MSG]
    assert nodes == []
    assert (model, project) == ("test-model", None)


@pytest.mark.asyncio
async def test_async_rag_stream_abstains_when_auto_rag_candidate_is_below_min_score(monkeypatch) -> None:
    node = SimpleNamespace(
        metadata={},
        excluded_llm_metadata_keys=[],
        score=0.001,
        get_content=lambda: "untrusted passage",
    )
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "RAG_MIN_SCORE", 0.015)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("retrieval", "synthesis"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _text: None)
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "Answer in English.")
    monkeypatch.setattr(rag_service, "wants_creator_bio", lambda _text: False)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service, "_cached_retrieve", lambda *_args: [node])
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)
    monkeypatch.setattr(
        rag_service,
        "get_response_synthesizer",
        lambda **_kwargs: pytest.fail("low-score evidence must not reach the synthesizer"),
    )

    response, nodes, model, project = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "What is in my notes?"}],
        retrieval_mode="auto",
    )

    assert [token async for token in response.async_response_gen()] == [rag_service.NO_RELEVANT_RESULTS_MSG]
    assert nodes == []
    assert (model, project) == ("test-model", None)


@pytest.mark.asyncio
async def test_async_freeform_path_returns_stream(monkeypatch) -> None:
    async def tokens():
        yield "answer"

    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda messages: messages)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "Answer in English.")
    monkeypatch.setattr(rag_service, "wants_creator_bio", lambda _text: False)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "build_generation_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(
        rag_service,
        "_freeform_generate_async",
        lambda *_args, **_kwargs: asyncio.sleep(0, result=rag_service._AsyncTextResponse(tokens())),
    )
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)

    response, nodes, model, project = await rag_service._run_rag_stream_async(
        [{"role": "user", "content": "Explain this."}],
    )

    assert [token async for token in response.async_response_gen()] == ["answer"]
    assert nodes == []
    assert (model, project) == ("test-model", None)


@pytest.mark.asyncio
async def test_async_response_tokens_completes_with_request_monitor() -> None:
    async def tokens():
        yield "one"
        yield "two"

    request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
    response = rag_service._AsyncTextResponse(tokens())

    assert [token async for token in rag_service._async_response_tokens(response, request)] == ["one", "two"]


@pytest.mark.asyncio
async def test_async_generate_stream_emits_complete_sse(monkeypatch) -> None:
    async def tokens():
        yield "answer"

    async def run(*_args, **kwargs):
        kwargs["on_thinking"]("thought")
        return rag_service._AsyncTextResponse(tokens()), [], "test-model", None

    monkeypatch.setattr(
        rag_service, "_model_slots", SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: None)
    )
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "_run_rag_stream_async", run)
    monkeypatch.setattr(rag_service.state, "lifecycle_stopping", threading.Event())

    events = [
        event
        async for event in rag_service.async_generate_stream(
            [{"role": "user", "content": "hello"}],
            request_id="request-async",
        )
    ]
    payload = "".join(events)

    assert '"phase":"generating"' in payload
    assert '"trinaxai_thinking":"thought"' in payload
    assert '"content":"answer"' in payload
    assert '"trinaxai_finish"' in payload
    assert "trinaxai_sources" in payload
    assert "trinaxai_usage" in payload
    assert "trinaxai_timing" in payload
    assert payload.endswith("data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_async_generate_stream_reports_missing_index(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_service, "_model_slots", SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: None)
    )
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)

    payload = "".join(
        [
            event
            async for event in rag_service.async_generate_stream(
                [{"role": "user", "content": "search my files"}],
            )
        ]
    )

    assert rag_service.NO_INDEX_MSG in payload
    assert '"abstained":true' in payload
    assert payload.endswith("data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_async_generate_stream_reports_selected_model_metadata(monkeypatch) -> None:
    async def tokens():
        yield "answer"

    async def run(*_args, **_kwargs):
        return rag_service._AsyncTextResponse(tokens()), [], "selected-model", "project"

    monkeypatch.setattr(
        rag_service, "_model_slots", SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: None)
    )
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(rag_service, "_run_rag_stream_async", run)
    monkeypatch.setattr(rag_service.state, "lifecycle_stopping", threading.Event())

    payload = "".join(
        [
            event
            async for event in rag_service.async_generate_stream(
                [{"role": "user", "content": "hello"}],
            )
        ]
    )

    assert '"model":"selected-model"' in payload
    assert '"project":"project"' in payload


@pytest.mark.asyncio
async def test_async_generate_stream_emits_safe_error_and_releases_slot(monkeypatch) -> None:
    released = []
    monkeypatch.setattr(
        rag_service,
        "_model_slots",
        SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: released.append(True)),
    )
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))

    async def fail(*_args, **_kwargs):
        raise RuntimeError("provider details stay private")

    monkeypatch.setattr(rag_service, "_run_rag_stream_async", fail)
    payload = "".join(
        [
            event
            async for event in rag_service.async_generate_stream(
                [{"role": "user", "content": "hello"}],
            )
        ]
    )

    assert '"trinaxai_error"' in payload
    assert "provider details stay private" not in payload
    assert released == [True]
    assert payload.endswith("data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_async_stream_cancels_upstream_on_client_disconnect(monkeypatch) -> None:
    closed = asyncio.Event()
    disconnect_checks = 0

    async def tokens():
        try:
            yield "partial"
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def is_disconnected():
        nonlocal disconnect_checks
        disconnect_checks += 1
        return disconnect_checks >= 3

    monkeypatch.setattr(
        rag_service, "_model_slots", SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: None)
    )
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=False))
    monkeypatch.setattr(
        rag_service,
        "_run_rag_stream_async",
        lambda *_args, **_kwargs: asyncio.sleep(
            0, result=(rag_service._AsyncTextResponse(tokens()), [], "test-model", None)
        ),
    )
    cancelled_models = []
    monkeypatch.setattr(rag_service, "_cancel_ollama_model", cancelled_models.append)

    request = SimpleNamespace(is_disconnected=is_disconnected)
    stream = rag_service.async_generate_stream(
        [{"role": "user", "content": "hello"}],
        request=request,
    )
    with pytest.raises(asyncio.CancelledError):
        async for _event in stream:
            pass

    assert closed.is_set()
    assert cancelled_models == ["test-model"]


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
    assert result["trinaxai"]["abstained"] is False
    assert result["usage"]["estimated"] is True


@pytest.mark.asyncio
async def test_chat_stream_empty_knowledge_collection_returns_safe_sse(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "authorize_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "_knowledge_collection_state", lambda _collections: "empty")

    request = SimpleNamespace(state=SimpleNamespace(request_id="request-empty"))
    req = ChatRequest(
        messages=[{"role": "user", "content": "what is in my collection?"}],
        stream=True,
        mode="knowledge",
    )
    response = await rag_service.chat(req, request)
    payload = "".join([event async for event in response.body_iterator])

    assert rag_service.EMPTY_COLLECTION_MSG in payload
    assert '"abstained":true' in payload
    assert '"error_code":"collection_empty"' in payload
    assert '"trinaxai_finish"' in payload
    assert payload.endswith("data: [DONE]\n\n")


def test_chat_nonstream_without_index_returns_safe_message(monkeypatch) -> None:
    request = SimpleNamespace(state=SimpleNamespace(request_id="request-no-index"))
    req = ChatRequest(messages=[{"role": "user", "content": "search my files"}], stream=False)
    monkeypatch.setattr(rag_service, "authorize_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))

    result = asyncio.run(rag_service.chat(req, request))

    assert result["choices"][0]["message"]["content"] == rag_service.NO_INDEX_MSG
    assert result["trinaxai"]["rag_used"] is False
    assert result["trinaxai"]["abstained"] is True


@pytest.mark.asyncio
async def test_chat_auto_requires_private_scope_when_router_selects_rag(monkeypatch) -> None:
    requested_scopes = []

    def deny_private(_request, scope):
        requested_scopes.append(scope)
        if scope == "read_private":
            raise HTTPException(status_code=403, detail="private scope required")

    monkeypatch.setattr(rag_service, "authorize_scope", deny_private)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", object())
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _spec(use_rag=True))

    request = SimpleNamespace(
        state=SimpleNamespace(request_id="request-private"),
        is_disconnected=lambda: asyncio.sleep(0, result=False),
    )
    req = ChatRequest(messages=[{"role": "user", "content": "what is in my indexed documents?"}], stream=True)

    with pytest.raises(HTTPException) as denied:
        await rag_service.chat(req, request)

    assert denied.value.status_code == 403
    assert requested_scopes == ["read_private"]


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
