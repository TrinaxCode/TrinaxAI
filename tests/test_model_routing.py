from __future__ import annotations

import config


def test_code_switches_to_coder_immediately() -> None:
    assert config.route_model("crea una función en Python", config.MODEL_GENERAL) == config.MODEL_CODE


def test_ambiguous_followup_keeps_warm_coder() -> None:
    assert config.route_model("hazlo más corto", config.MODEL_CODE) == config.MODEL_CODE


def test_explicit_everyday_topic_switches_back_to_general() -> None:
    assert config.route_model("cambiando de tema, dame una receta saludable", config.MODEL_CODE) == config.MODEL_GENERAL


def test_identity_question_never_uses_the_fast_route() -> None:
    assert config.route_model("quién te creó") == config.MODEL_GENERAL


def test_generic_analysis_does_not_trigger_deep_coder() -> None:
    assert config.route_model("analiza la historia de México con detalle") == config.MODEL_GENERAL


def test_conversation_router_infers_affinity_without_model_metadata() -> None:
    messages = [
        {"role": "user", "content": "corrige este error de Python"},
        {"role": "assistant", "content": "Aquí está la corrección."},
        {"role": "user", "content": "ahora hazlo más corto"},
    ]
    assert config.route_model_for_messages(messages) == config.MODEL_CODE
