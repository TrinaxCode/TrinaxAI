from __future__ import annotations

from trinaxai_cli.router import RouteContext, decide_mode, mode_label


def test_explicit_agent_phrase_routes_to_agent() -> None:
    d = decide_mode("usa el agente para arreglar el bug")
    assert d.mode == "agent"
    assert d.announce is True


def test_workspace_action_routes_to_agent() -> None:
    d = decide_mode("edita el archivo main.py y corrige el error")
    assert d.mode == "agent"


def test_explicit_web_search_routes_to_web() -> None:
    d = decide_mode("busca en internet el precio del bitcoin")
    assert d.mode == "web"
    assert d.web_search is True


def test_current_info_routes_to_web() -> None:
    d = decide_mode("cuáles son las noticias de hoy")
    assert d.mode == "web"
    assert d.web_search is True


def test_deep_research_phrase_routes_to_deep_research() -> None:
    d = decide_mode("investiga a fondo el impacto del cambio climático")
    assert d.mode == "deep_research"
    assert d.depth == 3


def test_local_grounding_routes_to_rag() -> None:
    d = decide_mode("según mis documentos indexados, qué dice el contrato")
    assert d.mode == "rag"


def test_plain_prompt_routes_to_chat() -> None:
    d = decide_mode("hola, cómo estás")
    assert d.mode == "chat"


def test_manual_web_mode_biases_to_web() -> None:
    d = decide_mode("quién ganó el partido", RouteContext(web_mode=True))
    assert d.mode == "web"
    assert d.web_search is True


def test_manual_research_and_web_becomes_deep_web() -> None:
    d = decide_mode("analiza esto", RouteContext(web_mode=True, research_mode=True))
    assert d.mode == "deep_research"
    assert d.web_search is True
    assert d.depth == 3


def test_engine_rag_defaults_to_rag_when_no_rule_matches() -> None:
    d = decide_mode("resume el tema", RouteContext(engine="rag"))
    assert d.mode == "rag"


def test_agent_action_with_documents_stays_out_of_agent() -> None:
    d = decide_mode("edita el archivo", RouteContext(has_documents=True))
    assert d.mode != "agent"


def test_english_prompts_route_like_spanish() -> None:
    assert decide_mode("search the web for the latest news").mode == "web"
    assert decide_mode("fix the file src/main.py").mode == "agent"
    assert decide_mode("research thoroughly this topic").mode == "deep_research"


def test_mode_label_is_bilingual() -> None:
    assert mode_label("web", "es") == "búsqueda web"
    assert mode_label("web", "en") == "web search"
