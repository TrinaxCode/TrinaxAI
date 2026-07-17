"""Tests for the generation pipeline (classifier, scoring, presets, validators).

These are pure-function tests — no Ollama, no network — so they run in CI.
"""

from __future__ import annotations

import config
from app.generation import build_task_spec, classify, complexity_score, validate_output
from app.generation.prompts import CREATOR_BIO, IDENTITY_SHORT, wants_creator_bio
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


def test_knowledge_mode_forces_retrieval_without_magic_phrases():
    spec = _spec("¿Cuál es el animal guardián de Aurora?", retrieval_mode="knowledge")
    assert spec.regime is Regime.GROUNDED_QA
    assert spec.use_rag is True
    assert spec.retrieval_mode == "knowledge"
    assert spec.model == config.MODEL_FAST


def test_knowledge_mode_fails_closed_when_index_is_missing():
    spec = _spec("What is Aurora's guardian animal?", has_index=False, retrieval_mode="knowledge")
    assert spec.regime is Regime.GROUNDED_QA
    assert spec.use_rag is True


def test_model_mode_never_reenables_retrieval():
    spec = _spec(
        "según el archivo config.py qué hace make_llm en mi proyecto",
        retrieval_mode="model",
    )
    assert spec.regime is not Regime.GROUNDED_QA
    assert spec.use_rag is False
    assert spec.retrieval_mode == "model"


def test_everyday_topic_is_explain_not_grounded():
    # The old pipeline forced these through grounded-QA ("only from context").
    assert classify("dame una receta saludable de pollo").regime is Regime.EXPLAIN


def test_identity_and_creator_profile_use_official_links():
    assert "https://github.com/TrinaxCode/TrinaxAI" in IDENTITY_SHORT
    assert "https://github.com/TrinaxCode" in CREATOR_BIO
    assert "https://www.tiktok.com/@trinaxcode" in CREATOR_BIO
    assert wants_creator_bio("¿Quién es tu creador?")
    assert wants_creator_bio("compárteme sus redes")


def test_debugging_routes_to_code():
    c = classify("tengo un TypeError en mi useEffect de React, no funciona, arréglalo")
    assert c.regime is Regime.CODE_GEN
    assert "debugging" in c.categories


# ── Attached documents (PWA appends a fenced ```text dump) ────────────────

# Mirrors the PWA's document-context suffix (ChatInterface.tsx). The ```text
# fence used to set has_fence → is_code → CODE_GEN on the small coder, which
# then answered a "summarise this PDF" turn with a truncated "El".
def _with_attachment(instruction: str, name: str = "informe.pdf") -> str:
    return (
        f"{instruction}\n\n[Archivo adjunto temporal: {name}]\n"
        "```text\n"
        "def build(): pass\nimport os\nconst x = () => 1;\n"
        "Lorem ipsum dolor sit amet " * 400
        + "\n```"
    )


def test_attached_document_summary_is_explain_not_code():
    c = classify(_with_attachment("resume este documento"))
    assert c.regime is Regime.EXPLAIN
    assert not c.has_code_fence


def test_attached_document_does_not_route_to_coder():
    spec = _spec(_with_attachment("resume este documento"))
    assert spec.regime is Regime.EXPLAIN
    assert spec.model != config.MODEL_CODE
    # MODEL_FAST may intentionally alias MODEL_GENERAL on smaller installations.
    assert spec.model == config.MODEL_GENERAL


def test_attached_document_dump_does_not_inflate_score():
    # The huge file text must not push the turn into complex/deep decoding.
    lean = complexity_score("resume este documento", classify("resume este documento"))
    withdoc = complexity_score(
        "resume este documento", classify(_with_attachment("resume este documento"))
    )
    assert withdoc.mode == lean.mode


def test_attachment_with_explicit_code_fix_still_uses_code_regime():
    # A real "fix the code in this file" request keeps the coder path.
    c = classify(_with_attachment("arréglame el bug de este código y corrige el error"))
    assert c.regime is Regime.CODE_GEN


# ── Reasoning regime (maths / science / algorithm analysis) ───────────────

def test_math_exam_is_reasoning_not_code():
    # A maths exam that mentions "algoritmo", a def-snippet and "grafo" must NOT
    # be routed to the small coder model with a "produce code" prompt.
    exam = (
        "Resuelve el sistema de ecuaciones por eliminación de Gauss. Calcula el "
        "determinante de la matriz A y su inversa. Encuentra los puntos críticos "
        "de f(x)=x^4-8x^2+5. Demuestra por inducción que la suma de cubos es "
        "(n(n+1)/2)^2. Determina si el grafo posee un camino euleriano."
    )
    c = classify(exam)
    assert c.regime is Regime.REASONING
    assert "math" in c.categories


def test_algorithm_analysis_is_reasoning():
    q = (
        "Obtén la recurrencia de este merge sort, resuélvela con el Teorema "
        "Maestro y analiza la complejidad temporal y espacial. Aplica Dijkstra "
        "desde A en el grafo ponderado y muestra el árbol de caminos mínimos."
    )
    assert classify(q).regime is Regime.REASONING


def test_reasoning_uses_instruct_model_not_coder():
    exam = (
        "Demuestra que 3^(2n)-1 es divisible entre 8 para todo entero positivo n, "
        "y calcula la integral por partes de x^2 e^x entre 0 y 2."
    )
    s = _spec(exam, has_index=True)
    assert s.regime is Regime.REASONING
    assert s.model in (config.MODEL_GENERAL, config.MODEL_DEEP)
    assert s.model != config.MODEL_CODE
    assert s.use_rag is False
    assert s.num_predict >= 3072  # long problem sets are not truncated
    assert 0.0 < s.temperature <= 0.35  # not greedy, not creative-hot


def test_real_code_build_stays_code_gen():
    # The reasoning lexicon must NOT hijack a genuine "build me code" task.
    s = _spec(
        "Implementa una caché LRU + TTL en Python con O(1), tests y benchmark",
        has_index=True,
    )
    assert s.regime is Regime.CODE_GEN


def test_long_prompt_grows_window_instead_of_truncating_output():
    # A long exam prompt should grow num_ctx to protect the answer budget,
    # never silently shrink the response below a useful length.
    exam = "Resuelve la integral y demuestra por inducción. " * 120
    s = _spec(exam, has_index=True, estimated_prompt_tokens=5000)
    assert s.regime is Regime.REASONING
    assert s.num_predict >= 2048
    assert s.num_predict + 5000 <= s.num_ctx + 256


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


def test_validator_inline_css_needs_a_real_responsive_signal():
    html = (
        "```html\n<html><head><meta name='viewport' content='width=device-width'>"
        "<style>.hero{color:red}</style></head><body>hi</body></html>\n```"
    )
    r = validate_output(html, regime="creative", require_responsive=True)
    assert not r.ok
    assert any("responsive" in e.lower() for e in r.errors)


def test_validator_accepts_fluid_grid_without_media_query():
    html = (
        "```html\n<html><head><meta name='viewport' content='width=device-width'>"
        "<style>.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr))}</style>"
        "</head><body><main class='cards'></main></body></html>\n```"
    )
    assert validate_output(html, regime="creative", require_responsive=True).ok


def test_js_balance_ignores_strings_templates_comments_and_regex():
    code = """```javascript
const text = "}";
const template = `literal { [ (`;
const matcher = /[(){}]/g;
// unmatched-looking }
function ok(value) { return matcher.test(value); }
```"""
    assert validate_output(code, regime="code_gen").ok


def test_js_balance_detects_wrong_nesting_not_only_counts():
    code = "```javascript\nfunction broken() { return ([)]); }\n```"
    result = validate_output(code, regime="code_gen")
    assert not result.ok
    assert any("unexpected" in error.lower() for error in result.errors)
