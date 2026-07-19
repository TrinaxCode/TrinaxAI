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

    assert data["general"] == "qwen3.5:0.8b"
    assert data["code"] == "qwen2.5-coder:1.5b"
    assert data["deep"] == "qwen3.5:0.8b"
    assert data["fast"] == "qwen3.5:0.8b"
    assert data["embed_preset"] == "balanced"
    assert data["embed"] == "bge-m3"
    assert data["batch"] == 1


def test_all_profile_model_roles_match_the_release_matrix(tmp_path: Path) -> None:
    (tmp_path / "dotenv.py").write_text("def load_dotenv(*args, **kwargs):\n    return False\n", encoding="utf-8")
    expected = {
        "16gb": ["granite4:3b", "qwen2.5-coder:1.5b", "qwen3.5:2b", "qwen3.5:0.8b"],
        "max": ["qwen3.5:27b", "qwen2.5-coder:14b", "qwen3.5:27b", "qwen3.5:4b"],
        "ultra": ["qwen3.5:35b-a3b", "qwen3-coder:30b", "qwen3.5:35b-a3b", "qwen3.5:4b"],
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
