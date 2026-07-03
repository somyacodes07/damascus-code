# Damascus

An intelligence operating system that executes, learns, and evolves.

## Phase 1 (V1) — Foundation

This is the Phase 1 implementation of Damascus, providing:

- **Core Infrastructure**: FastAPI backend, PostgreSQL, Redis, Qdrant, NATS, MinIO
- **Workspace & Workflow**: CRUD operations and basic sequential workflow execution  
- **Memory Layer V1**: Working (Redis), Episodic (PostgreSQL), Semantic (Qdrant)
- **Single Agent Execution**: Ollama-backed agents with terminal and filesystem tools
- **CLI & TUI**: `damascus` command with interactive Textual dashboard

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry (`pip install poetry`)
- Just (`brew install just` or `cargo install just`)

### 1. Start Infrastructure

```bash
docker compose up -d
```

Verify all services are healthy:

```bash
docker compose ps
```

### 2. Set Up Backend

```bash
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn damascus.main:app --reload --port 8000
```

Backend API: http://localhost:8000  
API Docs: http://localhost:8000/docs

### 3. Set Up CLI

```bash
cd cli
poetry install
damascus --help
```

### 4. Configure Models (optional — Ollama recommended)

```bash
ollama pull llama3.1
```

Or set API keys in `.env`:

```env
DAMASCUS_MODELS_OPENAI_API_KEY=sk-...
DAMASCUS_MODELS_ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Verify Setup

```bash
python scripts/verify_setup.py
```

---

## Infrastructure Services

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:8000 | FastAPI application |
| API Docs | http://localhost:8000/docs | OpenAPI documentation |
| PostgreSQL | localhost:5432 | Structured data + episodic memory |
| Redis | localhost:6379 | Working memory + caching |
| Qdrant | http://localhost:6333 | Semantic vector memory |
| NATS | nats://localhost:4222 | Event bus |
| MinIO Console | http://localhost:9001 | Object storage |
| Grafana | http://localhost:3000 | Observability dashboards |
| Prometheus | http://localhost:9090 | Metrics |

---

## Project Structure

```
damascus-code/
├── backend/              # Python backend (FastAPI + core logic)
├── cli/                  # CLI and TUI interface
├── scripts/              # Development and deployment scripts
├── docker/               # Docker configuration files
├── docker-compose.yml    # Infrastructure services
├── justfile              # Project-level commands
└── README.md
```

---

## Development Commands

```bash
# Start all infrastructure
just up

# Stop everything
just down

# Run backend tests
just test

# Run linters
just lint

# View logs
just logs
```
