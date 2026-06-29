# TrinaxAI V1 Public Release Checklist

Use this checklist before tagging or publishing a public TrinaxAI release.

## Required Checks

Run from the repository root:

```bash
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py index.py config.py trinaxai_cli.py service_manager.py test_system.py scripts/public_readiness.py
cd chat-pwa && npm run build
```

For a local runtime smoke test:

```bash
python3 test_system.py --verbose
```

## Release Scope

V1 uses the native installer path by default. This is intentional: local Ollama, host file indexing, LAN HTTPS, and phone access are more predictable natively than in Docker for most users.

Publish only source, docs, scripts, and lockfiles. Do not publish runtime data:

- `.env`
- `.venv/`
- `chat-pwa/node_modules/`
- `chat-pwa/dist/`
- `storage/`
- `local_sources/`
- `logs/`
- `backups/`

## Manual Verification

Before release, verify these workflows on a clean install:

- Install on Linux, macOS, or Windows using the documented installer.
- Open the PWA at `https://localhost:3334`.
- Complete initial configuration once and confirm it does not reappear on another synced browser/device.
- Use chat in English and Spanish; TrinaxAI should answer in the current message language.
- Use `Apagar IA`; Ollama and RAG must stop and remain off after restart.
- Use `Encender IA`; Ollama and RAG must start and remain enabled after restart.
- Run an index job and confirm sources appear in RAG responses.
- Open Settings > Stats and confirm message counts update after usage.

## Security Notes

System actions are intended for localhost or trusted LAN clients. If exposing TrinaxAI beyond a private LAN, configure `TRINAXAI_ADMIN_TOKEN` and prefer a VPN such as Tailscale or WireGuard.

The legacy `setup_trinaxai.sh` path can create system-level services and sudoers rules. For production, prefer the default `service_manager.py` autostart path or move allowed scripts to root-owned locations.
