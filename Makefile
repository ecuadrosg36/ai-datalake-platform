# =============================================================================
# AI-Powered Data Lake Platform — Makefile
# =============================================================================

.PHONY: help install test lint format run-pipeline run-mcp clean validate-cfn

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Setup ---
install: ## Install all dependencies
	pip install -r requirements.txt
	pip install -e ".[dev]"

install-dev: ## Install dev dependencies only
	pip install -e ".[dev]"

# --- Testing ---
test: ## Run all tests with coverage
	python -m pytest tests/ -v --cov=src --cov-report=term-missing

test-ingestion: ## Run ingestion tests only
	python -m pytest tests/test_ingestion.py -v

test-transform: ## Run transformation tests only
	python -m pytest tests/test_transformation.py -v

test-ai: ## Run AI integration tests only
	python -m pytest tests/test_ai_integration.py -v

test-mcp: ## Run MCP server tests only
	python -m pytest tests/test_mcp_server.py -v

# --- Code Quality ---
lint: ## Run linter (ruff)
	ruff check src/ tests/

format: ## Format code (ruff)
	ruff format src/ tests/

typecheck: ## Run type checker (mypy)
	mypy src/

# --- Pipeline ---
run-pipeline: ## Run the full data lake pipeline
	python -m src.pipeline.orchestrator

run-bronze: ## Run Bronze (ingestion) layer only
	python -m src.pipeline.orchestrator --layer bronze

run-silver: ## Run Silver (transformation) layer only
	python -m src.pipeline.orchestrator --layer silver

run-gold: ## Run Gold (analytics) layer only
	python -m src.pipeline.orchestrator --layer gold

# --- MCP Server ---
run-mcp: ## Start the MCP server
	python -m src.mcp_server.server

# --- DBT ---
dbt-run: ## Run all DBT models
	cd dbt && dbt run

dbt-test: ## Run DBT tests
	cd dbt && dbt test

dbt-docs: ## Generate DBT documentation
	cd dbt && dbt docs generate && dbt docs serve

# --- Infrastructure ---
validate-cfn: ## Validate CloudFormation template
	aws cloudformation validate-template \
		--template-body file://infrastructure/cloudformation/datalake_stack.yaml

deploy-dev: ## Deploy to AWS (dev environment)
	aws cloudformation deploy \
		--template-file infrastructure/cloudformation/datalake_stack.yaml \
		--stack-name ai-datalake-dev \
		--parameter-overrides Environment=dev \
		--capabilities CAPABILITY_NAMED_IAM

# --- Cleanup ---
clean: ## Clean generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/
