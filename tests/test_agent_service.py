from __future__ import annotations

import asyncio
import os
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from app.routes import ROUTERS


class AgentRouteRegistrationTests(unittest.TestCase):
    def test_agent_routes_registered(self) -> None:
        paths = {r.path for router in ROUTERS for r in router.routes}
        self.assertIn("/v1/agent", paths)
        self.assertIn("/v1/agent/approve", paths)
        self.assertIn("/v1/agent/cancel", paths)


class AgentServiceHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import agent_service

        self.svc = agent_service

    def test_resolve_workspace_accepts_existing_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"TRINAXAI_AGENT_WORKSPACE_ROOTS": tmp}):
                resolved = self.svc._resolve_workspace(tmp)
                self.assertEqual(resolved, Path(tmp).resolve())

    def test_resolve_workspace_rejects_missing_dir(self) -> None:
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            self.svc._resolve_workspace("/no/such/dir/really/nope")

    def test_stalled_agent_emits_recoverable_error_and_closes(self) -> None:
        session_id, session = self.svc._register_session()
        session["last_activity"] = time.monotonic() - 10

        class _Thread:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                pass

            def join(self, timeout=None):
                pass

        request = type("Request", (), {"max_steps": 1})()
        with patch.object(self.svc, "_AGENT_STALL_SECONDS", 1), patch.object(self.svc.threading, "Thread", _Thread):
            stream = self.svc._agent_event_stream(session_id, session, request, Path.cwd(), "test-model")
            self.assertIn('"type":"start"', next(stream))
            self.assertIn('"recoverable":true', next(stream))
            self.assertEqual(next(stream), "data: [DONE]\n\n")

    def test_resolve_workspace_rejects_existing_directory_outside_allowlist(self) -> None:
        from fastapi import HTTPException

        with TemporaryDirectory() as allowed, TemporaryDirectory() as outside:
            with patch.dict(os.environ, {"TRINAXAI_AGENT_WORKSPACE_ROOTS": allowed}):
                with self.assertRaises(HTTPException) as raised:
                    self.svc._resolve_workspace(outside)
        self.assertEqual(raised.exception.status_code, 403)

    def test_resolve_workspace_accepts_descendant_of_registered_root(self) -> None:
        with TemporaryDirectory() as allowed:
            child = Path(allowed) / "project"
            child.mkdir()
            with patch.dict(os.environ, {"TRINAXAI_AGENT_WORKSPACE_ROOTS": allowed}):
                self.assertEqual(self.svc._resolve_workspace(str(child)), child.resolve())

    def test_resolve_model_prefers_request(self) -> None:
        self.assertEqual(self.svc._resolve_model("my-model"), "my-model")
        # Falls back to a configured model when not requested.
        self.assertTrue(self.svc._resolve_model(None))

    def test_resolve_model_keeps_tool_capable_general_model(self) -> None:
        with (
            patch.object(self.svc.config, "MODEL_DEEP", "coder-deep"),
            patch.object(self.svc.config, "MODEL_CODE", "coder-small"),
            patch.object(self.svc.config, "MODEL_GENERAL", "chat-small"),
        ):
            self.assertEqual(self.svc._resolve_model(None), "chat-small")

    def test_resolve_model_uses_shared_autorouter(self) -> None:
        messages = [{"role": "user", "content": "Corrige este componente de React"}]
        with patch.object(self.svc.config, "route_model_for_messages", return_value="coder-auto") as router:
            self.assertEqual(self.svc._resolve_model("auto", messages), "coder-auto")
            router.assert_called_once_with(messages)

    def test_agent_context_uses_profile_window_without_forcing_8k(self) -> None:
        with (
            patch.object(self.svc.config, "NUM_CTX", 4096),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("TRINAXAI_AGENT_NUM_CTX", None)
            self.assertEqual(self.svc._agent_num_ctx(), 4096)

    def test_safe_args_truncates_large_values(self) -> None:
        out = self.svc._safe_args({"content": "x" * 5000, "path": "a.txt"})
        self.assertTrue(out["content"].endswith("…(truncated)"))
        self.assertEqual(out["path"], "a.txt")

    def test_agent_tools_include_knowledge_search(self) -> None:
        names = [tool.name for tool in self.svc._agent_tools()]
        self.assertIn("search_knowledge", names)
        self.assertIn("read_file", names)

    def test_agent_tools_can_toggle_rag_and_web_independently(self) -> None:
        local_names = [tool.name for tool in self.svc._agent_tools(knowledge_search=False)]
        web_names = [tool.name for tool in self.svc._agent_tools(web_search=True, knowledge_search=False)]
        self.assertNotIn("search_knowledge", local_names)
        self.assertNotIn("web_search", local_names)
        self.assertNotIn("search_knowledge", web_names)
        self.assertIn("web_search", web_names)
        deep_names = [tool.name for tool in self.svc._agent_tools(deep_research=True)]
        self.assertIn("deep_research", deep_names)


class AgentBrowseTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import agent_service

        self.svc = agent_service

    def test_browse_start_dir_defaults_to_registered_root(self) -> None:
        with TemporaryDirectory() as allowed:
            with patch.dict(os.environ, {"TRINAXAI_AGENT_WORKSPACE_ROOTS": allowed}):
                self.assertEqual(self.svc._browse_start_dir(""), Path(allowed).resolve())

    def test_browse_start_dir_honours_explicit_path(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"TRINAXAI_AGENT_WORKSPACE_ROOTS": tmp}):
                self.assertEqual(self.svc._browse_start_dir(tmp), Path(tmp).resolve())


class AgentHttpYoloPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.schemas import AgentRequest
        from app.services import agent_service

        self.svc = agent_service
        self.request_model = AgentRequest

    @staticmethod
    def _request(host: str) -> MagicMock:
        request = MagicMock()
        request.client.host = host
        request.headers = {}
        return request

    def test_http_yolo_is_disabled_by_default(self) -> None:
        req = self.request_model(messages=[{"role": "user", "content": "run tests"}], yolo=True)
        with patch.dict(os.environ, {"TRINAXAI_AGENT_HTTP_YOLO": "0"}):
            with self.assertRaisesRegex(Exception, "disabled"):
                self.svc._authorize_http_yolo(req, self._request("127.0.0.1"))

    def test_http_yolo_override_is_still_local_only(self) -> None:
        from fastapi import HTTPException

        req = self.request_model(messages=[{"role": "user", "content": "run tests"}], yolo=True)
        with patch.dict(os.environ, {"TRINAXAI_AGENT_HTTP_YOLO": "1"}):
            with self.assertRaises(HTTPException) as raised:
                self.svc._authorize_http_yolo(req, self._request("192.168.1.44"))
        self.assertEqual(raised.exception.status_code, 403)

    def test_removed_remote_yolo_escape_cannot_restore_remote_execution(self) -> None:
        from fastapi import HTTPException

        req = self.request_model(messages=[{"role": "user", "content": "run tests"}], yolo=True)
        with (
            patch.dict(
                os.environ,
                {
                    "TRINAXAI_AGENT_HTTP_YOLO": "1",
                    "TRINAXAI_AGENT_REMOTE_YOLO": "1",
                },
            ),
            patch.object(self.svc, "authorize_scope"),
            self.assertRaises(HTTPException) as raised,
        ):
            self.svc._authorize_http_yolo(req, self._request("192.168.1.44"))
        self.assertEqual(raised.exception.status_code, 403)

    def test_http_yolo_explicit_local_override(self) -> None:
        req = self.request_model(messages=[{"role": "user", "content": "run tests"}], yolo=True)
        with patch.dict(os.environ, {"TRINAXAI_AGENT_HTTP_YOLO": "1"}):
            self.svc._authorize_http_yolo(req, self._request("127.0.0.1"))

    def test_agent_endpoint_rejects_yolo_before_starting_model(self) -> None:
        from app.main import app

        with TemporaryDirectory() as allowed:
            with patch.dict(
                os.environ,
                {
                    "TRINAXAI_AGENT_HTTP_YOLO": "0",
                    "TRINAXAI_AGENT_WORKSPACE_ROOTS": allowed,
                },
            ):
                response = TestClient(app, client=("127.0.0.1", 50000)).post(
                    "/v1/agent",
                    json={
                        "messages": [{"role": "user", "content": "run tests"}],
                        "workspace": allowed,
                        "yolo": True,
                    },
                )
        self.assertEqual(response.status_code, 403)


class AgentApprovalFlowTests(unittest.TestCase):
    """Exercise the approval registry without spinning up FastAPI or Ollama."""

    def setUp(self) -> None:
        from app.services import agent_service

        self.svc = agent_service

    def test_wait_for_approval_unblocks_on_decision(self) -> None:
        _, session = self.svc._register_session()

        class _Tool:
            name = "write_file"

        results: list[bool] = []

        def waiter() -> None:
            results.append(self.svc._wait_for_approval(session, _Tool(), {"path": "a.txt"}))

        thread = threading.Thread(target=waiter)
        thread.start()

        # The worker should enqueue an approval_request we can read.
        event = session["queue"].get(timeout=3)
        self.assertEqual(event["type"], "approval_request")
        approval_id = event["approval_id"]

        # Resolve it as approved and confirm the waiter returns True.
        pending = session["approvals"][approval_id]
        pending["approved"] = True
        pending["event"].set()
        thread.join(timeout=3)
        self.assertEqual(results, [True])

    def test_drop_session_releases_pending_approvals(self) -> None:
        session_id, session = self.svc._register_session()

        class _Tool:
            name = "run_command"

        results: list[bool] = []

        def waiter() -> None:
            results.append(self.svc._wait_for_approval(session, _Tool(), {"command": "ls"}))

        thread = threading.Thread(target=waiter)
        thread.start()
        session["queue"].get(timeout=3)  # drain the approval_request
        # Dropping the session must unblock the waiter as a denial.
        self.svc._drop_session(session_id)
        thread.join(timeout=3)
        self.assertEqual(results, [False])
        # Allow the daemon queue thread to settle.
        time.sleep(0.01)

    def test_drop_session_cancels_active_engine_response(self) -> None:
        session_id, session = self.svc._register_session()
        engine = MagicMock()
        session["engine"] = engine

        self.svc._drop_session(session_id)

        engine.cancel.assert_called_once_with()

    def test_approval_requires_matching_session_and_identity(self) -> None:
        from fastapi import HTTPException

        from app.schemas import AgentApprovalRequest

        session_id, session = self.svc._register_session(("device", "device-a"))
        approval_id = "a" * 32
        pending = {"event": threading.Event(), "approved": False}
        session["approvals"][approval_id] = pending
        request = MagicMock()
        request.state.trinaxai_identity = {"kind": "device", "id": "device-b"}
        payload = AgentApprovalRequest(
            session_id=session_id,
            approval_id=approval_id,
            approved=True,
        )
        with patch.object(self.svc, "_authorize_system"):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(self.svc.agent_approve(payload, request))
            self.assertEqual(raised.exception.status_code, 404)
            self.assertFalse(pending["event"].is_set())

            request.state.trinaxai_identity = {"kind": "device", "id": "device-a"}
            result = asyncio.run(self.svc.agent_approve(payload, request))
        self.assertEqual(result, {"ok": True, "approved": True})
        self.assertTrue(pending["event"].is_set())
        self.svc._drop_session(session_id)

    def test_drop_session_sets_worker_cancellation_signal(self) -> None:
        session_id, session = self.svc._register_session()
        self.assertFalse(session["cancelled"].is_set())
        self.svc._drop_session(session_id)
        self.assertTrue(session["cancelled"].is_set())

    def test_cancel_endpoint_stops_active_engine_immediately(self) -> None:
        from app.schemas import AgentCancelRequest

        session_id, session = self.svc._register_session(("device", "device-a"))
        engine = MagicMock()
        session["engine"] = engine
        request = MagicMock()
        request.state.trinaxai_identity = {"kind": "device", "id": "device-a"}

        result = asyncio.run(self.svc.agent_cancel(AgentCancelRequest(session_id=session_id), request))

        self.assertEqual(result, {"ok": True, "cancelled": True})
        self.assertTrue(session["cancelled"].is_set())
        engine.cancel.assert_called_once_with()
        self.svc._drop_session(session_id)


if __name__ == "__main__":
    unittest.main()
