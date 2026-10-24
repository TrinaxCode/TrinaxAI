from __future__ import annotations

from trinaxai_cli.router import RouteContext, decide_mode, mode_label


def test_explicit_agent_phrase_routes_to_agent() -> None:
    d = decide_mode("usa el agente para arreglar el bug")
    assert d.mode == "agent"
    assert d.announce is True


def test_workspace_action_routes_to_agent() -> None:
    d = decide_mode("edita el archivo main.py y corrige el error")
    assert d.mode == "agent"


def test_hybrid_evidence_routes_to_agent_and_education_stays_chat() -> None:
    assert decide_mode("compara mis documentos con información web reciente").reason == "hybrid_evidence"
    assert decide_mode("explícame cómo editar un archivo").mode == "chat"


def test_explicit_web_search_routes_to_web() -> None:
    d = decide_mode("busca en internet el precio del bitcoin")
    assert d.mode == "web"
    assert d.web_search is True


def test_public_lookup_routes_to_web_and_personal_history_to_rag() -> None:
    d = decide_mode("busca quién es TrinaxCode")
    assert d.mode == "web"
    assert d.reason == "direct_lookup"
    assert d.web_search is True
    assert decide_mode("busca cuándo fue el último partido del Real Madrid").mode == "web"
    assert decide_mode("dime qué programas Python he hecho").mode == "rag"
    assert decide_mode("qué proyectos hice").mode == "rag"
    assert decide_mode("busca cuándo hice el proyecto Tal").mode == "rag"


def test_direct_lookup_in_local_documents_stays_local() -> None:
    assert decide_mode("busca en mis documentos el contrato").mode == "rag"


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


def test_web_creation_routes_to_agent_but_explanation_stays_chat() -> None:
    assert decide_mode("crea una página web para mi negocio").mode == "agent"
    assert decide_mode("quiero crear una página web para mi negocio").mode == "agent"
    assert decide_mode("diseña un sitio web").mode == "agent"
    assert decide_mode("explícame cómo diseñar una página web").mode == "chat"


def test_complex_research_routes_to_deep_research() -> None:
    d = decide_mode("haz una investigación compleja sobre este tema")
    assert d.mode == "deep_research"
    assert d.web_search is True
    assert d.depth == 3


def test_plain_prompt_routes_to_chat() -> None:
    d = decide_mode("hola, cómo estás")
    assert d.mode == "chat"


def test_manual_web_mode_biases_to_web() -> None:
    d = decide_mode("quién ganó el partido", RouteContext(web_mode=True))
    assert d.mode == "web"
    assert d.web_search is True


def test_local_grounding_stays_rag_when_web_mode_is_enabled() -> None:
    d = decide_mode("qué dice mi proyecto sobre la configuración", RouteContext(web_mode=True))
    assert d.mode == "rag"
    assert d.web_search is False


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


def test_a_named_file_is_a_workspace_target() -> None:
    for prompt in (
        "arregla el bug en calc.py",
        "fix the failing test in src/app.test.ts",
        "refactoriza utils/helpers.py",
        "update config.yaml with the new port",
    ):
        d = decide_mode(prompt)
        assert d.mode == "agent" and d.reason == "workspace_action", prompt


def test_reading_a_named_file_goes_to_the_agent_but_plain_reading_does_not() -> None:
    assert decide_mode("lee el archivo main.py y dime qué hace").mode == "agent"
    assert decide_mode("open README.md and summarize it").mode == "agent"
    # Reading in general, or about something, is ordinary chat; so is a framework name.
    assert decide_mode("read about the history of Rome").mode == "chat"
    assert decide_mode("lee mis archivos").mode != "agent"  # "my files" means the indexed documents
    assert decide_mode("what is the latest version of node.js").mode == "web"
    assert decide_mode("explica qué hace next.js").mode == "chat"
    assert decide_mode("install node.js on my laptop").mode == "chat"
    assert decide_mode("visit example.com/index.html").mode == "chat"


def test_version_control_orders_go_to_the_agent_but_questions_about_them_do_not() -> None:
    for prompt in (
        "commit these changes",
        "haz commit de los cambios",
        "git status",
        "git push origin main",
        "please commit my changes with a good message",
        "sube los cambios",
        "run git status and tell me what changed",
        "ejecuta git diff",
    ):
        assert decide_mode(prompt).mode == "agent", prompt
    for prompt in (
        "explain what a git commit is",
        "what is a good commit message convention?",
        "commit message conventions",
        "cómo hago un push seguro?",
        "don't push anything yet, just explain git status",
    ):
        assert decide_mode(prompt).mode == "chat", prompt
    # With documents attached the turn stays about them, as for every other workspace action.
    assert decide_mode("commit these changes", RouteContext(has_documents=True)).mode != "agent"
