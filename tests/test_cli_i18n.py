from trinaxai_cli.i18n import help_text, slash_help, translate


def test_common_cli_messages_are_localized() -> None:
    assert translate("No collections.", "es") == "No hay colecciones."
    assert translate("Watching 2 path(s) - 3 events", "es") == "Vigilando 2 ruta(s) - 3 eventos"
    assert translate("Exported 2 record(s) → /tmp/session.md", "es") == "Exportados 2 registro(s) -> /tmp/session.md"
    assert (
        translate("Stopping all TrinaxAI services including the PWA...", "es")
        == "Deteniendo todos los servicios de TrinaxAI, incluida la PWA..."
    )
    assert translate("service action failed: stop-all", "es") == "Falló la acción del servicio: stop-all"


def test_slash_help_has_both_languages() -> None:
    assert "Slash commands:" in slash_help("en")
    assert "Comandos slash:" in slash_help("es")
    assert "/research" in slash_help("en")
    assert "/research" in slash_help("es")


def test_help_text_translates_argparse_prose_and_keeps_flags() -> None:
    rendered = help_text(
        "RAG API base URL (overrides config). --lang en\nmcp ==SUPPRESS==\n",
        "es",
    )

    assert "URL base de la API RAG" in rendered
    assert "--lang en" in rendered
    assert "mcp ==SUPPRESS==" not in rendered


def test_help_text_hides_reserved_commands_in_english_too() -> None:
    assert "mcp ==SUPPRESS==" not in help_text("positional arguments:\n  mcp ==SUPPRESS==\n", "en")


def test_wrapped_argparse_help_is_localized() -> None:
    wrapped = "default asks before changes; accept-edits auto-\napproves file edits; plan blocks changes."
    rendered = help_text(wrapped, "es")

    assert "default pregunta antes de cambiar" in rendered
    assert "accept-edits" in rendered


def test_every_subcommand_help_is_fully_spanish() -> None:
    import argparse

    from trinaxai_cli.app import _build_parser

    def walk(parser: argparse.ArgumentParser):
        yield parser
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    yield from walk(child)

    for parser in walk(_build_parser("es")):
        rendered = parser.format_help()
        for english in ("Comma-separated", "Replace the permissions", "default asks"):
            assert english not in " ".join(rendered.split()), (parser.prog, english)


def test_table_headers_status_and_pinned_agent_lines_are_localized() -> None:
    assert translate("created", "es") == "creado"
    assert translate("file", "es") == "archivo"
    assert translate("AI boot preference: on", "es") == "Preferencia de arranque de la IA: activada"
    assert translate("AI boot preference: off", "es") == "Preferencia de arranque de la IA: desactivada"
    assert (
        translate("Agent mode pinned | Workspace: /w | confirm each action", "es")
        == "Modo agente fijado | Workspace: /w | confirmar cada acción"
    )


def test_command_failure_labels_and_model_states_are_localized() -> None:
    assert translate("Memory list", "es") == "Memoria listar"
    assert translate("Pair revoke", "es") == "Emparejar revocar"
    assert translate("Browse list-files", "es") == "Explorar listar archivos"
    assert translate("Import vault", "es") == "Importar vault"
    assert translate("Memory list", "en") == "Memory list"
    assert translate("installed", "es") == "instalado"
    assert translate("recommended", "es") == "recomendado"
