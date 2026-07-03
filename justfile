# Damascus Justfile
# Run `just` to see available commands.

# Default recipe
default:
    @just --list

# ============================================================
# Infrastructure
# ============================================================

# Start all infrastructure services
up:
    docker compose up -d
    @echo "Infrastructure started. Run 'just status' to check."

# Stop all infrastructure services
down:
    docker compose down

# Stop all services and remove volumes (WARNING: deletes all data)
down-volumes:
    docker compose down -v

# Show status of all services
status:
    docker compose ps

# Tail logs of all services
logs:
    docker compose logs -f

# Tail logs of a specific service (usage: just logs-service postgres)
logs-service service:
    docker compose logs -f {{service}}

# Restart a specific service
restart service:
    docker compose restart {{service}}

# ============================================================
# Backend
# ============================================================

# Install backend dependencies
backend-install:
    cd backend && poetry install

# Run the backend development server
backend-dev:
    cd backend && poetry run uvicorn damascus.main:app --reload --port 8000

# Run database migrations
migrate:
    cd backend && poetry run alembic upgrade head

# Create a new database migration
migration name:
    cd backend && poetry run alembic revision --autogenerate -m "{{name}}"

# Run backend tests
test:
    cd backend && poetry run pytest

# Run backend tests with coverage
test-cov:
    cd backend && poetry run pytest --cov=damascus --cov-report=html

# Run linters
lint:
    cd backend && poetry run ruff check .
    cd backend && poetry run ruff format --check .

# Auto-fix linting issues
lint-fix:
    cd backend && poetry run ruff check . --fix
    cd backend && poetry run ruff format .

# ============================================================
# CLI
# ============================================================

# Install CLI dependencies
cli-install:
    cd cli && poetry install

# ============================================================
# Full Setup
# ============================================================

# Complete dev environment setup
setup: up backend-install migrate cli-install
    @echo "Damascus development environment ready!"
    @echo ""
    @echo "Next steps:"
    @echo "  1. Run 'just backend-dev' to start the backend"
    @echo "  2. Run 'damascus --help' to use the CLI"
    @echo "  3. Run 'damascus tui' to open the TUI"

# Verify the setup is correct
verify:
    python scripts/verify_setup.py
