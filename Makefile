.PHONY: all up down test proof clean

all: up

up:
	docker compose up -d

down:
	docker compose down -v

test:
	pytest tests/ -v

proof:
	python bench/run.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
