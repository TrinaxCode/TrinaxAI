"""TaskSpec: a fully-resolved generation plan.

A :class:`TaskSpec` is the single object the live pipeline (``rag_api.run_rag``)
consumes. It bundles the routed model, decoding parameters, whether retrieval
should run, and which prompt regime to use. Building it is cheap and
deterministic (see ``presets.build_task_spec``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Regime(str, Enum):
    """Prompt/behaviour regime. Determines which system prompt + rules apply.

    - GROUNDED_QA: answer only from retrieved CONTEXT (the historical default).
      Correct for "ask me about my documents". Temperature 0, RAG on.
    - CODE_GEN:    generate/refactor/debug code. Invention is the point; RAG is
      off unless the user references their own repo/docs.
    - CREATIVE:    UI/landing/design. High temperature, long output, no
      "answer only from context" restriction.
    - EXPLAIN:     documentation/explanation prose. Medium temperature.
    """

    GROUNDED_QA = "grounded_qa"
    CODE_GEN = "code_gen"
    CREATIVE = "creative"
    EXPLAIN = "explain"


@dataclass(frozen=True)
class TaskSpec:
    """A resolved plan for one generation turn."""

    # Routing
    model: str
    regime: Regime
    categories: frozenset[str] = field(default_factory=frozenset)
    score: int = 0

    # Decoding / Ollama options
    num_ctx: int = 8192
    num_predict: int = 2048
    temperature: float = 0.0
    top_p: float | None = None
    top_k: int | None = None
    repeat_penalty: float | None = None
    stop: tuple[str, ...] | None = None

    # Pipeline behaviour
    use_rag: bool = True
    validate: bool = False
    max_fix_passes: int = 0

    def llm_kwargs(self) -> dict:
        """Kwargs for ``rag_api.get_llm`` / ``config.make_llm``."""
        return {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "stop": self.stop,
        }

    def describe(self) -> str:
        """Short human string for logs / SSE debug."""
        cats = ",".join(sorted(self.categories)) or "-"
        return (
            f"regime={self.regime.value} score={self.score} cats=[{cats}] "
            f"model={self.model} ctx={self.num_ctx} predict={self.num_predict} "
            f"temp={self.temperature} rag={int(self.use_rag)} "
            f"validate={int(self.validate)} fix={self.max_fix_passes}"
        )
