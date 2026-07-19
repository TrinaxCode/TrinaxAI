"""Complexity scoring (Phase 4 of the audit).

Maps a classified task to a 0–100 complexity score from cheap textual signals.
The score drives *mode* decisions: how much output budget to reserve, whether
to enable the validate→fix pass, and how much context to allow.

No LLM, no network — deterministic and fast.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.classifier import Classification

# Signal weights (sum of maxima ≈ 100). Tuned so that:
#   - a trivial one-liner scores < 25
#   - "implement an LRU+TTL cache with O(1), tests and benchmark" scores > 55
#   - "modern landing with glassmorphism, chat, FAQ, responsive" scores > 55
# The key insight from the audit: hard tasks are often SHORT but densely packed
# ("LRU + TTL, O(1), tests, benchmark"), so requirement/deliverable density
# matters far more than raw length.
_W_LENGTH = 10  # prompt length (weak proxy for spec size)
_W_REQUIREMENTS = 24  # inline feature list + bullets + numbered items
_W_DELIVERABLES = 22  # tests, benchmark, faq, responsive, ...
_W_CREATIVITY = 12
_W_PRECISION = 12  # O(1), correctness-critical wording
_W_REASONING = 12  # architecture / algorithm / debugging depth
_W_MULTIFILE = 8  # multiple files / components

_PRECISION_HINTS = (
    "o(1)",
    "o(n)",
    "o(log",
    "exacto",
    "preciso",
    "correcto",
    "sin errores",
    "must compile",
    "compile",
    "thread-safe",
    "concurren",
    "atómico",
    "atomic",
    "edge case",
    "caso límite",
    "invariante",
    "invariant",
)
_MULTIFILE_HINTS = (
    "varios archivos",
    "múltiples archivos",
    "multiple files",
    "cada archivo",
    "estructura de carpetas",
    "proyecto completo",
    "full project",
    "monorepo",
    "varios componentes",
    "múltiples componentes",
)


@dataclass(frozen=True)
class ScoreBreakdown:
    total: int
    length: int
    requirements: int
    deliverables: int
    creativity: int
    precision: int
    reasoning: int
    multifile: int

    @property
    def mode(self) -> str:
        if self.total <= 25:
            return "trivial"
        if self.total <= 55:
            return "normal"
        if self.total <= 80:
            return "complex"
        return "deep"


def _scale(value: float, cap: float, weight: int) -> int:
    if cap <= 0:
        return 0
    return int(round(min(value / cap, 1.0) * weight))


def complexity_score(text: str, cls: Classification) -> ScoreBreakdown:
    raw = text or ""
    t = raw.lower()

    length = _scale(len(raw), 1600, _W_LENGTH)
    requirements = _scale(cls.num_requirements, 6, _W_REQUIREMENTS)
    deliverables = _scale(cls.num_deliverables, 4, _W_DELIVERABLES)

    creativity = 0
    if "creative" in cls.categories:
        creativity = _W_CREATIVITY
    elif "frontend" in cls.categories:
        creativity = int(_W_CREATIVITY * 0.6)

    precision = _scale(sum(1 for h in _PRECISION_HINTS if h in t), 2, _W_PRECISION)

    reasoning_hits = len(cls.categories & {"architecture", "algorithm", "debugging", "math", "analysis"})
    reasoning = _scale(reasoning_hits, 2, _W_REASONING)

    multifile = _W_MULTIFILE if any(h in t for h in _MULTIFILE_HINTS) else 0

    # "Substantial build" bonus: asking to CREATE a real code/UI artifact is
    # inherently harder than a one-off question. This is what separates the two
    # audit failure cases (LRU cache, landing page) from trivial chat — both are
    # terse but demand a complete, correct deliverable.
    combo = 0
    if cls.is_generation and (cls.is_code or "creative" in cls.categories):
        combo = 10
        if cls.num_deliverables >= 2:
            combo += 6

    total = min(
        100,
        length + requirements + deliverables + creativity + precision + reasoning + multifile + combo,
    )
    return ScoreBreakdown(
        total=total,
        length=length,
        requirements=requirements,
        deliverables=deliverables,
        creativity=creativity,
        precision=precision,
        reasoning=reasoning,
        multifile=multifile,
    )
