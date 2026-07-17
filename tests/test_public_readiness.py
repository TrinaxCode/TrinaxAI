from scripts import public_readiness


def test_secret_scan_distinguishes_runtime_token_reads_from_literals(tmp_path, monkeypatch):
    safe = tmp_path / "safe.ts"
    safe.write_text(
        "const adminToken = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);\n",
        encoding="utf-8",
    )
    exposed = tmp_path / "exposed.py"
    exposed.write_text('admin_token = "this-is-a-real-looking-token"\n', encoding="utf-8")
    monkeypatch.setattr(public_readiness, "ROOT", tmp_path)

    errors = public_readiness.check_secrets([safe, exposed])

    assert not any("safe.ts" in error for error in errors)
    assert any("exposed.py" in error for error in errors)
