.PHONY: setup frontend-install dev build lint test test-python test-frontend audit audit-optional index check clean clean-build clean-all help

# Cross-platform Python detection: prefer venv, fall back to system python3/py.
PYTHON ?= python3
VENV_PYTHON := $(shell if test -f .venv/bin/python; then echo .venv/bin/python; \
                 elif test -f .venv/Scripts/python.exe; then echo .venv/Scripts/python.exe; \
                 else echo $(PYTHON); fi)

help:
	@echo "TrinaxAI — available targets:"
	@echo ""
	@echo "  setup            Create .venv, install Python + Node dependencies"
	@echo "  frontend-install Install Node dependencies only"
	@echo "  dev              Start frontend dev server (hot-reload)"
	@echo "  lint             Run Python lint and frontend typecheck"
	@echo "  test             Run backend + frontend unit tests"
	@echo "  build            Build frontend for production"
	@echo "  index            Run the RAG indexer"
	@echo "  audit            Run blocking local audits"
	@echo "  audit-optional   Print optional security audit commands"
	@echo "  check            Run lint, tests, script checks, build and audit"
	@echo "  clean-build      Remove build artifacts (.venv, node_modules, dist, __pycache__)"
	@echo "  clean-all        Remove build artifacts AND user data (storage/) — DESTRUCTIVE"
	@echo ""

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	cd chat-pwa && npm install

frontend-install:
	cd chat-pwa && npm install

dev:
	cd chat-pwa && npm run dev

build:
	$(VENV_PYTHON) -m py_compile rag_api.py config.py index.py trinaxai_cli.py
	cd chat-pwa && npm run build

lint:
	$(VENV_PYTHON) -m ruff check .
	cd chat-pwa && npx tsc --noEmit

test: test-python test-frontend

test-python:
	$(VENV_PYTHON) -m pytest -q

test-frontend:
	cd chat-pwa && npm test

index:
	$(VENV_PYTHON) index.py

audit:
	$(VENV_PYTHON) scripts/public_readiness.py
	bash -n install.sh
	bash -n backup.sh
	bash -n uninstall.sh
	cd chat-pwa && npm audit --audit-level=high

audit-optional:
	@echo "Optional security checks; install each tool locally before running:"
	@echo "  gitleaks detect --source . --redact"
	@echo "  semgrep scan --config auto ."
	@echo "  trivy fs --scanners vuln,secret,misconfig ."
	@echo "  $(VENV_PYTHON) -m pip_audit"
	@echo "  cd chat-pwa && npm audit --audit-level=high"

check: lint test audit build

clean: clean-build

clean-build:
	rm -rf __pycache__ .venv chat-pwa/node_modules chat-pwa/dist
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean-build
	@echo "⚠️  This will delete storage/ (your RAG index and collections). Press Ctrl+C to cancel."
	@sleep 3
	rm -rf storage/
