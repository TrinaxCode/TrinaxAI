from trinaxai_cli.i18n import help_text, slash_help, translate


def test_common_cli_messages_are_localized() -> None:
    assert translate("No collections.", "es") == "No hay colecciones."
    assert translate("Watching 2 path(s) - 3 events", "es") == "Vigilando 2 ruta(s) - 3 eventos"
    assert translate("Exported 2 record(s) → /tmp/session.md", "es") == "Exportados 2 registro(s) -> /tmp/session.md"


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
