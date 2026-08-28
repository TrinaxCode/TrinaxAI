#!/usr/bin/env python3
"""Generate a Continue configuration from the installed TrinaxAI profile."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROFILES = {
    "8gb": ("qwen3.5:2b", "qwen3.5:2b", "qwen3-embedding:0.6b", "qwen3.5:2b", 8192),
    "16gb": ("qwen3.5:4b", "qwen3.5:4b", "qwen3-embedding:0.6b", "qwen3.5:2b", 16384),
    "32gb": ("qwen3.5:9b", "qwen3.5:9b", "qwen3-embedding:4b", "qwen3.5:4b", 32768),
    "64gb": ("qwen3.5:35b", "qwen3-coder:30b", "qwen3-embedding:4b", "qwen3.5:4b", 32768),
}

PROFILE_MODEL_NAMES = {
    "8gb": {"TrinaxAI RAG (Primary)", "Qwen3.5 2B (8GB)", "Qwen3.5 2B (Fast)", "Qwen3.5 2B (Vision - 8GB)"},
    "16gb": {"TrinaxAI RAG (Primary)", "Qwen3.5 4B (16GB)", "Qwen3.5 2B (Fast)", "Qwen3.5 4B (Vision - 16GB)"},
    "32gb": {"TrinaxAI RAG (Primary)", "Qwen3.5 9B (32GB)", "Qwen3.5 4B (Fast)", "Qwen3.5 9B (Vision - 32GB)"},
    "64gb": {
        "TrinaxAI RAG (Primary)",
        "Qwen3.5 35B (64GB)",
        "Qwen3-Coder 30B (64GB)",
        "Qwen3.5 4B (Fast)",
        "Qwen3.5 35B (Vision - 64GB)",
    },
}
PROFILE_MODEL_ORDER = {
    profile: tuple(names)
    for profile, names in (
        ("8gb", ("TrinaxAI RAG (Primary)", "Qwen3.5 2B (8GB)", "Qwen3.5 2B (Fast)", "Qwen3.5 2B (Vision - 8GB)")),
        ("16gb", ("TrinaxAI RAG (Primary)", "Qwen3.5 4B (16GB)", "Qwen3.5 2B (Fast)", "Qwen3.5 4B (Vision - 16GB)")),
        ("32gb", ("TrinaxAI RAG (Primary)", "Qwen3.5 9B (32GB)", "Qwen3.5 4B (Fast)", "Qwen3.5 9B (Vision - 32GB)")),
        (
            "64gb",
            (
                "TrinaxAI RAG (Primary)",
                "Qwen3.5 35B (64GB)",
                "Qwen3-Coder 30B (64GB)",
                "Qwen3.5 4B (Fast)",
                "Qwen3.5 35B (Vision - 64GB)",
            ),
        ),
    )
}


def env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    return values


def detected_profile() -> str:
    try:
        if sys.platform == "linux":
            memory_kib = int(
                next(
                    line.split()[1]
                    for line in Path("/proc/meminfo").read_text().splitlines()
                    if line.startswith("MemTotal:")
                )
            )
            ram_gb = memory_kib / 1024 / 1024
        elif sys.platform == "darwin":
            ram_gb = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)) / 1024**3
        else:
            ram_gb = 0
    except (OSError, StopIteration, ValueError, subprocess.SubprocessError):
        ram_gb = 0
    return "64gb" if ram_gb >= 64 else "32gb" if ram_gb >= 32 else "16gb" if ram_gb >= 16 else "8gb"


def replace_line(text: str, pattern: str, replacement: str) -> str:
    result, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Continue template marker not found: {pattern}")
    return result


def profile_models(text: str, profile: str) -> str:
    """Keep only the Continue model entries supported by the active profile."""
    start = text.index("models:\n") + len("models:\n")
    end = text.index("\n# Keep TrinaxAI RAG as the default.", start)
    section = text[start:end]
    blocks = re.findall(r"(?ms)^  - name: (.+?)\n(.*?)(?=^  - name: |\Z)", section)
    allowed = PROFILE_MODEL_NAMES[profile]
    selected_names = {name for name, _ in blocks if name in allowed}
    block_map = {name: body for name, body in blocks}
    selected = [
        f"{name}\n{block_map[name].rstrip()}"
        for name in PROFILE_MODEL_ORDER[profile]
        if name in allowed and name in block_map
    ]
    for name in PROFILE_MODEL_ORDER[profile]:
        if name in selected_names:
            continue
        if name == "TrinaxAI RAG (Primary)":
            continue
        model = (
            "qwen3-coder:30b"
            if "Coder" in name
            else "qwen3.5:35b"
            if "35B" in name
            else "qwen3.5:9b"
            if "9B" in name
            else "qwen3.5:4b"
            if "4B" in name
            else "qwen3.5:4b"
            if "4B (Fast)" in name
            else "qwen3.5:2b"
        )
        context = 32768 if any(size in name for size in ("32GB", "64GB")) else 16384 if "16GB" in name else 8192
        roles = "[chat, autocomplete]" if "Fast" in name else "[chat]" if "Vision" in name else "[chat, edit, apply]"
        selected.append(
            f"{name}\n    provider: ollama\n    model: {model}\n    apiBase: http://localhost:11434\n"
            f"    contextLength: {context}\n    roles: {roles}\n"
            "    defaultCompletionOptions: {temperature: 0.1, maxTokens: 4096}\n"
            "    requestOptions: {timeout: 120000}"
        )
    order = {name: index for index, name in enumerate(PROFILE_MODEL_ORDER[profile])}
    selected.sort(key=lambda block: order[block.split("\n", 1)[0]])
    return text[:start] + "\n".join(f"  - name: {block}" for block in selected) + text[end:]


def generate(root: Path, output: Path, profile: str | None) -> None:
    values = env_values(root / ".env")
    selected = (profile or values.get("TRINAXAI_PROFILE") or detected_profile()).lower()
    if selected == "low":
        selected = "8gb"
    if selected not in PROFILES:
        raise ValueError(f"Unsupported TrinaxAI profile: {selected}")

    general, code, embedding, fast_default, context = PROFILES[selected]
    general = values.get("TRINAXAI_MODEL_GENERAL", general)
    code = values.get("TRINAXAI_MODEL_CODE", code)
    embedding = values.get("TRINAXAI_EMBED", embedding)
    fast = values.get("TRINAXAI_MODEL_FAST", fast_default)
    template = (root / "continue-config.yaml").read_text(encoding="utf-8")
    template = re.sub(r"^(?:# Generated automatically for TrinaxAI profile .*?\.\n)+", "", template)
    template = profile_models(template, selected)
    template = replace_line(template, r"^# ACTIVE PROFILE: .*?$", f"# ACTIVE PROFILE: {selected}")
    template = replace_line(template, r"^# Active chat/code: .*?$", f"# Active chat/code: {general} / {code}")
    template = replace_line(template, r"^# Active autocomplete: .*?$", f"# Active autocomplete: {fast} (Fast)")
    template = replace_line(template, r"^# Active embeddings: .*?$", f"# Active embeddings: {embedding}")
    fast_name = "Qwen3.5 4B (Fast)" if fast == "qwen3.5:4b" else "Qwen3.5 2B (Fast)"
    template = replace_line(template, r"^tabAutocompleteModel: .*?$", f"tabAutocompleteModel: {fast_name}")
    template = replace_line(template, r"^    contextLength: \d+$", f"    contextLength: {context}")
    template = replace_line(template, r"^  model: qwen3-embedding:.*$", f"  model: {embedding}")
    template = replace_line(
        template, r"^rerank:\n  provider: llm\n  model: .*?$", f"rerank:\n  provider: llm\n  model: {general}"
    )
    # Keep the generated file self-describing without changing Continue's schema.
    template = f"# Generated automatically for TrinaxAI profile {selected}.\n{template}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Continue config from TrinaxAI profile")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--install-user-config", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "continue-config.yaml").resolve()
    generate(root, output, args.profile)
    if args.install_user_config:
        user_config = Path(
            os.environ.get("CONTINUE_CONFIG_PATH", Path.home() / ".continue" / "config.yaml")
        ).expanduser()
        if user_config.resolve() != output:
            user_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, user_config)
        print(f"Continue config generated: {user_config}")
    else:
        print(f"Continue config generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
