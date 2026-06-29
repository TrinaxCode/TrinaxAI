# Contributing to TrinaxAI

First off, thank you for considering contributing to TrinaxAI!

TrinaxAI is an open-source project and we love to receive contributions from the community. There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, submitting bug reports and feature requests, or writing code which can be incorporated into TrinaxAI itself.

## Code of Conduct

This project follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be respectful, direct, and constructive.

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report:
- Check the [FAQ](https://github.com/TrinaxCode/trinaxai#readme) and [docs](https://github.com/TrinaxCode/trinaxai/tree/main/docs)
- Search [existing issues](https://github.com/TrinaxCode/trinaxai/issues) to see if it's already reported

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
4. Run `python3 scripts/public_readiness.py`
5. Run `python3 -m py_compile *.py scripts/*.py`
6. Run `cd chat-pwa && npm run build`
7. Open the pull request

### 🌍 Translations

TrinaxAI supports multiple languages. To add or improve translations:
- Edit `chat-pwa/src/i18n/translations.ts`
- Add your language following the existing pattern (ES, EN)
- Test that all UI elements display correctly

### 📚 Documentation

Documentation improvements are always welcome! The docs live in:
- `docs/` — API reference, architecture, developer guide
- `chat-pwa/src/components/Docs.tsx` (in-app documentation)
- `README.md` (project overview)
- `README.es.md` (Spanish version)

---

## Development Setup

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for full setup instructions.

Quick start:
```bash
git clone https://github.com/TrinaxCode/trinaxai.git
cd trinaxai
./install.sh                # or install.ps1 on Windows
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd chat-pwa
npm install
npm run dev
```

## Release Checks

Before a release:

```bash
python3 scripts/public_readiness.py
python3 -m py_compile *.py scripts/*.py
cd chat-pwa && npm run build
python3 test_system.py --verbose
```

See `docs/PUBLIC_RELEASE.md` for the full checklist.

## License

By contributing, you agree that your contribution is licensed under AGPL-3.0-or-later.

## Questions?

Open a [GitHub Discussion](https://github.com/TrinaxCode/trinaxai/discussions) or reach out on the issue tracker.

---

⭐ **Thanks for contributing!**
