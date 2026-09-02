.PHONY: setup frontend-install dev build lint test test-python test-frontend rag-eval audit audit-optional index check clean clean-generated clean-deps clean-build clean-data clean-all help typecheck readiness

# Cross-platform Python detection: prefer venv, fall back to system python3/py.
PYTHON ?= python3
VENV_PYTHON := $(shell if test -f .venv/bin/python; then echo .venv/bin/python; \
                 elif test -f .venv/Scripts/python.exe; then echo .venv/Scripts/python.exe; \
                 else echo $(PYTHON); fi)
REQUIREMENTS_INSTALL_ARGS := $(if $(wildcard requirements.lock),--require-hashes -r requirements.lock,-r requirements.txt)
AUDIT_REQUIREMENTS := $(if $(wildcard requirements.lock),--require-hashes -r requirements.lock,-r requirements.txt)
AUDIT_IGNORES := --ignore PYSEC-2026-3740

help:
	@echo "TrinaxAI — available targets:"
	@echo ""
	@echo "  setup            Create .venv, install Python + Node dependencies"
	@echo "  frontend-install Install Node dependencies only"
	@echo "  dev              Start frontend dev server (hot-reload)"
	@echo "  lint             Run Python lint/format and frontend ESLint"
	@echo "  typecheck        Run Python compile check + TypeScript typecheck"
	@echo "  test             Run backend + frontend unit tests"
	@echo "  test-python      Run Python tests only"
	@echo "  test-frontend    Run frontend tests only"
	@echo "  rag-eval         Evaluate the RAG golden set against a running API"
	@echo "  build            Build frontend for production"
	@echo "  index            Run the RAG indexer"
	@echo "  audit            Run blocking local audits"
	@echo "  audit-optional   Print optional security audit commands"
	@echo "  readiness        Run public release readiness check"
	@echo "  check            Run lint, tests, typecheck, audit, and build"
	@echo "  clean-generated  Remove generated build artifacts and caches"
	@echo "  clean-deps       Remove .venv and frontend node_modules"
	@echo "  clean-build      Remove generated artifacts and dependencies"
	@echo "  clean-all        Remove generated artifacts, dependencies AND user data — DESTRUCTIVE"
	@echo ""

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install $(REQUIREMENTS_INSTALL_ARGS)
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt
	$(VENV_PYTHON) -m pip install -e .
	cd chat-pwa && npm ci

frontend-install:
	cd chat-pwa && npm ci

dev:
	cd chat-pwa && npm run dev

build:
	$(VENV_PYTHON) -m py_compile rag_api.py config.py index.py trinaxai_index_documents.py trinaxai_index_state.py trinaxai_cli/app.py
	cd chat-pwa && npm run build && npm run check:bundle

lint:
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m ruff format --check .
	cd chat-pwa && npm run lint

test: test-python test-frontend

test-python:
	$(VENV_PYTHON) -m pytest -q \
		--cov=app --cov=trinaxai_agent --cov=trinaxai_cli --cov=trinaxai_core \
		--cov=service_manager --cov=index \
		--cov-branch --cov-report=term --cov-fail-under=98

test-frontend:
	cd chat-pwa && npm test && npm run test:coverage

RAG_API_URL ?= http://127.0.0.1:3333
RAG_EVAL_OUTPUT ?= rag-eval-report.json

rag-eval:
	$(VENV_PYTHON) scripts/evaluate_rag.py --api-url "$(RAG_API_URL)" --output "$(RAG_EVAL_OUTPUT)"

typecheck:
	$(VENV_PYTHON) -m py_compile rag_api.py config.py index.py trinaxai_index_documents.py trinaxai_index_state.py trinaxai_core.py
	cd chat-pwa && npx tsc --noEmit

readiness:
	$(VENV_PYTHON) scripts/public_readiness.py

index:
	$(VENV_PYTHON) index.py

audit:
	$(VENV_PYTHON) scripts/public_readiness.py
	bash -n install.sh
	bash -n backup.sh
	bash -n uninstall.sh
	cd chat-pwa && npm audit --audit-level=high
	$(VENV_PYTHON) -m pip_audit $(AUDIT_REQUIREMENTS) $(AUDIT_IGNORES)

audit-optional:
	@echo "Optional security checks; install each tool locally before running:"
	@echo "  gitleaks detect --source . --redact"
	@echo "  semgrep scan --config auto ."
	@echo "  trivy fs --scanners vuln,secret,misconfig ."
	@echo "  $(VENV_PYTHON) -m pip_audit"
	@echo "  cd chat-pwa && npm audit --audit-level=high"

check: lint test typecheck readiness audit build

clean: clean-generated clean-deps

clean-generated:
	rm -rf __pycache__ node_modules trinaxai.egg-info .coverage coverage.xml coverage.json htmlcov .pytest_cache .ruff_cache .mypy_cache chat-pwa/dist chat-pwa/server-dist chat-pwa/coverage chat-pwa/test-results chat-pwa/playwright-report chat-pwa/blob-report
	find . -path './.git' -prune -o -path './.venv' -prune -o -path './chat-pwa/node_modules' -prune -o -path './storage' -prune -o -path './storage.bak*' -prune -o -path './build' -prune -o -path './dist' -prune -o -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

clean-deps:
	rm -rf .venv chat-pwa/node_modules

clean-build: clean-generated clean-deps

clean-data:
	@echo "⚠️  This will delete storage/ (your RAG index and collections). Press Ctrl+C to cancel."
	@sleep 3
	rm -rf storage/

clean-all: clean-generated clean-deps
	$(MAKE) clean-data
