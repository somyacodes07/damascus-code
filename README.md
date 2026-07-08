# Damascus

An intelligence operating system that executes, learns, and evolves.

**[📚 Read the Official Documentation](https://somyacodes07.github.io/damascus-docs/)**

## About

Damascus is a comprehensive intelligence operating system designed to execute complex workflows, learn from past executions, and evolve its capabilities. It features a robust backend infrastructure (FastAPI, PostgreSQL, Redis, Qdrant), a three-tier memory layer (working, episodic, semantic), and Ollama-backed single-agent execution with terminal and filesystem access. Everything can be managed seamlessly through its dedicated CLI and interactive dashboard.

## Phase 2 (V2) — Intelligence

This is the Phase 2 implementation of Damascus, adding:

- **Multi-Agent Teams**: Agent collaboration via typed message channels with budget controls.
- **Capability-Aware Policy Routing**: Smart model routing policies (`LOCAL_FIRST`, `LOWEST_COST`, etc.) for Ollama, OpenAI, Anthropic, Gemini, and OpenRouter.
- **Benchmark System**: Deterministic scoring (6 methods) + composite evaluations to compare versions.
- **Evolution Engine (V1)**: Automatic opportunity detection, variant generation, and promotion.
- **Research Layer**: Web search integration, finding extraction, and source tracking.

---

## V1 vs V2 Architectural Differences

| Capability | Phase 1 (V1) | Phase 2 (V2) |
| :--- | :--- | :--- |
| **Agent Paradigm** | Single-agent execution | **Multi-Agent Teams** with typed message channels |
| **Model Routing** | Hardcoded, priority-based fallback | **Capability-Aware Policy Routing** (6 policies) |
| **Providers** | Ollama, basic OpenRouter fallback | Ollama, OpenAI, Anthropic, Gemini, OpenRouter |
| **Benchmarks** | None | **Structured Benchmark Suite** + composite scoring |
| **Self-Improvement**| None | **Evolution Engine** (Opportunity → Variant → Promotion) |
| **Research** | None | **Research Layer** (Web search + finding extraction) |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry (`pip install poetry`)
- Just (`brew install just` or `cargo install just`)

### 1. Start Infrastructure Services

Damascus depends on multiple background services. Start them via Docker Compose:

```bash
docker compose up -d
```

Verify that PostgreSQL, Redis, Qdrant, NATS, and MinIO are healthy:

```bash
docker compose ps
```

### 2. Run the Backend Server (Required for CLI/TUI)

The CLI/TUI connects to the FastAPI backend at `localhost:8000`. **You must start the backend server before running CLI commands.**

```bash
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn damascus.main:app --reload --port 8000
```

* **Backend API**: http://localhost:8000  
* **API Docs (Swagger)**: http://localhost:8000/docs

### 3. Set Up CLI & TUI Dashboard

Open a new terminal window, navigate to the `cli/` directory, and run the following:

```bash
cd cli
poetry install
# Initialize a workspace
poetry run damascus workspace create "My Workspace"
# Launch the Text User Interface dashboard
poetry run damascus tui
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
