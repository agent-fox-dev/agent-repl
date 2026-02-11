.PHONY: build test lint package clean

build:
	uv build

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check src/ tests/

package:
	uv build --wheel --sdist

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf *.egg-info dist/ build/ .pytest_cache/ .ruff_cache/
