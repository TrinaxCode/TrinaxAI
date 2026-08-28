from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

from trinaxai_cli.app import _build_parser


class CLIParserTests(unittest.TestCase):
    def test_default_command_is_interactive_chat(self) -> None:
        args = _build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_ask_parses_prompt(self) -> None:
        args = _build_parser().parse_args(["ask", "explica", "este", "proyecto"])
        self.assertEqual(args.command, "ask")
        self.assertEqual(args.prompt, ["explica", "este", "proyecto"])

    def test_general_chat_engine_is_available(self) -> None:
        chat = _build_parser().parse_args(["chat", "--engine", "general"])
        ask = _build_parser().parse_args(["ask", "hola", "--engine", "rag"])
        self.assertEqual(chat.engine, "general")
        self.assertEqual(ask.engine, "rag")

    def test_chat_accepts_a_local_attachment(self) -> None:
        args = _build_parser().parse_args(["chat", "--file", "photo.png", "--prompt", "describe it"])
        self.assertEqual(args.file, "photo.png")
        self.assertEqual(args.prompt, "describe it")

    def test_index_accepts_positional_path(self) -> None:
        args = _build_parser().parse_args(["index", "."])
        self.assertEqual(args.command, "index")
        self.assertEqual(args.path, ".")

    def test_export_accepts_pdf_and_word_formats(self) -> None:
        pdf = _build_parser().parse_args(["export", "--format", "pdf"])
        word = _build_parser().parse_args(["export", "--format", "word"])
        self.assertEqual(pdf.format, "pdf")
        self.assertEqual(word.format, "word")

    def test_research_accepts_a_persistent_session(self) -> None:
        args = _build_parser().parse_args(["research", "--query", "topic", "--session", "research"])
        self.assertEqual(args.session, "research")

    def test_service_commands_parse_yes_flag(self) -> None:
        stop = _build_parser().parse_args(["stop", "--yes"])
        restart = _build_parser().parse_args(["restart", "-y"])
        network = _build_parser().parse_args(["network", "refresh", "--yes"])
        self.assertTrue(stop.yes)
        self.assertTrue(restart.yes)
        self.assertEqual(network.network_command, "refresh")
        self.assertTrue(network.yes)

    def test_version_command_parses(self) -> None:
        args = _build_parser().parse_args(["version"])
        self.assertEqual(args.command, "version")

    def test_spanish_parser_errors_keep_argparse_context(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            _build_parser("es").parse_args(["ask", "--engine", "nope"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("opción inválida", stderr.getvalue())
        self.assertIn("nope", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
