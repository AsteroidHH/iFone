.PHONY: help proof test demo seed

help:
	@echo "Quorum Makefile Commands:"
	@echo "  make proof  - Runs all tests, benchmarks, and generates docs/PROOF.md"
	@echo "  make test   - Runs pytest backend test suite"
	@echo "  make demo   - Starts the deterministic replay mode backend"
	@echo "  make seed   - Generates the synthetic corpus and precomputed embeddings"

proof:
	@echo "Running tests and benchmarks..."
	python -m pytest backend/tests
	python bench/run.py

test:
	python -m pytest backend/tests

demo:
	@echo "Starting Quorum backend in deterministic replay mode..."
	python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

seed:
	@echo "Seeding database..."
	python scripts/seed.py

