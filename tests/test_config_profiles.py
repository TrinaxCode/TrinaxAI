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

    assert data["general"] == "llama3.2:1b"
    assert data["code"] == "qwen2.5-coder:1.5b"
    assert data["deep"] == "qwen2.5-coder:1.5b"
    assert data["fast"] == "llama3.2:1b"
    assert data["embed_preset"] == "lite"
    assert data["embed"] == "nomic-embed-text"
    assert data["batch"] == 1
