from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.evaluation import rag_metrics
from app.generation import classifier, presets, prompts, scoring
from app.generation.spec import Regime, TaskSpec
from app.routes import pairing
from app.schemas import (
    AgentRequest,
    AppStateOperation,
    AppStateRequest,
    ChatRequest,
    MemoryCreateRequest,
    MemoryUpdateRequest,
)
from app.security import admin_auth, device_auth


def _request(path: str = "/", *, client: str = "127.0.0.1", method: str = "GET", headers=None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "scheme": "http",
            "server": ("localhost", 3333),
            "client": (client, 50000),
            "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
        }
    )


def test_metrics_reject_invalid_shapes_and_support_empty_latency(tmp_path) -> None:
    assert rag_metrics._source_id("Source.md") == "source.md"
    assert rag_metrics._source_id({"unknown": "value"}) == ""

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="cases array"):
        rag_metrics.load_golden_set(invalid)

    invalid.write_text(json.dumps({"cases": [None]}), encoding="utf-8")
    with pytest.raises(ValueError, match="case 0"):
        rag_metrics.load_golden_set(invalid)

    invalid.write_text(json.dumps({"cases": [{"id": "", "query": ""}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        rag_metrics.load_golden_set(invalid)

    with pytest.raises(ValueError, match="positive"):
        rag_metrics.evaluate_results({"cases": []}, {}, k_values=())
    report = rag_metrics.evaluate_results({"cases": []}, {}, k_values=(1,))
    assert "performance" not in report
    assert rag_metrics._percentile([], 0.5) is None


def test_classifier_and_scoring_cover_list_history_and_frontend_paths() -> None:
    assert classifier.strip_attachment_context("") == ""
    assert classifier._count_requirements("- one\n2. two") == 2
    assert "architecture" in classifier.classify("diseña la arquitectura del servicio").categories
    assert classifier.classify("python").regime is Regime.CODE_GEN
    assert classifier.classify("¿puedes revisar esto?", "implementa en python").regime is Regime.CODE_GEN

    assert scoring._scale(1, 0, 10) == 0
    assert scoring.ScoreBreakdown(60, 0, 0, 0, 0, 0, 0, 0).mode == "complex"
    assert scoring.ScoreBreakdown(81, 0, 0, 0, 0, 0, 0, 0).mode == "deep"
    frontend = classifier.Classification(
        categories=frozenset({"frontend"}),
        regime=Regime.EXPLAIN,
        is_code=False,
        is_generation=False,
        has_code_fence=False,
    )
    assert scoring.complexity_score("crea una interfaz visual", frontend).creativity > 0


def test_prompt_variants_and_task_spec_edges(monkeypatch) -> None:
    rendered = prompts.build_generation_prompt(
        Regime.EXPLAIN,
        "Explain this",
        language_instruction="Answer in English.",
        include_creator_bio=True,
    )
    assert prompts.CREATOR_BIO in rendered
    assert "Answer in English." in rendered
    assert prompts.grounded_template(include_creator_bio=True) is not prompts.GROUNDED_QA_TEMPLATE

    assert TaskSpec(model="m", regime=Regime.EXPLAIN).llm_kwargs()["num_ctx"] == 8192
    assert "cats=[-]" in TaskSpec(model="m", regime=Regime.EXPLAIN).describe()
    with pytest.raises(ValueError, match="Unsupported retrieval"):
        presets.build_task_spec([{"role": "user", "content": "hello"}], retrieval_mode="bad")

    monkeypatch.setattr(presets.config, "GEN_NUM_CTX_MAX", 512)
    monkeypatch.setenv("TRINAXAI_GEN_NUM_CTX_MAX", "512")
    monkeypatch.setenv("TRINAXAI_GEN_NUM_PREDICT", "512")
    with pytest.raises(ValueError, match="context is too small"):
        presets.build_task_spec(
            [{"role": "user", "content": "hello"}],
            estimated_prompt_tokens=400,
        )


def test_proxy_authorization_edges_and_replay_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINAXAI_PROXY_SECRET_FILE", str(tmp_path / "proxy-secret"))
    monkeypatch.delenv("TRINAXAI_PROXY_SECRET", raising=False)
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", None)
    secret_file = tmp_path / "proxy-secret"
    secret_file.write_text("file-secret", encoding="utf-8")
    monkeypatch.setattr(admin_auth.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("readonly")))
    assert admin_auth._load_proxy_secret() == b"file-secret"

    admin_auth._PROXY_SEEN_NONCES.clear()
    monkeypatch.setattr(admin_auth.time, "time", lambda: 100)
    admin_auth._PROXY_SEEN_NONCES["expired"] = 99
    admin_auth._consume_proxy_nonce("fresh", 100)
    assert "expired" not in admin_auth._PROXY_SEEN_NONCES
    monkeypatch.setattr(admin_auth, "_PROXY_NONCE_CACHE_MAX", 1)
    with pytest.raises(HTTPException, match="cache is full"):
        admin_auth._consume_proxy_nonce("another", 100)

    client_ip = "192.168.1.12"
    now = str(100)

    def signed(timestamp: str, nonce: str, signature: str | None = None):
        value = signature or admin_auth._proxy_signature(b"secret", client_ip, timestamp, nonce, "GET", "/")
        return _request(
            headers={
                admin_auth._PROXY_HEADER: "v1",
                admin_auth._PROXY_CLIENT_HEADER: client_ip,
                admin_auth._PROXY_TIMESTAMP_HEADER: timestamp,
                admin_auth._PROXY_NONCE_HEADER: nonce,
                admin_auth._PROXY_SIGNATURE_HEADER: value,
            }
        )

    monkeypatch.setattr(admin_auth.time, "time", lambda: 100)
    monkeypatch.setattr(admin_auth, "_load_proxy_secret", lambda: b"secret")
    with pytest.raises(HTTPException, match="Expired"):
        admin_auth._verified_proxy_client(signed("1", "b" * 32), "127.0.0.1")
    with pytest.raises(HTTPException, match="Invalid"):
        admin_auth._verified_proxy_client(signed(now, "bad"), "127.0.0.1")
    monkeypatch.setattr(admin_auth, "_load_proxy_secret", lambda: b"")
    with pytest.raises(HTTPException, match="not configured"):
        admin_auth._verified_proxy_client(signed(now, "c" * 32), "127.0.0.1")

    called: list[str] = []
    monkeypatch.setattr(admin_auth, "authorize_scope", lambda _request, scope: called.append(scope))
    admin_auth.authorize_lan_or_scope(_request(headers={"X-Admin-Token": "admin"}), "web")
    assert called == ["web"]


def test_proxy_secret_creation_races_and_failures(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "race-secret"
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", None)
    monkeypatch.setattr(admin_auth, "_proxy_secret_path", lambda: path)
    real_open = admin_auth.os.open
    first = True

    def race_open(candidate, *args, **kwargs):
        nonlocal first
        if candidate == path and first:
            first = False
            path.write_text("race-secret", encoding="utf-8")
            raise FileExistsError
        return real_open(candidate, *args, **kwargs)

    monkeypatch.setattr(admin_auth.os, "open", race_open)
    assert admin_auth._load_proxy_secret() == b"race-secret"

    failed = tmp_path / "failed-secret"
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", None)
    monkeypatch.setattr(admin_auth, "_proxy_secret_path", lambda: failed)
    monkeypatch.setattr(admin_auth.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")))
    assert admin_auth._load_proxy_secret() == b""


def test_device_storage_and_authentication_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TRINAXAI_DEVICE_REGISTRY", raising=False)
    monkeypatch.delenv("TRINAXAI_DEVICE_SECRET_FILE", raising=False)
    assert device_auth._registry_path().name == "device_pairing.json"
    assert device_auth._secret_path().name == ".device_secret"

    monkeypatch.setenv("TRINAXAI_DEVICE_REGISTRY", "relative/registry.json")
    monkeypatch.setenv("TRINAXAI_DEVICE_SECRET_FILE", "relative/secret")
    assert device_auth._registry_path().parts[-2:] == ("relative", "registry.json")
    assert device_auth._secret_path().parts[-2:] == ("relative", "secret")

    secret = tmp_path / "secret"
    monkeypatch.setattr(device_auth.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(device_auth.DeviceRegistryError, match="could not be created"):
        device_auth._ensure_private_secret(secret)

    race = tmp_path / "race"
    real_open = device_auth.os.open
    first = True

    def race_open(candidate, *args, **kwargs):
        nonlocal first
        if candidate == race and first:
            first = False
            race.write_text("00" * 32, encoding="ascii")
            raise FileExistsError
        return real_open(candidate, *args, **kwargs)

    monkeypatch.setattr(device_auth.os, "open", race_open)
    assert device_auth._ensure_private_secret(race) == bytes(32)

    invalid_registry = tmp_path / "invalid-registry.json"
    invalid_registry.write_text(json.dumps({"schema_version": 0, "devices": {}, "pairing_codes": {}}), encoding="utf-8")
    with pytest.raises(device_auth.DeviceRegistryError, match="Unsupported"):
        device_auth._read_registry(invalid_registry)
    valid_registry = tmp_path / "valid-registry.json"
    valid_registry.write_text(json.dumps(device_auth._empty_registry()), encoding="utf-8")
    monkeypatch.setattr(device_auth.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("readonly")))
    assert device_auth._read_registry(valid_registry)["devices"] == {}


def test_device_token_returns_none_for_missing_bad_expired_and_broken_records(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    secret = tmp_path / "secret"
    monkeypatch.setenv("TRINAXAI_DEVICE_REGISTRY", str(registry))
    monkeypatch.setenv("TRINAXAI_DEVICE_SECRET_FILE", str(secret))
    with pytest.raises(PermissionError):
        device_auth.claim_pairing_code("bad", "Phone")

    claim = device_auth.create_pairing_code(["chat"], now=100)
    issued = device_auth.claim_pairing_code(claim["code"], "Phone", now=101)
    token = issued["token"]
    document = json.loads(registry.read_text(encoding="utf-8"))
    document["devices"].clear()
    registry.write_text(json.dumps(document), encoding="utf-8")
    assert device_auth.authenticate_device_token(token, "chat", now=102) is None

    claim = device_auth.create_pairing_code(["chat"], now=200)
    issued = device_auth.claim_pairing_code(claim["code"], "Phone", now=201)
    token = issued["token"]
    document = json.loads(registry.read_text(encoding="utf-8"))
    device = document["devices"][issued["device"]["id"]]
    device["token_hash"] = "wrong"
    registry.write_text(json.dumps(document), encoding="utf-8")
    assert device_auth.authenticate_device_token(token, "chat", now=202) is None

    claim = device_auth.create_pairing_code(["chat"], now=300)
    issued = device_auth.claim_pairing_code(claim["code"], "Phone", now=301)
    token = issued["token"]
    document = json.loads(registry.read_text(encoding="utf-8"))
    document["devices"][issued["device"]["id"]]["expires_at"] = 301
    registry.write_text(json.dumps(document), encoding="utf-8")
    assert device_auth.authenticate_device_token(token, "chat", now=302) is None

    monkeypatch.setattr(
        device_auth,
        "_ensure_private_secret",
        lambda _path: (_ for _ in ()).throw(device_auth.DeviceRegistryError("down")),
    )
    assert device_auth.authenticate_device_token("txd_" + "a" * 24 + "_" + "b" * 40, "chat", now=1) is None


def test_schema_and_pairing_validation_edges() -> None:
    with pytest.raises(ValueError):
        ChatRequest.validate_messages([None])
    with pytest.raises(ValueError, match="Conversation is too large"):
        ChatRequest(messages=[{"role": "user", "content": "x" * 70_000}] * 3)

    with pytest.raises(ValueError, match="base_revision"):
        AppStateRequest(operations=[AppStateOperation(op="set", key="tc-test", value="value")])

    for messages in (
        [{"role": "other", "content": "x"}],
        [{"role": "user", "content": 1}],
    ):
        with pytest.raises(ValueError):
            AgentRequest(messages=messages)
    with pytest.raises(ValueError):
        AgentRequest.validate_messages([None])
    with pytest.raises(ValueError, match="Conversation is too large"):
        AgentRequest(messages=[{"role": "user", "content": "x" * 70_000}] * 3)

    assert MemoryCreateRequest(text="fact", tags=None).tags is None
    assert MemoryUpdateRequest(text="fact", tags=None).tags is None

    response = Response()
    pairing._set_device_cookie(response, _request(), "token", "not-a-number")
    assert f"{pairing.DEVICE_TOKEN_COOKIE}=token" in response.headers["set-cookie"]
