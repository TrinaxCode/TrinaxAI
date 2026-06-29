"""
TrinaxAI CLI — local-first terminal assistant.

Examples:
  python trinaxai_cli.py
  python trinaxai_cli.py "Explain the indexed project" --engine rag
  python trinaxai_cli.py "Write a small index.html" --engine ollama
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

try:
    import config
except Exception:
    import ssl as _ssl

    class _FallbackConfig:
        OLLAMA_BASE_URL = "http://localhost:11434"
        LLM_MODEL = "qwen2.5-coder:3b"
        NUM_CTX = 4096
        NUM_THREAD = 8

        @staticmethod
        def create_ssl_context(verify: bool = True) -> "_ssl.SSLContext | None":
            if verify:
                return None
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            return ctx

    config = _FallbackConfig()

_rag_port = os.getenv("TRINAXAI_PORT", "3333")
_rag_host = os.getenv("TRINAXAI_RAG_HOST", "localhost")
RAG_URL = os.getenv(
    "TRINAXAI_RAG_URL",
    f"https://{_rag_host}:{_rag_port}/v1/chat/completions",
)
OLLAMA_URL = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"


def _post_json(url: str, payload: dict, *, verify_tls: bool = True) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    context = config.create_ssl_context(verify_tls)
    try:
        with urllib.request.urlopen(req, timeout=300, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to {url}: {exc}") from exc


def route_cli_model(messages: list[dict], requested: str) -> str:
    if requested and requested.lower() not in {"auto", "router"}:
        return requested
    current = next(
        (
            str(m.get("content", ""))
            for m in reversed(messages)
            if m.get("role") == "user"
        ),
        "",
    )
    route = getattr(config, "route_model", None)
    if callable(route):
        return route(current)
    return getattr(config, "MODEL_GENERAL", getattr(config, "LLM_MODEL", "llama3.2:3b"))


def ask_ollama(messages: list[dict], model: str) -> tuple[str, str]:
    used_model = route_cli_model(messages, model)
    system = {
        "role": "system",
        "content": (
            "You are TrinaxAI CLI, a local-first open-source assistant. "
            "Your product identity is TrinaxAI. You are not TrinaxCode; TrinaxCode is the project creator/author. "
            "If the user asks who or what you are, answer that you are TrinaxAI. "
            "Answer in the user's language. Be direct and practical."
        ),
    }
    payload = {
        "model": used_model,
        "messages": [system, *messages],
        "stream": False,
        "keep_alive": "0",
        "options": {
            "num_ctx": max(config.NUM_CTX, 4096),
            "num_thread": config.NUM_THREAD,
        },
    }
    data = _post_json(OLLAMA_URL, payload)
    return data.get("message", {}).get("content", ""), used_model


def ask_rag(
    messages: list[dict], collections: list[str] | None = None
) -> tuple[str, str]:
    payload = {
        "messages": messages,
        "stream": False,
        "collections": collections or ["default"],
    }
    # TrinaxAI uses self-signed certs for LAN HTTPS; TLS verification is off
    # by default for local access. Set TRINAXAI_TLS_VERIFY=1 to enable it.
    verify_tls = os.getenv("TRINAXAI_TLS_VERIFY", "0") == "1"
    data = _post_json(RAG_URL, payload, verify_tls=verify_tls)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    model = data.get("trinaxai", {}).get("model", data.get("model", config.LLM_MODEL))
    sources = data.get("trinaxai", {}).get("sources") or []
    if sources:
        content += "\n\nSources:\n" + "\n".join(
            f"- {s.get('file')} ({s.get('collection', 'General')})" for s in sources[:5]
        )
    return content, model


def print_status(engine: str, model: str) -> None:
    print(f"TrinaxAI CLI | engine={engine} | model={model}")
    print("Commands: /engine ollama|rag, /model auto|NAME, /status, /exit")


def run_once(prompt: str, engine: str, model: str, collections: list[str]) -> int:
    messages = [{"role": "user", "content": prompt}]
    answer, used_model = (
        ask_rag(messages, collections)
        if engine == "rag"
        else ask_ollama(messages, model)
    )
    print(answer)
    print(f"\n[model: {used_model}]")
    return 0


def repl(engine: str, model: str, collections: list[str]) -> int:
    messages: list[dict] = []
    print_status(engine, model)
    while True:
        try:
            prompt = input("\ntrinaxai> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/exit", "exit", "quit", "salir"}:
            return 0
        if prompt.startswith("/engine "):
            next_engine = prompt.split(maxsplit=1)[1].strip()
            if next_engine in {"ollama", "rag"}:
                engine = next_engine
                print_status(engine, model)
            continue
        if prompt.startswith("/model "):
            model = prompt.split(maxsplit=1)[1].strip() or model
            print_status(engine, model)
            continue
        if prompt == "/status":
            print_status(engine, model)
            continue

        messages.append({"role": "user", "content": prompt})
        try:
            answer, used_model = (
                ask_rag(messages, collections)
                if engine == "rag"
                else ask_ollama(messages, model)
            )
        except Exception as exc:
            print(f"Error: {exc}")
            continue
        messages.append({"role": "assistant", "content": answer})
        print(f"\n{answer}\n\n[model: {used_model}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TrinaxAI CLI local assistant")
    parser.add_argument(
        "prompt", nargs="*", help="Prompt to run once. Omit for interactive mode."
    )
    parser.add_argument("--engine", choices=["ollama", "rag"], default="ollama")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--collection", action="append", default=["default"])
    args = parser.parse_args(argv)
    prompt = " ".join(args.prompt).strip()
    if prompt:
        return run_once(prompt, args.engine, args.model, args.collection)
    return repl(args.engine, args.model, args.collection)


if __name__ == "__main__":
    raise SystemExit(main())
