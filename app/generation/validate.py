"""Deterministic output validators (Phase 6 of the audit).

Cheap, local, no-LLM checks that inspect a generated answer and report what is
missing or broken. They feed the generate→validate→fix policy (Phase 7): if a
complex code/creative task comes back with syntax errors or missing deliverables,
we run exactly one targeted correction pass.

Validators never raise on bad input — they return structured findings.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def summary(self) -> str:
        bits = []
        if self.errors:
            bits.append("errors: " + "; ".join(self.errors))
        if self.missing:
            bits.append("missing: " + ", ".join(self.missing))
        return " | ".join(bits) or "ok"


_FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Return list of (lang, code) fenced blocks."""
    return [(m.group(1).lower(), m.group(2)) for m in _FENCE_RE.finditer(text or "")]


def _check_python(code: str) -> list[str]:
    errors = []
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Python syntax error: {e.msg} (line {e.lineno})")
    # Obvious placeholder markers that mean the code is incomplete.
    if re.search(r"(?m)^\s*\.\.\.\s*(#.*)?$", code) or "rest of code" in code.lower():
        errors.append("Python code contains placeholder/ellipsis (incomplete).")
    return errors


def _balanced(code: str, open_c: str, close_c: str, label: str) -> list[str]:
    # Naive but effective: ignores strings, good enough as a smoke test.
    if code.count(open_c) != code.count(close_c):
        return [f"Unbalanced {label} ({open_c}{close_c})."]
    return []


def _check_js_ts(code: str) -> list[str]:
    errors = _balanced(code, "{", "}", "braces")
    errors += _balanced(code, "(", ")", "parens")
    if "rest of code" in code.lower():
        errors.append("JS/TS code contains placeholder (incomplete).")
    return errors


def _check_html(code: str, require_responsive: bool) -> list[str]:
    errors = []
    low = code.lower()
    if "<html" in low and "</html>" not in low:
        errors.append("HTML: <html> not closed.")
    if "<body" in low and "</body>" not in low:
        errors.append("HTML: <body> not closed.")
    if require_responsive:
        if "viewport" not in low:
            errors.append("HTML: missing responsive <meta viewport>.")
        # Landing pages usually inline their CSS in <style>; a real responsive
        # layout needs media queries somewhere in that inline CSS too.
        if "<style" in low and "@media" not in low:
            errors.append("HTML: inline CSS has no @media query (not responsive).")
    return errors


def _check_css(code: str, require_responsive: bool) -> list[str]:
    errors = _balanced(code, "{", "}", "CSS braces")
    if require_responsive and "@media" not in code:
        errors.append("CSS: no @media query despite responsive requirement.")
    return errors


def validate_output(
    text: str,
    *,
    regime: str = "code_gen",
    deliverables: tuple[str, ...] = (),
    require_responsive: bool = False,
) -> ValidationResult:
    """Validate a generated answer.

    ``deliverables`` is a list of keywords the user asked for (e.g. "tests",
    "benchmark", "faq", "chat"); each one that is entirely absent from the
    output is reported as missing.
    """
    text = text or ""
    errors: list[str] = []
    blocks = extract_code_blocks(text)

    for lang, code in blocks:
        if lang in ("python", "py"):
            errors += _check_python(code)
        elif lang in ("js", "javascript", "ts", "typescript", "jsx", "tsx"):
            errors += _check_js_ts(code)
        elif lang in ("html", "htm"):
            errors += _check_html(code, require_responsive)
        elif lang == "css":
            errors += _check_css(code, require_responsive)

    # If a code/creative regime produced zero code blocks, that itself is a miss.
    if regime in ("code_gen", "creative") and not blocks:
        errors.append("No code block produced for a generation task.")

    low = text.lower()
    missing = []
    _DELIVERABLE_MARKERS = {
        "tests": ("def test", "test(", "it(", "describe(", "assert", "pytest", "unittest"),
        "test": ("def test", "test(", "it(", "describe(", "assert"),
        "benchmark": ("benchmark", "timeit", "perf_counter", "time.time", "performance.now"),
        "faq": ("faq", "accordion", "preguntas frecuentes"),
        "chat": ("chat", "message", "mensaje", "input"),
        "responsive": ("@media", "viewport", "grid", "flex"),
        "animation": ("@keyframes", "transition", "animation", "animate"),
        "docstring": ('"""', "'''", "/**"),
        "types": (": str", ": int", "interface ", "type ", ": number", ": string"),
    }
    for want in deliverables:
        key = want.lower().strip()
        markers = _DELIVERABLE_MARKERS.get(key)
        if markers and not any(m in low for m in markers):
            missing.append(want)

    ok = not errors and not missing
    return ValidationResult(ok=ok, errors=errors, missing=missing)
