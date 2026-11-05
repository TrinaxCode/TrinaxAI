"""The host may pick a project anywhere under their home folder; paired devices may not."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import agent_service


def _request(identity=None, **query) -> SimpleNamespace:
    return SimpleNamespace(
        query_params=query,
        state=SimpleNamespace(trinaxai_identity=identity),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )


@pytest.fixture
def layout(monkeypatch, tmp_path):
    home = tmp_path / "home"
    install = home / "Documents" / "Insider" / "ai-rag"
    elsewhere = home / "code" / "my-app"
    install.mkdir(parents=True)
    elsewhere.mkdir(parents=True)
    monkeypatch.delenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setattr(agent_service.config, "BASE_DIR", str(install))
    monkeypatch.setattr(agent_service.config, "PROJECTS_DIRS", ())
    monkeypatch.setattr(agent_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(agent_service, "_read_app_state", lambda: {})
    return SimpleNamespace(home=home.resolve(), install=install.resolve(), elsewhere=elsewhere.resolve())


def test_host_can_use_a_folder_outside_the_installation(layout) -> None:
    roots = agent_service._workspace_roots_for(_request())
    assert agent_service._resolve_workspace(str(layout.elsewhere), roots) == layout.elsewhere


def test_paired_device_stays_inside_the_configured_roots(layout) -> None:
    device = _request({"kind": "device", "id": "d1", "scopes": ["agent"]})
    roots = agent_service._workspace_roots_for(device)
    assert layout.home not in roots
    with pytest.raises(HTTPException) as denied:
        agent_service._resolve_workspace(str(layout.elsewhere), roots)
    assert denied.value.status_code == 403


def test_operator_allowlist_is_never_widened(layout, monkeypatch) -> None:
    monkeypatch.setenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", str(layout.install))
    roots = agent_service._workspace_roots_for(_request())
    assert roots == (layout.install,)
    with pytest.raises(HTTPException) as denied:
        agent_service._resolve_workspace(str(layout.elsewhere), roots)
    assert denied.value.status_code == 403


def test_default_workspace_never_falls_back_to_the_whole_home_folder(layout) -> None:
    roots = agent_service._workspace_roots_for(_request())
    assert agent_service._resolve_workspace("", roots) == layout.install


def test_folder_picker_can_climb_above_the_installation(layout) -> None:
    listing = asyncio.run(agent_service.agent_browse(_request(path=str(layout.install))))
    assert listing["path"] == str(layout.install)
    assert listing["parent"] == str(layout.install.parent), "the picker must not be trapped in the install root"
    top = asyncio.run(agent_service.agent_browse(_request(path=str(layout.home))))
    assert top["parent"] is None
    assert {entry["name"] for entry in top["directories"]} >= {"Documents", "code"}
