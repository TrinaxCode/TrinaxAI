from __future__ import annotations

import io
import unittest
import urllib.error
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from trinaxai_cli.agent import AgentEngine, SandboxError, build_tool_map, default_system_prompt
from trinaxai_cli.agent.engine import (
    AgentCancelled,
    _code_review_evidence,
    _grounding_violations,
    _is_code_review_request,
    _is_final_answer,
    _is_simple_root_listing,
    _parse_tool_call,
    _requires_tool_action,
    _tool_calls_from_text,
)
from trinaxai_cli.agent.extract import DOCUMENT_EXTENSIONS, is_document
from trinaxai_cli.agent.tools import _resolve_in_workspace, _run_command
from trinaxai_cli.app import _build_parser

_MINIMAL_DOCX_DOCUMENT = (
    '<?xml version="1.0"?><w:document '
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>Hola desde Word TrinaxAI</w:t></w:r></w:p></w:body></w:document>"
)


def _write_minimal_docx(path: Path) -> None:
    content_types = (
        '<?xml version="1.0"?><Types '
        'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    )
    rels = (
        '<?xml version="1.0"?><Relationships '
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", _MINIMAL_DOCX_DOCUMENT)


class DocumentExtractionTests(unittest.TestCase):
    def test_is_document_detects_known_types(self) -> None:
        self.assertTrue(is_document(Path("report.pdf")))
        self.assertTrue(is_document(Path("notes.docx")))
        self.assertFalse(is_document(Path("main.py")))
        self.assertIn(".pdf", DOCUMENT_EXTENSIONS)

    def test_read_file_extracts_docx_text(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_docx(root / "d.docx")
            out = build_tool_map()["read_file"].handler(root, path="d.docx")
            self.assertIn("Hola desde Word TrinaxAI", out)

    def test_long_text_file_requires_targeted_read(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "large.py").write_text("value = 1\n" * 1000, encoding="utf-8")
            out = build_tool_map()["read_file"].handler(root, path="large.py")
            self.assertIn("Use grep", out)
            self.assertIn("Do not answer from unread lines", out)


class SandboxTests(unittest.TestCase):
    def test_relative_path_resolves_inside_root(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = _resolve_in_workspace(root, "sub/file.txt")
            self.assertTrue(str(resolved).startswith(str(root.resolve())))

    def test_parent_escape_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SandboxError):
                _resolve_in_workspace(root, "../secret.txt")

    def test_absolute_path_elsewhere_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SandboxError):
                _resolve_in_workspace(root, "/etc/passwd")


class ToolHandlerTests(unittest.TestCase):
    def test_glob_accepts_dot_slash_and_rejects_escape(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("pass\n")
            glob = build_tool_map()["glob"].handler
            self.assertEqual(glob(root, pattern="*.py"), "main.py")
            self.assertEqual(glob(root, pattern="./*.py"), "main.py")
            with self.assertRaises(SandboxError):
                glob(root, pattern="../*.py")

    def test_write_then_read_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = build_tool_map()
            out = tools["write_file"].handler(root, path="a.txt", content="hello")
            self.assertIn("created", out)
            self.assertEqual((root / "a.txt").read_text(), "hello")
            read = tools["read_file"].handler(root, path="a.txt")
            self.assertIn("hello", read)

    def test_edit_requires_unique_match(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("x x")
            tools = build_tool_map()
            out = tools["edit_file"].handler(root, path="a.txt", old="x", new="y")
            self.assertIn("matches 2 times", out)

    def test_write_outside_workspace_returns_error(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SandboxError):
                build_tool_map()["write_file"].handler(root, path="../evil.txt", content="x")

    def test_python_read_reports_complete_file_and_valid_syntax(self) -> None:
        source = (
            "import math\nimport turtle\n\n"
            "def xt(value):\n    return 16 * math.sin(value) ** 3\n\n"
            "pen = turtle.Turtle()\n"
            "for i in range(10):\n    pen.goto((xt(i), 0))\n"
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "corazon.py").write_text(source)
            result = build_tool_map()["read_file"].handler(root, path="corazon.py")

        self.assertIn("complete", result)
        self.assertIn("syntax=valid", result)
        self.assertIn("pen.goto((xt(i), 0))", result)
        self.assertIn("[end read_file: complete]", result)

    def test_python_read_includes_verified_turtle_call_semantics(self) -> None:
        source = "import turtle\npen = turtle.Turtle()\npen.speed(500)\npen.goto((1, 2))\npen.goto(0, 0)\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drawing.py").write_text(source)
            result = build_tool_map()["read_file"].handler(root, path="drawing.py")

        self.assertIn("verified local stdlib API evidence", result)
        self.assertIn("turtle.Turtle.goto", result)
        self.assertIn("a pair (tuple) of coordinates", result)
        self.assertIn("If the pen is down, a line will be drawn", result)
        self.assertIn("greater than 10", result)

    def test_python_read_reports_real_syntax_error(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broken.py").write_text("def nope(:\n    pass\n")
            result = build_tool_map()["read_file"].handler(root, path="broken.py")

        self.assertIn("syntax=invalid", result)
        self.assertIn("line 1", result)

    def test_dangerous_flags(self) -> None:
        tools = build_tool_map()
        self.assertTrue(tools["write_file"].dangerous)
        self.assertTrue(tools["edit_file"].dangerous)
        self.assertTrue(tools["run_command"].dangerous)
        self.assertFalse(tools["read_file"].dangerous)
        self.assertFalse(tools["grep"].dangerous)

    @unittest.skipUnless(Path("/usr/bin/bwrap").is_file(), "bubblewrap not installed")
    def test_run_command_cannot_read_host_paths_or_use_network(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = _run_command(
                root,
                'test ! -e /etc/passwd && test ! -e "$HOME/.ssh" && echo isolated',
            )
        self.assertIn("sandboxed, network=off", result)
        self.assertIn("isolated", result)

    def test_run_command_fails_closed_without_sandbox(self) -> None:
        with (
            TemporaryDirectory() as tmp,
            patch("trinaxai_cli.agent.tools._bubblewrap_argv", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = _run_command(Path(tmp), "echo unsafe")
        self.assertIn("terminal execution is disabled", result)
        self.assertNotIn("[exit 0", result)


class ToolCallParsingTests(unittest.TestCase):
    def test_parses_dict_arguments(self) -> None:
        name, args = _parse_tool_call({"function": {"name": "read_file", "arguments": {"path": "a.txt"}}})
        self.assertEqual(name, "read_file")
        self.assertEqual(args, {"path": "a.txt"})

    def test_parses_json_string_arguments(self) -> None:
        name, args = _parse_tool_call({"function": {"name": "grep", "arguments": '{"pattern": "todo"}'}})
        self.assertEqual(name, "grep")
        self.assertEqual(args, {"pattern": "todo"})

    def test_malformed_arguments_become_empty(self) -> None:
        _, args = _parse_tool_call({"function": {"name": "x", "arguments": "not-json"}})
        self.assertEqual(args, {})


class TextFallbackParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool_map = build_tool_map()

    def test_recovers_bare_json_tool_call(self) -> None:
        text = '{"name": "write_file", "arguments": {"path": "a.txt", "content": "hi"}}'
        calls = _tool_calls_from_text(text, self.tool_map)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "write_file")

    def test_recovers_fenced_json_tool_call(self) -> None:
        text = '```json\n{"name": "read_file", "arguments": {"path": "a.txt"}}\n```'
        calls = _tool_calls_from_text(text, self.tool_map)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["arguments"], {"path": "a.txt"})

    def test_recovers_qwen_filename_as_read_file_name(self) -> None:
        text = '```json\n{"name":"pyproject.toml","arguments":{"path":"pyproject.toml"}}\n```'
        calls = _tool_calls_from_text(text, self.tool_map)
        self.assertEqual(
            calls,
            [{"function": {"name": "read_file", "arguments": {"path": "pyproject.toml"}}}],
        )

    def test_does_not_infer_mutating_tool_from_malformed_name(self) -> None:
        text = '{"name":"a.txt","arguments":{"path":"a.txt","content":"oops"}}'
        self.assertEqual(_tool_calls_from_text(text, self.tool_map), [])

    def test_ignores_prose_and_unknown_tools(self) -> None:
        self.assertEqual(_tool_calls_from_text("Here is the plan: do things.", self.tool_map), [])
        self.assertEqual(_tool_calls_from_text('{"name": "not_a_tool", "arguments": {}}', self.tool_map), [])


class EngineConfirmationTests(unittest.TestCase):
    def _engine(self, root: Path, confirm) -> AgentEngine:
        return AgentEngine(model="test", workspace_root=root, on_confirm=confirm)

    def test_cancel_closes_active_stream(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._engine(Path(tmp), confirm=lambda tool, args: False)
            response = MagicMock()
            engine._active_response = response

            engine.cancel()

            response.close.assert_called_once_with()

    def test_denied_dangerous_action_is_not_executed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = self._engine(root, confirm=lambda tool, args: False)
            result = engine._execute_call(
                {"function": {"name": "write_file", "arguments": {"path": "a.txt", "content": "x"}}}
            )
            self.assertIn("denied", result)
            self.assertFalse((root / "a.txt").exists())

    def test_approved_dangerous_action_runs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls: list[str] = []

            def confirm(tool, args):
                calls.append(tool.name)
                return True

            engine = self._engine(root, confirm=confirm)
            result = engine._execute_call(
                {"function": {"name": "write_file", "arguments": {"path": "a.txt", "content": "hi"}}}
            )
            self.assertEqual(calls, ["write_file"])
            self.assertIn("created", result)
            self.assertEqual((root / "a.txt").read_text(), "hi")

    def test_read_only_action_skips_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("data")

            def confirm(tool, args):
                raise AssertionError("read_file must not ask for confirmation")

            engine = self._engine(root, confirm=confirm)
            result = engine._execute_call({"function": {"name": "read_file", "arguments": {"path": "a.txt"}}})
            self.assertIn("data", result)


class AgentParserTests(unittest.TestCase):
    def test_agent_command_flags(self) -> None:
        args = _build_parser().parse_args(
            ["agent", "--prompt", "do it", "--workspace", "/tmp/x", "--yolo", "--max-steps", "5"]
        )
        self.assertEqual(args.command, "agent")
        self.assertEqual(args.prompt, "do it")
        self.assertEqual(args.workspace, "/tmp/x")
        self.assertTrue(args.yolo)
        self.assertEqual(args.max_steps, 5)


class MeaningfulAnswerTests(unittest.TestCase):
    def test_simple_root_listing_is_identified_for_early_stop(self) -> None:
        self.assertTrue(
            _is_simple_root_listing([{"role": "user", "content": "Lista los archivos de la raíz sin subcarpetas"}])
        )
        self.assertFalse(_is_simple_root_listing([{"role": "user", "content": "Crea un archivo en la raíz"}]))

    def test_creation_and_improvement_requests_require_tools(self) -> None:
        for prompt in (
            "Crea una página web de cumpleaños",
            "Mejora mucho más la web para que sea increíble",
            "Improve the website project",
        ):
            self.assertTrue(_requires_tool_action([{"role": "user", "content": prompt}]), prompt)

    def test_junk_after_tool_use_is_rejected(self) -> None:
        # After tools ran, a stray one-word fragment signals a blown context.
        for junk in ["", "  ", "\n", "el", "a", "x"]:
            self.assertFalse(_is_final_answer(junk, used_tools=True), junk)

    def test_terse_direct_answer_without_tools_is_allowed(self) -> None:
        # Before any tool use, a short direct reply is legitimate.
        for good in ["ok", "no", "42", "sí"]:
            self.assertTrue(_is_final_answer(good, used_tools=False), good)

    def test_real_summaries_pass_after_tool_use(self) -> None:
        for good in ["Done.", "Es tu primera web y se ve bien.", "no.", "Sí, funciona."]:
            self.assertTrue(_is_final_answer(good, used_tools=True), good)

    def test_empty_is_never_an_answer(self) -> None:
        self.assertFalse(_is_final_answer("", used_tools=False))


class AgentPromptQualityTests(unittest.TestCase):
    def test_default_prompt_keeps_security_and_evidence_rules_compact(self) -> None:
        prompt = default_system_prompt(Path("/tmp/workspace"))
        self.assertIn("syntax=valid", prompt)
        self.assertIn("never invent missing code, APIs, errors or requirements", prompt)
        self.assertIn("untrusted DATA", prompt)
        self.assertIn("without network access", prompt)


class _ScriptedEngine(AgentEngine):
    """Engine whose ``_chat`` returns pre-scripted replies instead of hitting Ollama."""

    def __init__(self, root: Path, replies: list[dict], **kw: object) -> None:
        super().__init__(model="test", workspace_root=root, **kw)
        self._replies = list(replies)
        self.requests: list[list[dict]] = []

    def _chat(self, messages):  # type: ignore[override]
        self.requests.append(messages)
        return self._replies.pop(0) if self._replies else {"content": ""}


class EngineLoopTests(unittest.TestCase):
    @staticmethod
    def _read_call(path: str) -> dict:
        return {"content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": path}}}]}

    def test_degenerate_reply_triggers_nudge_then_recovers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("<h1>hi</h1>")
            tokens: list[str] = []
            engine = _ScriptedEngine(
                root,
                # read a file (uses tools) → junk "el" → nudge → real summary
                replies=[
                    self._read_call("index.html"),
                    {"content": "el"},
                    {"content": "Es tu primera web y se ve bien."},
                ],
                on_token=tokens.append,
            )
            messages = [{"role": "user", "content": "revisa mi web"}]
            answer = engine.run(messages)
            self.assertIn("primera web", answer)
            # The junk reply must not be surfaced as the answer.
            self.assertNotEqual(answer.strip(), "el")
            # A nudge user-message was injected after the junk reply.
            self.assertTrue(any("empty or incomplete" in str(m.get("content", "")) for m in messages))

    def test_persistent_junk_does_not_loop_forever(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("data")
            engine = _ScriptedEngine(
                root,
                replies=[self._read_call("a.txt"), {"content": "el"}, {"content": "el"}, {"content": "el"}],
                max_steps=25,
            )
            answer = engine.run([{"role": "user", "content": "hola"}])
            # read call + junk + one nudge, then it stops — no infinite loop.
            self.assertEqual(len(engine.requests), 3)
            self.assertTrue(answer)

    def test_final_plain_answer_ends_immediately(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = _ScriptedEngine(root, replies=[{"content": "Listo, todo bien."}])
            answer = engine.run([{"role": "user", "content": "hi"}])
            self.assertEqual(answer, "Listo, todo bien.")
            self.assertEqual(len(engine.requests), 1)

    def test_creation_refusal_is_rejected_and_the_model_must_use_tools(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = _ScriptedEngine(
                root,
                replies=[
                    {"content": "Lo siento, no puedo crear una página web."},
                    {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "write_file",
                                    "arguments": {
                                        "path": "index.html",
                                        "content": "<h1>Feliz cumpleaños</h1>",
                                    },
                                }
                            }
                        ],
                    },
                    {"content": "Creé y mejoré la página de cumpleaños."},
                ],
            )

            answer = engine.run([{"role": "user", "content": "Crea una página web de cumpleaños"}])

            self.assertTrue((root / "index.html").exists())
            self.assertIn("Creé", answer)
            self.assertTrue(
                any("You do have file and shell tools" in str(m.get("content", "")) for m in engine.requests[1])
            )

    def test_standalone_file_creation_finishes_without_a_summary_inference(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = _ScriptedEngine(
                root,
                replies=[
                    {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "write_file",
                                    "arguments": {
                                        "path": "clima.md",
                                        "content": "# Calentamiento global",
                                    },
                                }
                            }
                        ],
                    },
                ],
                on_confirm=None,
            )

            answer = engine.run(
                [{"role": "user", "content": "Crea un archivo clima.md que explique el calentamiento global"}]
            )

            self.assertEqual(answer, "Archivo creado: `clima.md`.")
            self.assertEqual(len(engine.requests), 1)
            self.assertTrue((root / "clima.md").exists())

    def test_terse_answer_without_tools_is_accepted(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = _ScriptedEngine(root, replies=[{"content": "ok"}])
            answer = engine.run([{"role": "user", "content": "¿listo?"}])
            self.assertEqual(answer, "ok")
            self.assertEqual(len(engine.requests), 1)

    def test_code_review_draft_is_replaced_by_verified_answer(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "corazon.py").write_text("t = turtle.Turtle()\nt.goto((1, 2))\n")

            class _VerifiedEngine(_ScriptedEngine):
                verifier_payload: dict | None = None

                def _post(self, url, payload):  # type: ignore[override]
                    self.verifier_payload = payload
                    return {"message": {"content": "La sintaxis es válida; goto acepta la tupla."}}

            engine = _VerifiedEngine(
                root,
                replies=[
                    self._read_call("corazon.py"),
                    {"content": "Error falso: Turtle necesita argumentos."},
                ],
                verifier_model="coder-test",
            )
            answer = engine.run([{"role": "user", "content": "Revisa corazon.py"}])

            self.assertEqual(answer, "La sintaxis es válida; goto acepta la tupla.")
            self.assertIsNotNone(engine.verifier_payload)
            audit_text = engine.verifier_payload["messages"][-1]["content"]
            self.assertIn("syntax=valid", audit_text)
            self.assertIn("UNTRUSTED DRAFT", audit_text)

    def test_contradictory_verifier_is_replaced_by_safe_turtle_review(self) -> None:
        root = Path(__file__).parent / "fixtures" / "agent_reviews"

        class _WrongVerifier(_ScriptedEngine):
            def _post(self, url, payload):  # type: ignore[override]
                return {
                    "message": {
                        "content": (
                            "Error de sintaxis: xt recibe el objeto Turtle, goto no acepta una tupla "
                            "y volver al origen borra el trazo."
                        )
                    }
                }

        engine = _WrongVerifier(
            root,
            replies=[
                self._read_call("corazon.py"),
                {"content": "El regreso al origen borra todo el dibujo."},
            ],
            verifier_model="coder-test",
        )
        answer = engine.run([{"role": "user", "content": "Opina y revisa corazon.py"}])

        self.assertIn("sintaxis Python válida", answer)
        self.assertIn("no borra el trazo", answer)
        self.assertIn("`xt(i)` y `yt(i)` reciben el entero", answer)
        self.assertNotIn("no acepta una tupla", answer)


class CodeReviewRoutingTests(unittest.TestCase):
    def test_detects_spanish_and_english_review_requests(self) -> None:
        self.assertTrue(_is_code_review_request([{"role": "user", "content": "Revisa app.py"}]))
        self.assertTrue(_is_code_review_request([{"role": "user", "content": "Review app.py"}]))
        self.assertFalse(_is_code_review_request([{"role": "user", "content": "Crea app.py"}]))
        self.assertFalse(_is_code_review_request([{"role": "user", "content": "Analiza los problemas del clima"}]))

    def test_evidence_labels_tool_with_its_arguments(self) -> None:
        messages = [
            {"role": "user", "content": "Revisa corazon.py"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "corazon.py"}}}],
            },
            {"role": "tool", "content": "[complete; syntax=valid]\n1\tprint('ok')"},
        ]
        evidence = _code_review_evidence(messages)
        self.assertIn('read_file({"path": "corazon.py"})', evidence)
        self.assertIn("syntax=valid", evidence)

    def test_rejects_the_reported_false_turtle_diagnostics(self) -> None:
        root = Path(__file__).parent / "fixtures" / "agent_reviews"
        source_evidence = build_tool_map()["read_file"].handler(root, path="corazon.py")
        evidence = f"[USER REQUEST]\nRevisa los problemas\n\n[TOOL RESULT]\n{source_evidence}"
        false_answer = (
            "Hay un error de sintaxis. xt(t) recibe el objeto Turtle, goto no acepta una tupla "
            "y volver al origen borra el dibujo, por lo que no queda ningún trazo."
        )

        violations = _grounding_violations(false_answer, evidence)

        self.assertIn("contradicts valid syntax", violations)
        self.assertIn("contradicts goto tuple signature", violations)
        self.assertIn("contradicts goto drawing semantics", violations)
        self.assertIn("contradicts call-site arguments", violations)


class StreamingChatTests(unittest.TestCase):
    """Exercise the NDJSON streaming path with a stubbed Ollama response."""

    class _FakeResponse:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter(self._lines)

    def _run_stream(self, root: Path, lines: list[bytes], tokens: list[str]):
        import urllib.request

        engine = AgentEngine(model="test", workspace_root=root, on_token=tokens.append)
        original = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: self._FakeResponse(lines)  # type: ignore[assignment]
        try:
            return engine._chat_stream("http://x/api/chat", {"stream": True})
        finally:
            urllib.request.urlopen = original

    def test_prose_stream_emits_tokens(self) -> None:
        with TemporaryDirectory() as tmp:
            tokens: list[str] = []
            lines = [
                b'{"message":{"content":"Hola "}}',
                b'{"message":{"content":"mundo"}}',
                b'{"message":{"content":""},"done":true}',
            ]
            msg = self._run_stream(Path(tmp), lines, tokens)
            self.assertEqual(msg["content"], "Hola mundo")
            # Deltas are emitted live as they arrive, not buffered into one chunk.
            self.assertEqual(tokens, ["Hola ", "mundo"])
            self.assertTrue(msg["_streamed"])

    def test_tool_call_stream_does_not_emit_prose(self) -> None:
        with TemporaryDirectory() as tmp:
            tokens: list[str] = []
            lines = [
                b'{"message":{"content":""}}',
                b'{"message":{"tool_calls":[{"function":{"name":"read_file","arguments":{"path":"a"}}}]}}',
                b'{"message":{"content":""},"done":true}',
            ]
            msg = self._run_stream(Path(tmp), lines, tokens)
            self.assertEqual(tokens, [])  # tool calls are not user-facing prose
            self.assertEqual(len(msg["tool_calls"]), 1)

    def test_fenced_json_fallback_tool_call_is_not_streamed(self) -> None:
        with TemporaryDirectory() as tmp:
            tokens: list[str] = []
            lines = [
                b'{"message":{"content":"```json\\n"}}',
                b'{"message":{"content":"{\\"name\\":\\"read_file\\",\\"arguments\\":{\\"path\\":\\"a.txt\\"}}"}}',
                b'{"message":{"content":"\\n```"},"done":true}',
            ]
            msg = self._run_stream(Path(tmp), lines, tokens)
            self.assertEqual(tokens, [])
            self.assertFalse(msg["_streamed"])

    def test_fenced_json_final_answer_is_emitted_after_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            tokens: list[str] = []
            lines = [
                b'{"message":{"content":"```json\\n{\\"answer\\":42}\\n```"},"done":true}',
            ]
            msg = self._run_stream(Path(tmp), lines, tokens)
            self.assertEqual(tokens, ['```json\n{"answer":42}\n```'])
            self.assertTrue(msg["_streamed"])

    def test_streamed_final_answer_is_not_double_emitted(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            emitted: list[str] = []

            class _StreamOnce(AgentEngine):
                def _chat(self, messages):  # type: ignore[override]
                    self.on_token("streamed answer")
                    return {"role": "assistant", "content": "streamed answer", "_streamed": True}

            engine = _StreamOnce(model="t", workspace_root=root, on_token=emitted.append)
            answer = engine.run([{"role": "user", "content": "hi"}])
            self.assertEqual(answer, "streamed answer")
            # Emitted exactly once (by _chat), not twice (run must not re-emit).
            self.assertEqual(emitted, ["streamed answer"])


class ContextBudgetTests(unittest.TestCase):
    def _engine(self, root: Path, num_ctx: int) -> AgentEngine:
        return AgentEngine(model="test", workspace_root=root, num_ctx=num_ctx)

    def test_short_history_is_untouched(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._engine(Path(tmp), num_ctx=8192)
            messages = [
                {"role": "user", "content": "task"},
                {"role": "assistant", "content": "working"},
                {"role": "tool", "content": "small result"},
            ]
            fitted = engine._fit_to_budget(messages)
            self.assertEqual(len(fitted), 3)

    def test_oversized_history_is_pruned_but_keeps_task(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._engine(Path(tmp), num_ctx=2048)
            big = "x" * 20_000
            messages = [{"role": "user", "content": "THE TASK"}]
            for i in range(10):
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": f"f{i}"}}}],
                    }
                )
                messages.append({"role": "tool", "content": big})
            fitted = engine._fit_to_budget(messages)
            total = sum(len(str(m.get("content") or "")) for m in fitted)
            # Pruned well under the raw size…
            self.assertLess(total, len(big) * 10)
            # …but the original task survives as an anchor.
            self.assertTrue(any(m.get("content") == "THE TASK" for m in fitted))
            # …and no orphan tool message leads the pruned list.
            self.assertNotEqual(fitted[0].get("role"), "tool")

    def test_single_huge_tool_result_is_clipped(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._engine(Path(tmp), num_ctx=4096)
            clipped = engine._clip_message({"role": "tool", "content": "y" * 500_000})
            self.assertLess(len(clipped["content"]), 500_000)
            self.assertIn("clipped", clipped["content"])

    def test_system_prompt_requires_follow_up_for_clipped_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            prompt = default_system_prompt(Path(tmp))
            self.assertIn("never answer from missing content", prompt)
            self.assertIn("Grep only locates evidence", prompt)

    def test_ollama_http_error_surfaces_response_body(self) -> None:
        error = urllib.error.HTTPError(
            "http://ollama/api/chat",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error":"invalid think/tools combination"}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "invalid think/tools combination"):
                AgentEngine._post("http://ollama/api/chat", {"model": "test"})

    def test_single_huge_document_turn_is_clipped_at_both_ends(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._engine(Path(tmp), num_ctx=4096)
            content = "QUESTION\n" + ("x" * 500_000) + "\nLAST PAGE"
            clipped = engine._clip_message({"role": "user", "content": content})
            self.assertLess(len(clipped["content"]), len(content))
            self.assertTrue(clipped["content"].startswith("QUESTION"))
            self.assertTrue(clipped["content"].endswith("LAST PAGE"))
            self.assertIn("clipped", clipped["content"])


class AgentCancellationTests(unittest.TestCase):
    def test_cancelled_run_stops_before_contacting_model(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = AgentEngine(
                model="test",
                workspace_root=Path(tmp),
                should_cancel=lambda: True,
            )
            with self.assertRaises(AgentCancelled):
                engine.run([{"role": "user", "content": "do work"}])


if __name__ == "__main__":
    unittest.main()
