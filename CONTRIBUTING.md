# Contributing to TrinaxAI

[Versión en español](docs/es/CONTRIBUTING.md)

First off, thank you for considering contributing to TrinaxAI!

TrinaxAI is an open-source project and we love to receive contributions from the community. There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, submitting bug reports and feature requests, or writing code which can be incorporated into TrinaxAI itself.

## Code of Conduct

This project follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be respectful, direct, and constructive.

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report:
- Check the [docs](https://github.com/TrinaxCode/TrinaxAI/tree/main/docs)
- Search [existing issues](https://github.com/TrinaxCode/TrinaxAI/issues) to see if it's already reported

When reporting a bug, please include:
- Your OS and hardware specs (CPU, RAM)
- TrinaxAI version or commit hash
- Steps to reproduce
- Expected vs actual behavior
- Any error messages or logs

### 💡 Suggesting Features

Feature suggestions are tracked as GitHub Issues. Please describe:
- The problem you're trying to solve
- How you'd like TrinaxAI to solve it
- Any alternatives you've considered

### 📝 Pull Requests

1. Fork the repo and create your branch from `main`
2. Sign off every commit for DCO: `git commit -s`
3. If you've added code, add tests if applicable
4. Run the pre-release checks (see below)
5. Open the pull request

### 🌍 Translations

TrinaxAI supports multiple languages. To add or improve translations:
- Edit `chat-pwa/src/i18n/translations.ts`
- Add your language following the existing pattern (ES, EN)
- Test that all UI elements display correctly

### 📚 Documentation

Documentation improvements are always welcome! The docs live in:
- `docs/README.md` — documentation map and maintenance sources of truth
- `docs/` — API, CLI, configuration, architecture, installation, and developer references
- `chat-pwa/README.md` — PWA runtime and development reference
- `chat-pwa/src/components/Docs.tsx` (in-app documentation)
- `README.md` (project overview)
- `README.es.md` (Spanish version)

Keep English and `.es.md` counterparts aligned. Verify command names against `trinaxai_cli/app.py`, API paths against `/openapi.json`, and PWA scripts against `chat-pwa/package.json`.

---

## Development Setup

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for full setup instructions.

Quick start:
```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh                # or install.ps1 on Windows
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd chat-pwa
npm install
npm run dev

# CLI (editable install)
pip install -e .
trinaxai doctor
```

## Pre-Release Checks

Before opening a PR or pushing to main, run these:

```bash
# Python
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py config.py index.py trinaxai_cli/app.py
ruff check .

# Frontend
cd chat-pwa
npx tsc --noEmit
npm run build
npm audit --audit-level=high

# System test (requires running services)
trinaxai doctor
python3 test_system.py --verbose
```

Run `make readiness` before opening a release-oriented pull request.

## Commit Style

- Use present tense ("Add feature" not "Added feature")
- Keep commits focused — one logical change per commit
- Reference issues with `#123` when applicable
- Sign off with `git commit -s` for DCO compliance

## License

By contributing, you agree that your contribution is licensed under AGPL-3.0-or-later.

## Questions?

Open a [GitHub Discussion](https://github.com/TrinaxCode/TrinaxAI/discussions) or reach out on the issue tracker.

---

⭐ **Thanks for contributing!**
