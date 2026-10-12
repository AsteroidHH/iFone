.PHONY: all up down test proof seed demo clean help

help:
	@echo "Quorum Makefile — Person 1 (Janani: Graph & FalkorDB)"
	@echo ""
	@echo "  make up      Start full stack (FalkorDB, backend, frontend, helpdesk, MCP)"
	@echo "  make down    Stop and remove all containers + volumes"
	@echo "  make seed    Generate synthetic corpus into live FalkorDB"
	@echo "  make test    Run pytest for graph layer + mock helpdesk tests"
	@echo "  make proof   Run benchmark harness → bench/results.json + docs/PROOF.md"
	@echo "  make demo    Start backend in deterministic replay mode (no FalkorDB needed)"
	@echo "  make clean   Remove __pycache__ and *.pyc files"

all: up

up:
	docker compose up -d

down:
	docker compose down -v

seed:
	@echo "Seeding FalkorDB with synthetic corpus..."
	python scripts/seed.py

test:
	pytest tests/ -v

proof:
	@echo "Running benchmark harness..."
	python bench/run.py

demo:
	@echo "Starting backend in replay mode (no FalkorDB needed)..."
	python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
