"""Generation adapters shared by the synchronous and asynchronous RAG paths."""

from __future__ import annotations

import math
import re
import threading
from typing import Callable

from .shared_runtime import Regime


def estimate_tokens(text: str) -> int:
    """Conservative multilingual/code token estimate.

    Ollama/LlamaIndex do not expose tokenizer counts uniformly for every model
    and streaming path. Counting word runs plus punctuation is materially less
    wrong for Spanish and source code than ``len(text) / 4``.
    """
    pieces = re.findall(r"[\w]+|[^\w\s]", text or "", flags=re.UNICODE)
    total = 0
    for piece in pieces:
        if piece.isalnum() or "_" in piece:
            total += max(1, math.ceil(len(piece) / 4))
        else:
            total += 1
    return total


class TextResponse:
    """Minimal stand-in for a LlamaIndex response for ungrounded generation."""

    def __init__(self, text: str | None = None, gen=None, finish_reason: str | None = None):
        self._text = text
        self._gen = gen
        self.finish_reason = finish_reason
        self.source_nodes: list = []

    @property
    def response_gen(self):
        if self._gen is not None:
            return self._gen
        return iter([self._text or ""])

    @property
    def response(self) -> str:
        return str(self)

    def __str__(self) -> str:
        if self._text is None:
            self._text = "".join(self._gen or [])
        return self._text or ""


class AsyncTextResponse:
    """Small async equivalent used by the cancellation-safe stream path."""

    def __init__(self, gen):
        self._gen = gen
        self.finish_reason: str | None = None
        self.source_nodes: list = []

    def async_response_gen(self):
        return self._gen


async def ollama_async_chat_stream(llm, messages):
    response = await llm.async_client.chat(
        model=llm.model,
        messages=llm._convert_to_ollama_messages(messages),
        stream=True,
        format="json" if llm.json_mode else None,
        tools=None,
        think=llm.thinking,
        options=llm._model_kwargs,
        keep_alive=llm.keep_alive,
    )
    completed = False
    try:
        async for item in response:
            raw = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            message = raw.get("message") or {}
            content = message.get("content")
            thinking = message.get("thinking") or ""
            if content is None and not thinking and not raw.get("done_reason"):
                continue
            yield content or "", thinking, raw
        completed = True
    finally:
        close = getattr(response, "aclose", None)
        if close is not None:
            await close()
        if not completed:
            await llm.async_client.close()
            llm._async_client = None


class ThinkingLLM:
    """Keep Ollama thinking deltas beside, not inside, answer text."""

    def __init__(self, llm, on_thinking: Callable[[str], None] | None = None):
        self._llm = llm
        self._on_thinking = on_thinking or (lambda _part: None)
        self.finish_reason: str | None = None

    def __getattr__(self, name):
        return getattr(self._llm, name)

    def stream(self, prompt, **prompt_args):
        messages = self._llm._get_messages(prompt, **prompt_args)
        for response in self._llm.stream_chat(messages):
            thinking = getattr(response, "additional_kwargs", {}).get("thinking_delta")
            if isinstance(thinking, str) and thinking:
                self._on_thinking(thinking)
            raw = getattr(response, "raw", None)
            reason = raw.get("done_reason") if isinstance(raw, dict) else None
            if reason:
                self.finish_reason = normalize_finish_reason(reason)
            yield getattr(response, "delta", "") or ""

    async def astream(self, prompt, **prompt_args):
        messages = self._llm._get_messages(prompt, **prompt_args)

        async def _token_stream():
            async for delta, thinking, raw in ollama_async_chat_stream(self._llm, messages):
                if thinking:
                    self._on_thinking(thinking)
                reason = raw.get("done_reason")
                if reason:
                    self.finish_reason = normalize_finish_reason(reason)
                yield delta

        return _token_stream()


def normalize_finish_reason(reason: object, *, cancelled: bool = False, error: bool = False) -> str:
    if error:
        return "error"
    if cancelled:
        return "cancelled"
    value = str(reason or "").strip().lower()
    return value if value in {"stop", "length", "cancelled", "error"} else (value or "stop")


def response_finish_reason(response: object, *, cancelled: bool = False, error: bool = False) -> str:
    tracker = getattr(response, "_finish_tracker", None)
    if tracker is not None and getattr(tracker, "finish_reason", None):
        return normalize_finish_reason(tracker.finish_reason, cancelled=cancelled, error=error)
    return normalize_finish_reason(getattr(response, "finish_reason", None), cancelled=cancelled, error=error)


def structurally_incomplete(text: str) -> bool:
    """Cheap signal for an answer that can safely be continued."""
    return (text or "").count("```") % 2 == 1


def freeform_generate(
    llm,
    prompt: str,
    stream: bool,
    cancel_event: threading.Event | None = None,
    on_thinking: Callable[[str], None] | None = None,
):
    """Generate without RAG grounding. Returns a :class:`TextResponse`.

    Always drives Ollama via ``stream_complete`` under the hood, including for
    full responses, so a slow CPU generation is bounded by per-token reads.
    """
    tracked = TextResponse()

    def _token_stream():
        chunks = llm.stream_complete(prompt)
        finish_reason = None
        try:
            for chunk in chunks:
                if cancel_event is not None and cancel_event.is_set():
                    break
                thinking = getattr(chunk, "additional_kwargs", {}).get("thinking_delta")
                if on_thinking and isinstance(thinking, str) and thinking:
                    on_thinking(thinking)
                delta = getattr(chunk, "delta", None)
                yield delta if delta is not None else str(chunk)
                raw = getattr(chunk, "raw", None)
                reason = raw.get("done_reason") if isinstance(raw, dict) else None
                if reason:
                    finish_reason = normalize_finish_reason(reason)
        finally:
            tracked.finish_reason = finish_reason or "stop"
            close = getattr(chunks, "close", None)
            if close is not None:
                close()

    if stream:
        generator = _token_stream()
        tracked._gen = generator
        return tracked
    generator = _token_stream()
    tracked._text = "".join(generator)
    return tracked


async def freeform_generate_async(
    llm,
    prompt: str,
    on_thinking: Callable[[str], None] | None = None,
):
    """Async Ollama stream so task cancellation closes the HTTP response."""
    tracked = AsyncTextResponse(None)

    async def _token_stream():
        from llama_index.core.base.llms.generic_utils import prompt_to_messages

        chunks = ollama_async_chat_stream(llm, prompt_to_messages(prompt))
        finish_reason = None
        try:
            async for delta, thinking, raw in chunks:
                if on_thinking and thinking:
                    on_thinking(thinking)
                yield delta
                reason = raw.get("done_reason")
                if reason:
                    finish_reason = normalize_finish_reason(reason)
        finally:
            tracked.finish_reason = finish_reason or "stop"
            close = getattr(chunks, "aclose", None)
            if close is not None:
                await close()

    tracked._gen = _token_stream()
    return tracked


def async_text_response(text: str) -> AsyncTextResponse:
    async def _token_stream():
        yield text

    return AsyncTextResponse(_token_stream())


def wanted_deliverables(text: str) -> tuple[str, ...]:
    t = (text or "").lower()
    hits = []
    if "test" in t or "prueba" in t:
        hits.append("tests")
    if "benchmark" in t:
        hits.append("benchmark")
    if "faq" in t:
        hits.append("faq")
    if "chat" in t:
        hits.append("chat")
    if "responsive" in t or "adaptable" in t:
        hits.append("responsive")
    if "animaci" in t or "animation" in t:
        hits.append("animation")
    return tuple(hits)


def fix_prompt(regime: Regime, original: str, answer: str, findings: str) -> str:
    """Targeted single-pass correction prompt."""
    return (
        "Your previous answer to the user's request has issues that must be "
        "fixed. Keep everything that was correct; change ONLY what is needed to "
        "resolve the problems below. Return the COMPLETE corrected result "
        "(full code/files), not a diff and not a description of the changes.\n\n"
        f"USER REQUEST:\n{original}\n\n"
        f"PROBLEMS TO FIX:\n{findings}\n\n"
        f"PREVIOUS ANSWER:\n{answer}\n\n"
        "Corrected answer:"
    )
