.PHONY: help proof demo seed

help:
	@echo "Quorum Makefile Commands:"
	@echo "  make proof  - Runs all tests, benchmarks, and generates docs/PROOF.md"
	@echo "  make demo   - Starts the deterministic replay mode demo"
	@echo "  make seed   - Generates the synthetic corpus and precomputed embeddings (Available Oct 15+)"

proof:
	@echo "Running tests and benchmarks..."
	@echo "(Placeholder for Oct 15: python bench/run.py > docs/PROOF.md)"

demo:
	@echo "Starting demo environment..."
	@echo "(Placeholder for Oct 15)"

seed:
	@echo "Seeding database..."
	@echo "(Placeholder for Oct 15)"
