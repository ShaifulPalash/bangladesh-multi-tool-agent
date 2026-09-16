# Common commands for this project. Run `make help` to see them all.
# Industry-standard convenience layer: `make <target>` instead of everyone
# remembering/retyping the same long shell commands.

.PHONY: help install install-dev data build run test lint fmt docker-up docker-down clean

help:
	@echo "make install       - install runtime dependencies"
	@echo "make install-dev   - install runtime + dev dependencies (tests, linter)"
	@echo "make data          - download + inspect the 3 datasets"
	@echo "make build         - build the 3 SQLite databases from data/"
	@echo "make run           - run the CLI agent (main.py)"
	@echo "make ui            - run the Streamlit chat UI locally"
	@echo "make test          - run the automated test suite"
	@echo "make test-queries  - run the 5 example queries against the live agent (needs API key)"
	@echo "make lint          - run ruff lint checks"
	@echo "make fmt           - auto-fix lint issues with ruff"
	@echo "make docker-up     - build and start everything via docker compose"
	@echo "make docker-down   - stop the docker compose stack"
	@echo "make clean         - remove caches, __pycache__, etc."

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

data:
	python scripts/download_and_inspect.py

build:
	python scripts/build_databases.py

run:
	python main.py

ui:
	streamlit run streamlit_app.py

test:
	pytest tests/ -v

test-queries:
	python scripts/test_queries.py

lint:
	ruff check .

fmt:
	ruff check . --fix

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache
