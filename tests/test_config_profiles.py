from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_config_8gb_profile_uses_light_defaults(tmp_path: Path) -> None:
    (tmp_path / "dotenv.py").write_text(
        "def load_dotenv(*args, **kwargs):\n    return False\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)]),
        "TRINAXAI_PROFILE": "8gb",
    }
    env.pop("TRINAXAI_MODEL_GENERAL", None)
    env.pop("TRINAXAI_MODEL_CODE", None)
    env.pop("TRINAXAI_MODEL_DEEP", None)
    env.pop("TRINAXAI_MODEL_FAST", None)
    env.pop("TRINAXAI_EMBED_PRESET", None)
    env.pop("TRINAXAI_EMBED", None)
    env.pop("TRINAXAI_EMBED_BATCH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, config; "
                "print(json.dumps({"
                "'general': config.MODEL_GENERAL, "
                "'code': config.MODEL_CODE, "
                "'deep': config.MODEL_DEEP, "
                "'fast': config.MODEL_FAST, "
                "'embed_preset': config.EMBED_PRESET, "
                "'embed': config.EMBED_MODEL, "
                "'batch': config.EMBED_BATCH_SIZE"
                "}))"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["general"] == "qwen3.5:2b"
    assert data["code"] == "qwen3.5:2b"
    assert data["deep"] == "qwen3.5:2b"
    assert data["fast"] == "qwen3.5:2b"
    assert data["embed_preset"] == "balanced"
    assert data["embed"] == "qwen3-embedding:0.6b"
    assert data["batch"] == 1


def test_all_profile_model_roles_match_the_release_matrix(tmp_path: Path) -> None:
    (tmp_path / "dotenv.py").write_text("def load_dotenv(*args, **kwargs):\n    return False\n", encoding="utf-8")
    expected = {
        "8gb": ["qwen3.5:2b", "qwen3.5:2b", "qwen3.5:2b", "qwen3.5:2b", "qwen3-embedding:0.6b", 1024],
        "16gb": ["qwen3.5:4b", "qwen3.5:4b", "qwen3.5:4b", "qwen3.5:2b", "qwen3-embedding:0.6b", 1024],
        "32gb": ["qwen3.5:9b", "qwen3.5:9b", "qwen3.5:9b", "qwen3.5:4b", "qwen3-embedding:4b", 2560],
        "64gb": ["qwen3.5:35b", "qwen3-coder:30b", "qwen3.5:35b", "qwen3.5:4b", "qwen3-embedding:4b", 2560],
    }
    for profile, models in expected.items():
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)]), "TRINAXAI_PROFILE": profile}
        for name in (
            "TRINAXAI_MODEL_GENERAL",
            "TRINAXAI_MODEL_CODE",
            "TRINAXAI_MODEL_DEEP",
            "TRINAXAI_MODEL_FAST",
            "TRINAXAI_EMBED_PRESET",
            "TRINAXAI_EMBED",
            "TRINAXAI_EMBED_DIMS",
        ):
            env.pop(name, None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, config; print(json.dumps([config.MODEL_GENERAL, config.MODEL_CODE, config.MODEL_DEEP, config.MODEL_FAST, config.EMBED_MODEL, config.EMBED_DIMS]))",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == models


def test_legacy_environment_profile_is_migrated_to_a_canonical_profile(tmp_path: Path) -> None:
    (tmp_path / "dotenv.py").write_text(
        "def load_dotenv(*args, **kwargs):\n    return False\n",
        encoding="utf-8",
    )
    legacy = bytes((109, 97, 120)).decode("ascii")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)]), "TRINAXAI_PROFILE": legacy}
    for name in (
        "TRINAXAI_MODEL_GENERAL",
        "TRINAXAI_MODEL_CODE",
        "TRINAXAI_MODEL_DEEP",
        "TRINAXAI_MODEL_FAST",
        "TRINAXAI_EMBED_PRESET",
        "TRINAXAI_EMBED",
        "TRINAXAI_EMBED_DIMS",
    ):
        env.pop(name, None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, config; print(json.dumps([config.TRINAXAI_PROFILE, config.PROFILE_MIGRATED, config.MODEL_GENERAL]))",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["32gb", True, "qwen3.5:9b"]


def test_legacy_small_environment_profile_is_migrated_to_8gb(tmp_path: Path) -> None:
    (tmp_path / "dotenv.py").write_text(
        "def load_dotenv(*args, **kwargs):\n    return False\n",
        encoding="utf-8",
    )
    legacy = bytes((108, 111, 119)).decode("ascii")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)]), "TRINAXAI_PROFILE": legacy}
    for name in (
        "TRINAXAI_MODEL_GENERAL",
        "TRINAXAI_MODEL_CODE",
        "TRINAXAI_MODEL_DEEP",
        "TRINAXAI_MODEL_FAST",
        "TRINAXAI_EMBED_PRESET",
        "TRINAXAI_EMBED",
        "TRINAXAI_EMBED_DIMS",
    ):
        env.pop(name, None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, config; print(json.dumps([config.TRINAXAI_PROFILE, config.PROFILE_MIGRATED, config.MODEL_GENERAL]))",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["8gb", True, "qwen3.5:2b"]
