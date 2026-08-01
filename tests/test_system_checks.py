from __future__ import annotations

import builtins
import json
import sys
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import test_system


def test_check_python_returns_structured_result() -> None:
    results = test_system.check_python()
    assert len(results) == 1
    assert results[0].group == "Runtime"
    assert results[0].ok is (sys.version_info >= (3, 10))


def test_summary_output_does_not_raise(capsys) -> None:  # noqa: ANN001
    test_system.print_results(
        [test_system.CheckResult("example", False, "detail", "Group")],
        summary_only=True,
    )
    assert "Se encontraron 1 problemas" in capsys.readouterr().out


def test_fetch_rejects_non_http_urls() -> None:
    with patch("test_system.urllib.request.urlopen") as urlopen:
        assert test_system._fetch("file:///etc/passwd") == (-1, "")
    urlopen.assert_not_called()


def test_fetch_handles_success_http_error_transport_and_https_fallback() -> None:
    response = MagicMock()
    response.__enter__.return_value = SimpleNamespace(status=200, read=lambda: b"ok")
    with patch("test_system.urllib.request.urlopen", return_value=response):
        assert test_system._fetch("https://localhost:3333/health") == (200, "ok")

    error = urllib.error.HTTPError("https://localhost", 503, "offline", {}, None)
    error.read = lambda: b"unavailable"
    with patch("test_system.urllib.request.urlopen", side_effect=error):
        assert test_system._fetch("https://localhost") == (503, "unavailable")
    with patch("test_system.urllib.request.urlopen", side_effect=OSError("offline")):
        assert test_system._fetch("https://localhost") == (-1, "")

    with patch.object(test_system, "_fetch", side_effect=[(-1, ""), (200, "fallback")]) as fetch:
        assert test_system._fetch_with_http_fallback("https://localhost") == (200, "fallback")
    assert fetch.call_args_list[-1].args[0] == "http://localhost"


def test_ollama_rag_and_frontend_checks_cover_online_and_invalid_responses() -> None:
    models = {"models": [{"name": "model", "size": 10}]}
    with patch.object(test_system, "_fetch", return_value=(200, json.dumps(models))):
        results = test_system.check_ollama("http://localhost", verbose=True)
    assert all(result.ok for result in results)
    assert results[-1].extra == ["📦 model (10)"]

    with patch.object(test_system, "_fetch", return_value=(-1, "")):
        assert test_system.check_ollama("http://localhost")[0].ok is False
    with patch.object(test_system, "_fetch", return_value=(200, "broken")):
        assert test_system.check_ollama("http://localhost")[-1].ok is False

    health = {
        "indexed": True,
        "projects": ["docs"],
        "num_ctx": 8192,
        "rerank": True,
        "profile": "16gb",
        "models": ["model"],
    }
    with patch.object(test_system, "_fetch_with_http_fallback", return_value=(200, json.dumps(health))):
        results = test_system.check_rag("https://localhost", verbose=True)
    assert all(result.ok for result in results)
    assert results[0].extra

    with patch.object(test_system, "_fetch_with_http_fallback", return_value=(503, "")):
        assert test_system.check_rag("https://localhost")[0].ok is False
    with patch.object(test_system, "_fetch_with_http_fallback", return_value=(200, "broken")):
        assert "inválida" in test_system.check_rag("https://localhost")[0].detail
    with patch.object(test_system, "_fetch_with_http_fallback", return_value=(200, "")):
        assert test_system.check_frontend("https://localhost")[0].ok is True


def test_feature_dependencies_and_resources_degrade_without_optional_packages(monkeypatch) -> None:
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name in {"pptx", "openpyxl", "striprtf", "watchdog", "psutil"}:
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_module)
    monkeypatch.setattr(test_system.shutil, "which", lambda _name: None)
    dependencies = test_system.check_feature_dependencies()
    assert all(not result.ok for result in dependencies)

    usage = SimpleNamespace(free=1, total=100)
    monkeypatch.setattr(test_system.shutil, "disk_usage", lambda _path: usage)
    resources = test_system.check_resources()
    assert resources[0].ok is False


def test_run_checks_printing_and_main_route_flags(monkeypatch, capsys) -> None:
    ok = [test_system.CheckResult("healthy", True, group="Core")]
    failed = [test_system.CheckResult("offline", False, "start it", "Core", ["detail"])]
    monkeypatch.setattr(test_system, "check_python", lambda: ok)
    monkeypatch.setattr(test_system, "check_ollama", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(test_system, "check_rag", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(test_system, "check_frontend", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(test_system, "check_feature_dependencies", lambda: [])
    monkeypatch.setattr(test_system, "check_resources", lambda: [])
    assert test_system.run_checks(verbose=True) == ok

    test_system.print_results(ok)
    assert "Todo funciona" in capsys.readouterr().out
    test_system.print_results(failed)
    output = capsys.readouterr().out
    assert "start it" in output and "detail" in output

    assert test_system.main(["--help"]) == 0
    monkeypatch.setattr(test_system, "run_checks", lambda **_kwargs: ok)
    assert test_system.main(["--summary"]) == 0
    monkeypatch.setattr(test_system, "run_checks", lambda **_kwargs: failed)
    assert test_system.main([]) == 1
