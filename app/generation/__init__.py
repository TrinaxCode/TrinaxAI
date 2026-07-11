"""TrinaxAI generation pipeline (Phase 3–8 of the generation audit).

This package sits between the auto-router and the actual Ollama call. It turns
a raw conversation into a :class:`TaskSpec` — a fully resolved generation plan
(model, decoding params, RAG on/off, prompt regime) — and provides deterministic
validators plus the generate→validate→fix policy.

Everything here is local and dependency-light (stdlib + config). No network, no
extra LLM call for classification/scoring — those are pure functions over text.

Public entry points:
    build_task_spec(messages, *, model_override=None) -> TaskSpec
    classify(text, history_text="") -> Classification
    complexity_score(text, classification) -> ScoreBreakdown
    validate_output(text, spec) -> ValidationResult
"""

from __future__ import annotations

from app.generation.classifier import Classification, classify
from app.generation.presets import build_task_spec
from app.generation.scoring import ScoreBreakdown, complexity_score
from app.generation.spec import Regime, TaskSpec
from app.generation.validate import ValidationResult, validate_output

__all__ = [
    "Classification",
    "Regime",
    "ScoreBreakdown",
    "TaskSpec",
    "ValidationResult",
    "build_task_spec",
    "classify",
    "complexity_score",
    "validate_output",
]
