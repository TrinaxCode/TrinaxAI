.PHONY: setup frontend-install dev build test audit index clean clean-build clean-all help

# Cross-platform Python detection: prefer venv, fall back to system python3/py.
PYTHON ?= python3
VENV_PYTHON := $(shell test -f .venv/bin/python && echo .venv/bin/python || \
                 test -f .venv/Scripts/python.exe && echo .venv/Scripts/python.exe || \
                 echo $(PYTHON))

help:
	@echo "TrinaxAI — available targets:"
	@echo ""
	@echo "  setup            Create .venv, install Python + Node dependencies"
	@echo "  frontend-install Install Node dependencies only"
	@echo "  dev              Start frontend dev server (hot-reload)"
	@echo "  build            Build frontend for production"
	@echo "  index            Run the RAG indexer"
	@echo "  test             Run system health check (requires services running)"
	@echo "  audit            Run pre-release readiness audit"
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
	cd chat-pwa && npm run build

index:
	$(VENV_PYTHON) index.py

test:
	$(VENV_PYTHON) test_system.py --verbose

audit:
	$(VENV_PYTHON) scripts/public_readiness.py

clean: clean-build

clean-build:
	rm -rf __pycache__ .venv chat-pwa/node_modules chat-pwa/dist
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean-build
	@echo "⚠️  This will delete storage/ (your RAG index and collections). Press Ctrl+C to cancel."
	@sleep 3
	rm -rf storage/
