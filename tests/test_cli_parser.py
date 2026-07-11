from __future__ import annotations

import unittest

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

    def test_index_accepts_positional_path(self) -> None:
        args = _build_parser().parse_args(["index", "."])
        self.assertEqual(args.command, "index")
        self.assertEqual(args.path, ".")

    def test_service_commands_parse_yes_flag(self) -> None:
        stop = _build_parser().parse_args(["stop", "--yes"])
        restart = _build_parser().parse_args(["restart", "-y"])
        self.assertTrue(stop.yes)
        self.assertTrue(restart.yes)

    def test_version_command_parses(self) -> None:
        args = _build_parser().parse_args(["version"])
        self.assertEqual(args.command, "version")


if __name__ == "__main__":
    unittest.main()
