from pathlib import Path
from types import SimpleNamespace

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


def test_release_contract_matches_the_repository():
    assert public_readiness.check_release_contract() == []


def test_install_surface_contract_rejects_unpinned_trinaxai_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setattr(public_readiness, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text(
        "curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash\n",
        encoding="utf-8",
    )

    errors = public_readiness.check_install_surfaces()

    assert any("README.md" in error and "unpinned" in error for error in errors)


def test_release_workflow_security_contract_is_fail_closed_and_reproducible():
    workflow = (Path(public_readiness.__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )

    assert public_readiness.check_release_workflow_security(workflow) == []


def test_ci_workflow_has_effective_publication_gates():
    workflow = (Path(public_readiness.__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )

    assert public_readiness.check_ci_workflow_contract(workflow) == []
    assert public_readiness.check_ci_workflow_contract(workflow.replace("--cov-fail-under=98", "", 1))
    assert public_readiness.check_ci_workflow_contract(workflow + "\ncontinue-on-error: true\n")
    live_smoke = "run: python scripts/evaluate_rag.py --ollama-smoke"
    assert public_readiness.check_ci_workflow_contract(workflow.replace(live_smoke, "run: true", 1))
    echoed_gate = workflow.replace("run: ruff check .", 'run: echo "ruff check ."', 1)
    assert public_readiness.check_ci_workflow_contract(echoed_gate)


def test_release_workflow_security_contract_catches_regressions():
    workflow = (Path(public_readiness.__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )

    mutable_action = workflow.replace(
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "actions/checkout@v6",
        1,
    )
    assert any("commit SHA" in error for error in public_readiness.check_release_workflow_security(mutable_action))

    unsigned = workflow.replace("gpg --batch --verify", "gpg --batch --inspect", 1)
    assert any("gpg --batch --verify" in error for error in public_readiness.check_release_workflow_security(unsigned))

    echoed = workflow.replace("gpg --batch --verify", 'echo "gpg --batch --verify"', 1)
    assert any("gpg --batch --verify" in error for error in public_readiness.check_release_workflow_security(echoed))

    floating_tool = workflow.replace('"wheel==0.45.1"', '"wheel"', 1)
    assert any("wheel" in error for error in public_readiness.check_release_workflow_security(floating_tool))

    unsigned_published_asset = workflow.replace(
        '[[ -n "$asset" && -f "$asset" && -f "$asset.asc" ]]',
        '[[ -n "$asset" && -f "$asset" ]]',
        1,
    )
    assert any(
        "signature for every checksummed asset" in error
        for error in public_readiness.check_release_workflow_security(unsigned_published_asset)
    )


def test_required_gates_run_repository_commands_without_logging_output(monkeypatch, capsys):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="gate output", stderr="")

    monkeypatch.setattr(public_readiness.subprocess, "run", run)

    assert public_readiness.check_required_gates() == []
    assert len(calls) == 10
    assert calls[0][0][1:] == ["-m", "ruff", "check", "."]
    assert calls[2][0][1:] == ["-m", "mypy"]
    assert "--cov-branch" in calls[3][0]
    assert "--cov-fail-under=98" in calls[3][0]
    assert calls[4][0][1:] == ["scripts/evaluate_rag.py", "--deterministic", "--output", "-"]
    assert calls[5][0][1:] == ["run", "lint"]
    assert calls[6][0][1:] == ["run", "typecheck"]
    assert calls[7][0][1:] == ["run", "test:coverage"]
    assert calls[8][0][1:] == ["run", "build"]
    assert calls[9][0][1:] == ["run", "check:bundle"]
    assert "gate output" not in capsys.readouterr().out


def test_required_gate_failure_is_reported_without_leaking_output(monkeypatch, capsys):
    responses = iter(
        SimpleNamespace(
            returncode=2 if index == 6 else 0,
            stdout="private gate output",
            stderr="private gate failure",
        )
        for index in range(10)
    )
    monkeypatch.setattr(public_readiness.subprocess, "run", lambda *_args, **_kwargs: next(responses))

    errors = public_readiness.check_required_gates()

    assert errors == ["TypeScript typecheck failed with exit code 2"]
    output = capsys.readouterr().out
    assert "private typecheck output" not in output
    assert "private typecheck failure" not in output
