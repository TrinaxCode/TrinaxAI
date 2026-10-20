from __future__ import annotations

from types import SimpleNamespace

from trinaxai_cli.commands import pair


class _UI:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.rows = []

    def success(self, message):
        self.messages.append(str(message))

    def info(self, message):
        self.messages.append(str(message))

    def warn(self, message):
        self.messages.append(str(message))

    def error(self, message):
        self.messages.append(str(message))

    def table(self, headers, rows, title=None):
        self.rows = rows


class _Client:
    base_url = "https://192.168.1.20:3333"

    def start_pairing(self, scopes, ttl_seconds, device_ttl_days):
        assert scopes == ["chat", "read_private"]
        assert ttl_seconds == 300
        return {"code": "ABCD-EFGH", "expires_at": 1234}

    def list_paired_devices(self):
        return [{"id": "abc", "name": "Phone", "scopes": ["chat"], "revoked_at": None}]

    def revoke_paired_device(self, device_id):
        return {"id": device_id, "name": "Phone", "revoked_at": 1234}


def test_pair_start_prints_code_and_pwa_link() -> None:
    ui = _UI()
    result = pair.run(
        SimpleNamespace(
            pair_command="start",
            scopes="chat,read_private",
            ttl=300,
            device_ttl_days=None,
            pwa_url=None,
        ),
        _Client(),
        ui,
        None,
    )
    assert result == 0
    assert any("ABCD-EFGH" in message for message in ui.messages)
    assert any("https://192.168.1.20:3334/#/settings/advanced?pair=ABCD-EFGH" in message for message in ui.messages)


def test_pair_list_and_revoke() -> None:
    ui = _UI()
    assert pair.run(SimpleNamespace(pair_command="list"), _Client(), ui, None) == 0
    assert ui.rows[0][1] == "Phone"
    assert pair.run(SimpleNamespace(pair_command="revoke", device_id="abc"), _Client(), ui, None) == 0
    assert any("Revoked Phone" in message for message in ui.messages)


class _SetClient(_Client):
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def set_paired_device_scopes(self, device_id, scopes):
        self.calls.append((device_id, scopes))
        return {"id": device_id, "name": "Phone", "scopes": scopes}


def test_pair_set_updates_permissions_and_warns_about_elevated_scopes() -> None:
    ui, client = _UI(), _SetClient()
    result = pair.run(
        SimpleNamespace(pair_command="set", device_id="abc", scopes="chat, agent ,index"),
        client,
        ui,
        None,
    )
    assert result == 0
    assert client.calls == [("abc", ["chat", "agent", "index"])]
    assert any("Updated Phone: chat,agent,index." in message for message in ui.messages)
    assert any("Elevated permissions granted: agent, index" in message for message in ui.messages)

    quiet = _UI()
    pair.run(SimpleNamespace(pair_command="set", device_id="abc", scopes="chat,web"), _SetClient(), quiet, None)
    assert not any("Elevated" in message for message in quiet.messages)


def test_pair_start_warns_when_granting_elevated_scopes() -> None:
    class Client(_Client):
        def start_pairing(self, scopes, ttl_seconds, device_ttl_days):
            assert scopes == ["chat", "modify"]
            return {"code": "ABCD-EFGH", "expires_at": 1234}

    ui = _UI()
    pair.run(
        SimpleNamespace(pair_command="start", scopes="chat,modify", ttl=300, device_ttl_days=None, pwa_url=None),
        Client(),
        ui,
        None,
    )
    assert any("Elevated permissions granted: modify" in message for message in ui.messages)
