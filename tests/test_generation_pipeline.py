"""Tests for the generation pipeline (classifier, scoring, presets, validators).

These are pure-function tests — no Ollama, no network — so they run in CI.
"""

from __future__ import annotations

import config
from app.generation import build_task_spec, classify, complexity_score, validate_output
from app.generation.spec import Regime


def _spec(text: str, **kw):
    return build_task_spec([{"role": "user", "content": text}], **kw)


# ── Regime classification ─────────────────────────────────────────────────

def test_landing_page_is_creative_regime():
    c = classify(
        "Crea una landing page moderna con glassmorphism, animaciones, un chat, "
        "FAQ funcional y diseño responsive premium"
    )
    assert c.regime is Regime.CREATIVE
    assert "creative" in c.categories


def test_lru_cache_is_code_regime():
    c = classify(
        "Implementa una caché LRU + TTL en Python con complejidad O(1), "
        "incluye tests y un benchmark"
    )
    assert c.regime is Regime.CODE_GEN
    assert "algorithm" in c.categories


def test_code_question_is_explain_not_codegen():
    # A conceptual question about code should explain, not generate a project.
    assert classify("qué es un decorador en python").regime is Regime.EXPLAIN
    assert classify("cómo funciona async/await en javascript?").regime is Regime.EXPLAIN


def test_explicit_repo_lookup_is_grounded():
    c = classify("según el archivo config.py qué hace make_llm en mi proyecto")
    assert c.regime is Regime.GROUNDED_QA
    assert "rag_lookup" in c.categories


def test_everyday_topic_is_explain_not_grounded():
    # The old pipeline forced these through grounded-QA ("only from context").
    assert classify("dame una receta saludable de pollo").regime is Regime.EXPLAIN


def test_debugging_routes_to_code():
    c = classify("tengo un TypeError en mi useEffect de React, no funciona, arréglalo")
    assert c.regime is Regime.CODE_GEN
    assert "debugging" in c.categories


# ── Complexity scoring ────────────────────────────────────────────────────

def test_trivial_prompt_scores_low():
    c = classify("hola")
    assert complexity_score("hola", c).total <= 25


def test_lru_and_landing_reach_complex_mode():
    lru = "Implementa una caché LRU + TTL en Python con O(1), tests y benchmark."
    landing = (
        "Crea una landing moderna con glassmorphism, animaciones, chat, FAQ y "
        "diseño responsive premium con varias secciones"
    )
    assert complexity_score(lru, classify(lru)).total >= 56
    assert complexity_score(landing, classify(landing)).total >= 56


# ── TaskSpec resolution / decoding params ─────────────────────────────────

def test_generation_disables_rag_and_sets_output_budget():
    s = _spec("Crea una función en Python que sume dos números", has_index=True)
    assert s.use_rag is False
    assert s.num_predict >= 384  # never clipped to nothing
    assert s.top_p is not None and s.repeat_penalty is not None  # knobs are sent


def test_creative_uses_higher_temperature():
    s = _spec(
        "Crea una landing page moderna con glassmorphism y animaciones",
        has_index=True,
    )
    assert s.regime is Regime.CREATIVE
    assert s.temperature >= 0.4  # creative is NOT greedy


def test_grounded_lookup_keeps_temperature_zero_and_rag():
    s = _spec("según mis documentos indexados, qué dice el readme", has_index=True)
    assert s.regime is Regime.GROUNDED_QA
    assert s.use_rag is True
    assert s.temperature == 0.0


def test_complex_code_routes_to_deep_model():
    s = _spec(
        "Implementa una caché LRU + TTL en Python con O(1), tests y benchmark",
        has_index=True,
    )
    assert s.model == config.MODEL_DEEP


def test_grounded_degrades_to_free_regime_without_index():
    s = _spec("según el archivo config.py qué hace make_llm", has_index=False)
    assert s.use_rag is False
    assert s.regime in (Regime.CODE_GEN, Regime.EXPLAIN)


def test_output_budget_reserved_against_context():
    # A huge prompt must shrink num_predict, never overflow num_ctx.
    s = _spec("crea código " + "x " * 5000, has_index=True, estimated_prompt_tokens=7000)
    assert s.num_predict + 7000 <= s.num_ctx + 256


def test_model_override_is_respected_but_regime_still_tuned():
    s = _spec(
        "Crea una landing moderna con glassmorphism",
        has_index=True,
        model_override="qwen2.5-coder:7b",
    )
    assert s.model == "qwen2.5-coder:7b"
    assert s.regime is Regime.CREATIVE  # regime/params still task-aware


# ── Validators ────────────────────────────────────────────────────────────

def test_validator_flags_python_syntax_error():
    bad = "```python\ndef f(:\n    pass\n```"
    r = validate_output(bad, regime="code_gen")
    assert not r.ok
    assert any("syntax" in e.lower() for e in r.errors)


def test_validator_flags_missing_deliverables():
    code = "```python\ndef add(a, b):\n    return a + b\n```"
    r = validate_output(code, regime="code_gen", deliverables=("tests", "benchmark"))
    assert "tests" in r.missing
    assert "benchmark" in r.missing


def test_validator_passes_complete_answer():
    good = (
        "```python\n"
        "import time\n"
        "def test_add():\n    assert add(1, 2) == 3\n"
        "t = time.perf_counter()  # benchmark\n"
        "```"
    )
    r = validate_output(good, regime="code_gen", deliverables=("tests", "benchmark"))
    assert r.ok


def test_validator_flags_no_code_block_for_generation():
    r = validate_output("solo texto sin código", regime="creative")
    assert not r.ok


def test_validator_html_responsive_requirement():
    html = "```html\n<html><body><h1>Hi</h1></body></html>\n```"
    r = validate_output(html, regime="creative", require_responsive=True)
    assert not r.ok
    assert any("viewport" in e.lower() for e in r.errors)


def test_validator_inline_css_needs_media_query():
    # Landing pages inline their CSS; responsive check must look inside <style>.
    html = (
        "```html\n<html><head><meta name='viewport' content='width=device-width'>"
        "<style>.hero{color:red}</style></head><body>hi</body></html>\n```"
    )
    r = validate_output(html, regime="creative", require_responsive=True)
    assert not r.ok
    assert any("@media" in e.lower() for e in r.errors)
