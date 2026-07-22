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
        "8gb": ["qwen3.5:2b", "qwen3.5:2b", "qwen3.5:2b", "qwen3.5:2b"],
        "16gb": ["qwen3.5:4b", "qwen3.5:4b", "qwen3.5:4b", "qwen3.5:2b"],
        "max": ["qwen3.5:9b", "qwen3.5:9b", "qwen3.5:9b", "qwen3.5:2b"],
        "ultra": ["qwen3.5:35b", "qwen3-coder:30b", "qwen3.5:35b", "qwen3.5:4b"],
    }
    for profile, models in expected.items():
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)]), "TRINAXAI_PROFILE": profile}
        for name in ("TRINAXAI_MODEL_GENERAL", "TRINAXAI_MODEL_CODE", "TRINAXAI_MODEL_DEEP", "TRINAXAI_MODEL_FAST"):
            env.pop(name, None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, config; print(json.dumps([config.MODEL_GENERAL, config.MODEL_CODE, config.MODEL_DEEP, config.MODEL_FAST]))",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == models
