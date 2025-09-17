.PHONY: help install install-dev test test-unit test-integration test-e2e lint format type-check security-check clean docker-build docker-run docker-dev docker-stop setup health

# Default target
help:
	@echo "Available commands:"
	@echo "  setup           - Setup development environment"
	@echo "  install         - Install production dependencies"
	@echo "  install-dev     - Install development dependencies"
	@echo "  run-dev         - Run development server"
	@echo "  test            - Run all tests"
	@echo "  test-unit       - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e        - Run end-to-end tests"
	@echo "  lint            - Run all linting"
	@echo "  format          - Format code"
	@echo "  type-check      - Run type checking"
	@echo "  security-check  - Run security checks"
	@echo "  clean           - Clean build artifacts"
	@echo "  docker-build    - Build Docker image"
	@echo "  docker-run      - Run Docker container"
	@echo "  docker-dev      - Start development environment"
	@echo "  docker-stop     - Stop development environment"
	@echo "  health          - Check application health"

# Setup development environment
setup:
	python -m pip install --upgrade pip
	pip install -e ".[dev,test,docs]"
	pre-commit install
	@echo "✅ Development environment setup complete!"

# Install dependencies
install:
	pip install -e .

install-dev:
	pip install -e ".[dev,test,docs]"

# Run development server
run-dev:
	python -m airtable_whatsapp_agent.cli run --reload --log-level debug

# Testing
test:
	pytest tests/ -v --cov=src/airtable_whatsapp_agent --cov-report=html --cov-report=term

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

# Code quality
lint: format type-check security-check
	flake8 src/ tests/
	@echo "✅ All linting checks passed!"

format:
	black src/ tests/
	isort src/ tests/

type-check:
	mypy src/

security-check:
	bandit -r src/
	safety check

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/

# Docker commands
docker-build:
	docker build -t airtable-whatsapp-agent .

docker-run:
	docker run -p 8000:8000 --env-file .env airtable-whatsapp-agent

docker-dev:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Health check
health:
	python -m airtable_whatsapp_agent.cli health

# Configuration
config:
	python -m airtable_whatsapp_agent.cli config

# Version
version:
	python -m airtable_whatsapp_agent.cli version