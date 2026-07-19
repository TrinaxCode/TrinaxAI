"""Deterministic output quality heuristics (Phase 6 of the audit).

Cheap, local, no-LLM checks that inspect a generated answer and report what is
missing or broken. They feed the generate→validate→fix policy (Phase 7): if a
complex code/creative task comes back with syntax errors or missing deliverables,
we run exactly one targeted correction pass.

These checks are smoke tests, not a compiler or a proof of correctness. They
never raise on bad input and return structured findings for one optional repair
pass. Callers should label them as heuristics in user-facing surfaces.
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


def _mask_js_literals(code: str) -> str:
    """Mask JS/TS strings, comments, templates and likely regex literals."""
    out = list(code)
    index = 0
    state = "normal"
    quote = ""
    regex_class = False
    previous_significant = ""
    while index < len(code):
        char = code[index]
        nxt = code[index + 1] if index + 1 < len(code) else ""
        if state == "normal":
            if char in {"'", '"', "`"}:
                state, quote = "string", char
                out[index] = " "
            elif char == "/" and nxt == "/":
                state = "line_comment"
                out[index] = out[index + 1] = " "
                index += 1
            elif char == "/" and nxt == "*":
                state = "block_comment"
                out[index] = out[index + 1] = " "
                index += 1
            elif char == "/" and previous_significant in {"", "=", "(", "[", "{", ":", ",", ";", "!", "?"}:
                state = "regex"
                regex_class = False
                out[index] = " "
            elif not char.isspace():
                previous_significant = char
        elif state == "string":
            if char != "\n":
                out[index] = " "
            if char == "\\":
                if index + 1 < len(code):
                    if code[index + 1] != "\n":
                        out[index + 1] = " "
                    index += 1
            elif char == quote:
                state = "normal"
                previous_significant = "v"
        elif state == "line_comment":
            if char == "\n":
                state = "normal"
            else:
                out[index] = " "
        elif state == "block_comment":
            if char != "\n":
                out[index] = " "
            if char == "*" and nxt == "/":
                out[index + 1] = " "
                index += 1
                state = "normal"
        elif state == "regex":
            if char != "\n":
                out[index] = " "
            if char == "\\":
                if index + 1 < len(code):
                    out[index + 1] = " "
                    index += 1
            elif char == "[":
                regex_class = True
            elif char == "]":
                regex_class = False
            elif char == "/" and not regex_class:
                state = "normal"
                previous_significant = "v"
        index += 1
    return "".join(out)


def _check_balanced_pairs(code: str, label: str) -> list[str]:
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {value: key for key, value in pairs.items()}
    stack: list[tuple[str, int]] = []
    for offset, char in enumerate(code):
        if char in pairs:
            stack.append((char, offset))
        elif char in closing:
            if not stack or stack[-1][0] != closing[char]:
                return [f"Unbalanced {label}: unexpected {char} at offset {offset}."]
            stack.pop()
    if stack:
        char, offset = stack[-1]
        return [f"Unbalanced {label}: {char} opened at offset {offset} is not closed."]
    return []


def _check_js_ts(code: str) -> list[str]:
    errors = _check_balanced_pairs(_mask_js_literals(code), "JS/TS delimiters")
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
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", code, flags=re.I | re.S)
        if style_blocks and not any(_has_responsive_css(style) for style in style_blocks):
            errors.append("HTML: inline CSS has no responsive layout signal.")
    return errors


def _check_css(code: str, require_responsive: bool) -> list[str]:
    masked = re.sub(r"/\*.*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "", code, flags=re.DOTALL)
    errors = _check_balanced_pairs(masked, "CSS delimiters")
    if require_responsive and not _has_responsive_css(code):
        errors.append("CSS: no responsive layout signal (fluid sizing, flex/grid, media or container query).")
    return errors


def _has_responsive_css(code: str) -> bool:
    low = code.lower()
    signals = (
        "@media",
        "@container",
        "clamp(",
        "minmax(",
        "auto-fit",
        "auto-fill",
        "display:flex",
        "display: flex",
        "display:grid",
        "display: grid",
        "max-width",
        "inline-size",
        "vw",
        "dvw",
        "cqw",
    )
    return any(signal in low for signal in signals) or bool(
        re.search(r"\b(?:width|flex-basis)\s*:\s*\d+(?:\.\d+)?%", low)
    )


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
